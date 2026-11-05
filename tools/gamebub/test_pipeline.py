"""@brief Deterministic tests for the bounded overlapping video pipeline."""

import threading
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from host import Profile, encode
from msv1 import VIDEO, frame_datagrams, validate_receiver_jpeg
from pipeline import Frame, VideoPipeline


class PipelineTests(unittest.TestCase):
    """@brief Verify queue bounds, worker overlap, expiry, and lifecycle."""

    def setUp(self):
        """@brief Use a fixed clock and a small solid RGB canvas."""
        self.now = 100
        self.image = Image.new("RGB", (720, 480), "red")

    def frame(self, number, captured=100):
        """@brief Construct a timestamped input for the pipeline."""
        return Frame(number, captured, number, self.image)

    def test_sender_cpu_is_final_only_after_worker_shutdown(self):
        """@brief CPU accounting includes the sender lifetime and marks a completed sample."""
        cpu = iter((100, 5100))
        pipeline = VideoPipeline(
            lambda image: b"x",
            lambda *args: True,
            100,
            10,
            clock=lambda: 100,
            cpu_clock=lambda: next(cpu),
        )
        self.assertFalse(pipeline.snapshot()["sender_thread_cpu_final"])
        pipeline.close()
        snapshot = pipeline.snapshot()
        self.assertTrue(snapshot["sender_thread_cpu_final"])
        self.assertEqual(snapshot["sender_thread_cpu_ns"], 5000)

    def test_sender_start_failure_releases_started_encoder(self):
        """@brief A later startup error cannot strand the first worker indefinitely."""
        created = []

        def factory(*args, **kwargs):
            """@brief Start a real encoder but make the owned sender fail before launch."""
            worker = threading.Thread(*args, **kwargs)
            if kwargs["name"] == "gamebub-sender":
                worker.start = lambda: (_ for _ in ()).throw(RuntimeError("sender startup"))
            created.append(worker)
            return worker

        with (
            patch("pipeline.Thread", side_effect=factory),
            self.assertRaisesRegex(RuntimeError, "sender startup"),
        ):
            VideoPipeline(lambda image: b"x", lambda *args: True, 100, 10, clock=lambda: 100)
        self.assertFalse(any(worker.is_alive() for worker in created))

    def test_startup_exception_joins_each_worker_that_is_already_alive(self):
        """@brief Cleanup also handles a failure raised after the second worker starts."""
        for encoder_alive, sender_alive in ((False, False), (True, False), (True, True)):
            with self.subTest(encoder_alive=encoder_alive, sender_alive=sender_alive):
                encoder, sender = Mock(), Mock()
                encoder.is_alive.return_value = encoder_alive
                sender.is_alive.return_value = sender_alive
                sender.start.side_effect = RuntimeError("startup interrupted")
                owner = VideoPipeline.__new__(VideoPipeline)
                with (
                    patch("pipeline.Thread", side_effect=(encoder, sender)),
                    self.assertRaisesRegex(RuntimeError, "startup interrupted"),
                ):
                    owner.__init__(lambda image: b"x", lambda *args: True, 100, 10)
                self.assertTrue(owner.closed)
                self.assertEqual(encoder.join.call_count, int(encoder_alive))
                self.assertEqual(sender.join.call_count, int(sender_alive))

    def test_encoder_overlaps_blocked_sender_and_keeps_latest_encoded(self):
        """@brief A blocked sender does not prevent encoding or create an unbounded queue."""
        entered, release, third_encoded = threading.Event(), threading.Event(), threading.Event()
        sent, encoded = [], []

        def encode(image):
            encoded.append(image.getpixel((0, 0))[0])
            if len(encoded) == 3:
                third_encoded.set()
            return bytes([len(encoded)])

        def send(frame, payload):
            sent.append((frame.frame_id, payload))
            if frame.frame_id == 1:
                entered.set()
                self.assertTrue(release.wait(5))
            return True

        pipeline = VideoPipeline(encode, send, 100, 10, lambda: self.now)
        try:
            pipeline.submit(self.frame(1))
            self.assertTrue(entered.wait(5))
            pipeline.submit(self.frame(2))
            # Wait until frame 2 has been encoded before submitting frame 3.
            with pipeline.condition:
                self.assertTrue(
                    pipeline.condition.wait_for(lambda: pipeline.encoded is not None, 5)
                )
            pipeline.submit(self.frame(3))
            self.assertTrue(third_encoded.wait(5))
            with pipeline.condition:
                self.assertTrue(
                    pipeline.condition.wait_for(lambda: pipeline.counts["encoded_replaced"] == 1, 5)
                )
        finally:
            release.set()
            pipeline.close()
        self.assertEqual(sent, [(1, b"\x01"), (3, b"\x03")])
        self.assertEqual(pipeline.snapshot()["counts"]["encoded_replaced"], 1)

    def test_latest_raw_and_owned_image(self):
        """@brief A blocked encoder retains only the newest copied waiting canvas."""
        entered, release = threading.Event(), threading.Event()
        sent = []

        def encode(image):
            if not entered.is_set():
                entered.set()
                self.assertTrue(release.wait(5))
            return bytes([image.getpixel((0, 0))[0]])

        pipeline = VideoPipeline(
            encode, lambda f, b: sent.append((f.frame_id, b)) or True, 100, 10, lambda: self.now
        )
        try:
            pipeline.submit(self.frame(1))
            self.assertTrue(entered.wait(5))
            pipeline.submit(self.frame(2))
            pipeline.submit(self.frame(3))
            self.image.putpixel((0, 0), (0, 0, 0))
            self.assertEqual(pipeline.snapshot()["raw_waiting"], 1)
        finally:
            release.set()
            pipeline.close()
        self.assertEqual(sent[-1], (3, b"\xff"))
        self.assertEqual(pipeline.snapshot()["counts"]["raw_replaced"], 1)

    def test_stale_before_encoding_and_after_encoding(self):
        """@brief Expired work is dropped before either costly step."""
        calls = []
        pipeline = VideoPipeline(
            lambda image: calls.append("encode") or b"x",
            lambda f, b: calls.append("send") or True,
            10,
            10,
            lambda: self.now,
        )
        pipeline.submit(self.frame(1, 89))
        pipeline.close()
        self.assertEqual(calls, [])
        self.assertEqual(pipeline.snapshot()["counts"]["stale_before_encode"], 1)

        def slow_encode(image):
            self.now = 111
            return b"x"

        self.now = 100
        pipeline = VideoPipeline(
            slow_encode, lambda f, b: calls.append("send") or True, 10, 10, lambda: self.now
        )
        pipeline.submit(self.frame(2))
        pipeline.close()
        self.assertEqual(calls, [])
        self.assertEqual(pipeline.snapshot()["counts"]["stale_before_send"], 1)

    def test_invalid_input_failures_and_closed_submission(self):
        """@brief Reject invalid input and bound failures without killing worker threads."""
        for limits in ((0, 1), (1, True)):
            with self.assertRaises(ValueError):
                VideoPipeline(None, None, *limits)
        outcomes = iter((b"", b"too large", b"ok", b"ok"))
        sends = iter((False, True))
        p = VideoPipeline(
            lambda image: next(outcomes), lambda f, b: next(sends), 100, 2, lambda: self.now
        )
        for bad in (
            None,
            Frame(-1, 100, 1, self.image),
            Frame(0, 101, 1, self.image),
            Frame(0, 100, 1, Image.new("L", (720, 480))),
        ):
            with self.assertRaises(ValueError):
                p.submit(bad)
        # Synchronize after each attempt to avoid intentional latest-slot replacement.
        for number in range(4):
            p.submit(self.frame(number))
            with p.condition:
                self.assertTrue(
                    p.condition.wait_for(
                        lambda number=number: (
                            sum(p.counts[k] for k in ("encode_failures", "sent", "send_failures"))
                            == number + 1
                        ),
                        5,
                    )
                )
        p.close()
        self.assertFalse(p.submit(self.frame(5)))
        self.assertEqual(p.snapshot()["counts"]["encode_failures"], 2)
        self.assertEqual(p.snapshot()["counts"]["send_failures"], 1)
        self.assertEqual(p.snapshot()["counts"]["sent"], 1)

    def test_real_jpeg_through_msv1_packetization(self):
        """@brief The overlapped pipeline can hand actual conforming JPEG to MSV1."""
        packets = []
        p = VideoPipeline(
            lambda image: encode(image, 75, Profile())[0],
            lambda frame, jpeg: (
                packets.extend(frame_datagrams(jpeg, frame.frame_id, frame.capture_us)) or True
            ),
            100,
            262144,
            lambda: self.now,
        )
        p.submit(self.frame(7))
        p.close()
        self.assertEqual(p.snapshot()["counts"]["sent"], 1)
        self.assertGreater(len(packets), 1)
        self.assertTrue(all(VIDEO.unpack(packet[: VIDEO.size])[4] == 7 for packet in packets))
        jpeg = b"".join(packet[VIDEO.size :] for packet in packets)
        self.assertEqual(validate_receiver_jpeg(jpeg)["subsampling"], "4:2:0")

    def test_callback_exceptions_and_older_capture(self):
        """@brief Callback errors are counted, and capture timestamps cannot regress."""
        results = iter((ValueError("encode"), b"ok", b"ok"))
        sends = iter((OSError("send"), True))

        def encode_callback(image):
            value = next(results)
            if isinstance(value, Exception):
                raise value
            return value

        def send_callback(frame, payload):
            value = next(sends)
            if isinstance(value, Exception):
                raise value
            return value

        p = VideoPipeline(encode_callback, send_callback, 100, 2, lambda: self.now)
        try:
            for number in range(3):
                self.assertTrue(p.submit(self.frame(number)))
                with p.condition:
                    self.assertTrue(
                        p.condition.wait_for(
                            lambda number=number: (
                                sum(
                                    p.counts[k]
                                    for k in ("encode_failures", "sent", "send_failures")
                                )
                                == number + 1
                            ),
                            5,
                        )
                    )
            self.assertFalse(p.submit(self.frame(4, 99)))
        finally:
            p.close()
        self.assertEqual(p.snapshot()["counts"]["encode_failures"], 1)
        self.assertEqual(p.snapshot()["counts"]["send_failures"], 1)
        self.assertEqual(p.snapshot()["counts"]["sent"], 1)
        self.assertEqual(p.snapshot()["last_error"], "send: OSError: send")

    def test_metadata_encoder_receives_frame_and_recovers_after_error(self):
        """@brief Optional encoder gets capture metadata and callback errors keep the worker alive."""
        received, sent = [], []

        def encode_frame(frame):
            """@brief Fail once, then encode the next complete metadata-bearing frame."""
            received.append(frame)
            if frame.frame_id == 1:
                raise ValueError("retry deadline elapsed")
            return str(frame.frame_id).encode()

        pipeline = VideoPipeline(
            lambda image: self.fail("legacy encoder should not be called"),
            lambda frame, payload: sent.append((frame.frame_id, payload)) or True,
            100,
            10,
            lambda: self.now,
            encode_frame=encode_frame,
        )
        try:
            for number in (1, 2):
                self.assertTrue(pipeline.submit(self.frame(number, captured=90 + number)))
                with pipeline.condition:
                    self.assertTrue(
                        pipeline.condition.wait_for(
                            lambda number=number: (
                                pipeline.counts["encode_failures"] + pipeline.counts["sent"]
                                == number
                            ),
                            5,
                        )
                    )
        finally:
            pipeline.close()

        self.assertEqual(
            [(frame.frame_id, frame.captured_ns, frame.capture_us) for frame in received],
            [(1, 91, 1), (2, 92, 2)],
        )
        self.assertEqual(sent, [(2, b"2")])
        self.assertEqual(pipeline.snapshot()["counts"]["encode_failures"], 1)
        self.assertEqual(
            pipeline.snapshot()["last_error"], "encode: ValueError: retry deadline elapsed"
        )


if __name__ == "__main__":
    unittest.main()
