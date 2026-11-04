"""@brief Bounded overlapping video preparation and transmission for host experiments.

This is a local pipeline primitive, not a Sunshine mode or an authenticated session.
Callbacks must return in bounded time; shutdown cannot interrupt a blocked callback.
"""

from collections import Counter
from dataclasses import dataclass, replace
from threading import Condition, Thread
from time import perf_counter_ns

from PIL import Image

from host import HEIGHT, WIDTH


@dataclass(frozen=True)
class Frame:
    """@brief An owned RGB canvas and its local capture metadata.

    captured_ns and encoded_ns use the pipeline's monotonic clock. With the
    default clock, supply timestamps from time.perf_counter_ns().
    """

    frame_id: int
    captured_ns: int
    capture_us: int
    image: Image.Image
    encoded_ns: int = 0


class VideoPipeline:
    """@brief One latest raw frame and one latest encoded frame, plus active workers.

    The capture caller owns scaling and timing. A single encoder and a single sender
    run concurrently. Callbacks must not retain or mutate frame data after returning.
    """

    def __init__(
        self, encode, send, max_age_ns, max_encoded_bytes, clock=perf_counter_ns, encode_frame=None
    ):
        """@brief Start workers with bounded queues and injectable callbacks/clock.

        @param encode Callable accepting an RGB canvas and returning JPEG bytes.
        @param send Callable accepting frame metadata and JPEG bytes; returns success.
        @param max_age_ns Maximum age before encode and send, in monotonic nanoseconds.
        @param max_encoded_bytes Maximum complete encoded frame size.
        @param clock Monotonic nanosecond clock shared with submitted timestamps.
        @param encode_frame Optional callable accepting a complete Frame for deadline-aware
            encoding; when omitted, encode is called with the frame's image as before.
        """
        if any(type(v) is not int or v <= 0 for v in (max_age_ns, max_encoded_bytes)):
            raise ValueError("Pipeline limits must be positive integers")
        self.encode, self.send, self.clock = encode, send, clock
        self.encode_frame = encode_frame
        self.max_age_ns, self.max_encoded_bytes = max_age_ns, max_encoded_bytes
        self.condition = Condition()
        self.raw = self.encoded = None
        self.closed = self.encoder_done = False
        self.last_capture = -1
        self.counts = Counter()
        self.last_error = None
        self.encoder = Thread(target=self._encode_loop, name="gamebub-encoder")
        self.sender = Thread(target=self._send_loop, name="gamebub-sender")
        self.encoder.start()
        self.sender.start()

    def submit(self, frame):
        """@brief Copy and submit a capture; replace any raw frame waiting to encode.

        @param frame Valid 720x480 RGB canvas and capture metadata.
        @return False when closed or capture order regresses; otherwise True.
        """
        if (
            not isinstance(frame, Frame)
            or type(frame.frame_id) is not int
            or not 0 <= frame.frame_id <= 0xFFFFFFFF
            or type(frame.capture_us) is not int
            or not 0 <= frame.capture_us <= 0xFFFFFFFFFFFFFFFF
            or type(frame.captured_ns) is not int
            or not 0 <= frame.captured_ns <= self.clock()
            or not isinstance(frame.image, Image.Image)
            or frame.image.mode != "RGB"
            or frame.image.size != (WIDTH, HEIGHT)
        ):
            raise ValueError("Invalid frame or capture metadata")
        with self.condition:
            if self.closed or frame.captured_ns < self.last_capture:
                return False
            if self.raw is not None:
                self.counts["raw_replaced"] += 1
            self.raw = Frame(
                frame.frame_id, frame.captured_ns, frame.capture_us, frame.image.copy()
            )
            self.last_capture = frame.captured_ns
            self.counts["submitted"] += 1
            self.condition.notify_all()
            return True

    def _stale(self, frame):
        """@brief Check a capture against its monotonic deadline."""
        return self.clock() - frame.captured_ns > self.max_age_ns

    def _encode_loop(self):
        """@brief Encode the latest nonstale canvas until the raw slot is drained."""
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.raw is not None or self.closed)
                if self.raw is None:
                    self.encoder_done = True
                    self.condition.notify_all()
                    return
                frame, self.raw = self.raw, None
            if self._stale(frame):
                with self.condition:
                    self.counts["stale_before_encode"] += 1
                continue
            try:
                payload = (
                    self.encode_frame(frame)
                    if self.encode_frame is not None
                    else self.encode(frame.image)
                )
                if not isinstance(payload, bytes) or not 0 < len(payload) <= self.max_encoded_bytes:
                    raise ValueError("Encoded frame outside configured bounds")
            except Exception as error:  # noqa: BLE001 - keep worker alive after callback failures
                with self.condition:
                    self.counts["encode_failures"] += 1
                    self.last_error = f"encode: {type(error).__name__}: {error}"
                    self.condition.notify_all()
                continue
            with self.condition:
                self.counts["encoded"] += 1
                if self.encoded is not None:
                    self.counts["encoded_replaced"] += 1
                self.encoded = (replace(frame, encoded_ns=self.clock()), payload)
                self.condition.notify_all()

    def _send_loop(self):
        """@brief Send the latest nonstale encoded frame until the encoder finishes."""
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.encoded is not None or self.encoder_done)
                if self.encoded is None:
                    return
                (frame, payload), self.encoded = self.encoded, None
            if self._stale(frame):
                with self.condition:
                    self.counts["stale_before_send"] += 1
                continue
            try:
                sent = self.send(frame, payload)
            except Exception as error:  # noqa: BLE001 - keep worker alive after callback failures
                sent = False
                with self.condition:
                    self.last_error = f"send: {type(error).__name__}: {error}"
            with self.condition:
                self.counts["sent" if sent else "send_failures"] += 1
                self.condition.notify_all()

    def close(self):
        """@brief Stop accepting captures and drain the two slots; join both workers."""
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.encoder.join()
        self.sender.join()

    def snapshot(self):
        """@brief Return thread-safe queue occupancy and cumulative counters."""
        with self.condition:
            return {
                "raw_waiting": int(self.raw is not None),
                "encoded_waiting": int(self.encoded is not None),
                "counts": dict(self.counts),
                "last_error": self.last_error,
            }
