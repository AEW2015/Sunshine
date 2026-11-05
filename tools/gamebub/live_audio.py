"""@brief Bounded callback WASAPI loopback and product-rounded AV v1 audio.

Silence/inactive-device callbacks may stop; inactivity is reported by the owner,
never filled with invented PCM. No capture or imports of PyAudio occur on import.
"""

import array
import queue
import threading
import time
from collections import deque

from audio_codec import AudioEncoder, validate_block


class LoopbackAudio:
    """@brief Own bounded PCM/ADPCM queues and one daemon encoding/capture worker."""

    def __init__(self, gain=0.75, backend=None, clock=time.perf_counter_ns):
        """@brief Prepare capture; gain must be between zero and one inclusive."""
        if not 0 <= gain <= 1:
            raise ValueError("Gain must be within[0,1]")
        self.gain, self.backend, self.clock = gain, backend, clock
        self.pcm, self.blocks = queue.Queue(8), queue.Queue(4)
        self.eviction_trace = deque(maxlen=32)
        self.eviction_trace_lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.error = None
        self.last_capture_ns = None
        self.info = {}
        self.counts = {
            "encoded": 0,
            "pcm_drops": 0,
            "queue_drops": 0,
            "trace_clock_errors": 0,
            "capture_errors": 0,
            "captured_frames": 0,
            "encoded_source_frames": 0,
            "pcm_dropped_frames": 0,
            "tail_frames": 0,
            "unsent_tail_blocks": 0,
            "late_callbacks": 0,
        }

    def callback(self, raw, frames, timing, status):
        """@brief Enqueue bounded native PCM; never encode or block the audio callback."""
        if self.stop.is_set():
            self.counts["late_callbacks"] += 1
            return None, self.backend.paComplete
        if status:
            self.counts["capture_errors"] += 1
            self.error = f"WASAPI callback status:{status}"
            return None, self.backend.paAbort
        if not isinstance(raw, bytes) or frames <= 0 or len(raw) != frames * self.channels * 2:
            self.counts["capture_errors"] += 1
            self.error = "Short/invalid callback PCM"
            return None, self.backend.paAbort
        stamp = self.clock()
        self.last_capture_ns = stamp
        self.counts["captured_frames"] += frames
        try:
            self.pcm.put_nowait((raw, stamp))
        except queue.Full:
            # A missing PCM interval must fail visibly rather than compress time.
            self.counts["pcm_drops"] += 1
            self.counts["pcm_dropped_frames"] += frames
            self.error = "PCM capture queue overflow"
            return None, self.backend.paAbort
        return None, self.backend.paContinue

    def publish(self, block, stamp):
        """@brief Allocate sequence and record metadata for each actual oldest-block eviction.

        @param block Encoded ADPCM payload, kept only in the bounded send queue.
        @param stamp Monotonic capture time for this newly published block.
        @note A trace-clock failure is counted separately and does not block publication.
        """
        validate_block(block)
        sequence = self.counts["encoded"] & 0xFFFFFFFF
        self.counts["encoded"] += 1
        if self.blocks.full():
            try:
                evicted_sequence, evicted_capture_ns, _evicted_block = self.blocks.get_nowait()
            except queue.Empty:
                pass
            else:
                try:
                    publish_ns = self.clock()
                    clock_error = None
                except Exception as error:  # noqa: BLE001 - telemetry cannot fail audio publication
                    publish_ns = None
                    clock_error = type(error).__name__
                shutdown = self.stop.is_set()
                with self.eviction_trace_lock:
                    self.counts["queue_drops"] += 1
                    self.counts["trace_clock_errors"] += int(clock_error is not None)
                    self.eviction_trace.append(
                        {
                            "evicted_sequence": evicted_sequence,
                            "evicted_capture_ns": evicted_capture_ns,
                            "new_sequence": sequence,
                            "publish_ns": publish_ns,
                            "shutdown": shutdown,
                            "clock_error": clock_error,
                        }
                    )
        self.blocks.put_nowait((sequence, stamp, block))

    def start(self):
        """@brief Start one worker; callbacks and native cleanup remain worker-owned."""
        if self.thread is not None:
            raise RuntimeError("Audio worker already started")
        self.thread = threading.Thread(target=self._run, daemon=True, name="gamebub-loopback")
        self.thread.start()

    def _run(self):
        """@brief Capture callbacks and resample/encode outside the native callback."""
        try:
            if self.backend is None:
                import pyaudiowpatch

                self.backend = pyaudiowpatch
            with self.backend.PyAudio() as manager:
                device = manager.get_default_wasapi_loopback()
                self.channels = min(2, int(device["maxInputChannels"]))
                rate = int(device["defaultSampleRate"])
                if not device.get("isLoopbackDevice") or self.channels not in (1, 2):
                    raise ValueError("Expected default mono/stereo-capable WASAPI loopback")
                self.info = {
                    "name": device["name"],
                    "index": device["index"],
                    "rate": rate,
                    "channels": self.channels,
                    "gain": self.gain,
                }
                encoder = AudioEncoder(rate, self.channels)
                with manager.open(
                    format=self.backend.paInt16,
                    channels=self.channels,
                    rate=rate,
                    input=True,
                    input_device_index=device["index"],
                    frames_per_buffer=max(1, rate // 100),
                    stream_callback=self.callback,
                ):
                    while not self.stop.is_set() and self.error is None:
                        try:
                            raw, stamp = self.pcm.get(timeout=0.05)
                        except queue.Empty:
                            continue
                        values = array.array("h", raw)
                        scaled = array.array("h", (round(v * self.gain) for v in values)).tobytes()
                        for block in encoder.push(scaled):
                            self.publish(block, stamp)
                        self.counts["encoded_source_frames"] += len(scaled) // (self.channels * 2)
                    # Report, but never pad or send resampler tail after STOP.
                    final, tail = encoder.finish()
                    self.counts["tail_frames"] = tail
                    self.counts["unsent_tail_blocks"] = len(final)
        except Exception as error:  # noqa: BLE001 - worker failures are delivered to session owner
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.stop.set()

    def close(self, timeout=2):
        """@brief Bound join and snapshot counts plus bounded eviction metadata.

        @param timeout Maximum worker join time in seconds.
        @return Counts, detached eviction trace snapshot, queued work and shutdown status.
        """
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout)
        with self.eviction_trace_lock:
            counts = dict(self.counts)
            eviction_trace = tuple(dict(record) for record in self.eviction_trace)
            eviction_trace_overwritten = max(counts["queue_drops"] - len(eviction_trace), 0)
        with self.pcm.mutex:
            queued_pcm_blocks = len(self.pcm.queue)
            queued_pcm_bytes = sum(len(raw) for raw, _ in self.pcm.queue)
        return {
            **counts,
            "eviction_trace": eviction_trace,
            "eviction_trace_overwritten": eviction_trace_overwritten,
            "queued_unsent": self.blocks.qsize(),
            "queued_pcm_blocks": queued_pcm_blocks,
            "queued_pcm_bytes": queued_pcm_bytes,
            "queued_pcm_frames": queued_pcm_bytes // (getattr(self, "channels", 1) * 2),
            "device": self.info,
            "error": self.error,
            "shutdown_complete": self.thread is None or not self.thread.is_alive(),
        }
