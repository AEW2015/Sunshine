"""@brief Experimental video-only MSV1 clip/desktop sender for a trusted test LAN.

This is not Sunshine integration. Feedback confirms ingress, not displayed video.
"""

import argparse
import json
import math
import socket
import threading
import time
from collections import Counter, OrderedDict
from pathlib import Path

import av
from PIL import Image, ImageGrab

from controller import ControllerTracker
from event_log import EventLog
from host import WIDTH, canvas, clip_frames, shift_canvas_right
from msv1 import (
    FEEDBACK,
    MAX_FRAME,
    VIDEO,
    JpegCapacityError,
    Pacer,
    PartialSendError,
    encode_receiver_jpeg,
    parse_feedback,
    send_frame,
)
from pipeline import Frame, VideoPipeline
from quality import QualityController


def frame_key_is_newer_or_same(current, previous):
    """@brief Compare wrapping frame identifiers and equal-frame capture timestamps.

    @param current Candidate (frame ID, capture timestamp) key.
    @param previous Most recently accepted (frame ID, capture timestamp) key.
    @return True for a newer serial ID or the exact same frame key.
    """
    frame_id, capture_us = current
    previous_id, previous_capture_us = previous
    frame_delta = (frame_id - previous_id) & 0xFFFFFFFF
    if frame_delta == 0:
        return capture_us == previous_capture_us
    return frame_delta < 0x80000000


class _FeedbackSilenceStop(OSError):
    """@brief Stop a paced send when the feedback silence limit is reached."""


class FeedbackGate:
    """@brief Limit sends during feedback silence while retaining recovery probes.

    Only matching feedback from the current session confirms liveness. Once
    silence exceeds the deadline, only feedback for a newly sent probe can
    resume normal sending; old ACKs and heartbeats cannot revive the session.
    """

    def __init__(
        self,
        now_ns,
        timeout_ns=750_000_000,
        probe_ns=1_000_000_000,
        max_silence_ns=3_000_000_000,
    ):
        """@brief Set fixed monotonic durations; None defers the initial grace period.

        @param now_ns Initial grace timestamp, or None to defer it until traffic is sent.
        @param timeout_ns Maximum feedback silence before probing.
        @param probe_ns Minimum interval between recovery probes.
        @param max_silence_ns Absolute per-feedback-epoch silence bound.
        """
        if timeout_ns <= 0 or probe_ns <= 0 or max_silence_ns < timeout_ns:
            raise ValueError("Feedback timing must be positive")
        self.last_feedback = now_ns
        self.timeout_ns, self.probe_ns = timeout_ns, probe_ns
        self.max_silence_ns = max_silence_ns
        self.probing = False
        self.next_probe = now_ns
        self.probe_key = None
        self.probe_started_ns = None
        self.heartbeat_key = None
        self.candidate = None
        self.extension_deadline = None

    def expire(self, now_ns):
        """@brief Enter probing once and indicate when old pending ACKs must be cleared."""
        if self.last_feedback is None or self.probing:
            return False
        deadline = self.last_feedback + self.timeout_ns
        if now_ns > deadline and self.candidate is not None and self.extension_deadline is None:
            self.extension_deadline = max(
                deadline,
                min(
                    self.candidate[1] + self.timeout_ns,
                    self.last_feedback + self.max_silence_ns,
                ),
            )
        if self.extension_deadline is not None:
            deadline = self.extension_deadline
        if now_ns > deadline:
            self.probing = True
            self.next_probe = now_ns
            self.probe_key = None
            self.probe_started_ns = None
            self.heartbeat_key = None
            self.candidate = None
            self.extension_deadline = None
            return True
        return False

    def offer(self, key, now_ns):
        """@brief Allow a frame or a bounded recovery probe; signal pending reset."""
        expired = self.expire(now_ns)
        if not self.probing:
            return True, expired
        if now_ns < self.next_probe:
            return False, expired
        self.next_probe = now_ns + self.probe_ns
        self.probe_key = key
        self.probe_started_ns = None
        return True, True

    def sent(self, now_ns):
        """@brief Arm initial grace after transmission, preserving any earlier feedback.

        @param now_ns Monotonic time after a send which transmitted at least one byte.
        """
        if self.last_feedback is None:
            self.last_feedback = now_ns

    def packet_sent(self, key, frame_deadline_ns, now_ns):
        """@brief Record a successful datagram as eligible for bounded in-flight grace.

        @param key Frame ID and capture timestamp.
        @param frame_deadline_ns Absolute monotonic capture-age deadline.
        @param now_ns Monotonic time after the successful datagram send.
        """
        self.sent(now_ns)
        if self.probing and self.probe_key == key and self.probe_started_ns is None:
            self.probe_started_ns = now_ns
        if not self.probing and self.extension_deadline is None:
            self.candidate = (key, frame_deadline_ns)

    def permit_packet(self, key, now_ns):
        """@brief Bound one recovery probe as well as the established feedback epoch.

        @param key Frame ID and capture timestamp.
        @param now_ns Current monotonic time.
        @return False for a stale or overlong recovery probe.
        """
        if not self.probing:
            return True
        if key != self.probe_key:
            return False
        if (
            self.probe_started_ns is not None
            and now_ns - self.probe_started_ns > self.max_silence_ns
        ):
            self.probe_key = None
            self.probe_started_ns = None
            return False
        return True

    def send_finished(self, key, now_ns):
        """@brief End a candidate's transmission and bound its remaining ACK grace.

        @param key Frame ID and capture timestamp.
        @param now_ns Monotonic time after the send completes or aborts.
        """
        if self.candidate is None or self.candidate[0] != key:
            return
        self.candidate = (key, min(self.candidate[1], now_ns))
        if self.extension_deadline is not None:
            self.extension_deadline = min(self.extension_deadline, now_ns + self.timeout_ns)

    def feedback(self, key, matched, now_ns):
        """@brief Process a matching ACK or current heartbeat and report liveness."""
        if self.probing:
            if (
                not matched
                or key != self.probe_key
                or self.probe_started_ns is None
                or not self.permit_packet(key, now_ns)
            ):
                return False
            self.probing = False
            self.probe_key = None
            self.probe_started_ns = None
        elif not matched and key != self.heartbeat_key:
            return False
        self.last_feedback = now_ns
        if self.candidate is not None and self.candidate[0] == key:
            self.candidate = None
        self.extension_deadline = None
        if self.heartbeat_key is None or frame_key_is_newer_or_same(key, self.heartbeat_key):
            self.heartbeat_key = key
        return True


class ReceiverCounterTracker:
    """@brief Track cumulative receiver counters without attributing them to frames.

    Feedback heartbeats echo the currently active frame, so counter deltas prove
    aggregate receiver outcomes but cannot safely identify a particular frame.
    """

    _HALF_RANGE = 0x80000000

    def __init__(self):
        """@brief Start without a receiver counter baseline."""
        self.key = None
        self.received = None
        self.dropped = None

    def observe(self, frame_id, capture_us, received, dropped):
        """@brief Accept a current counter snapshot and return wrap-safe deltas.

        Older feedback snapshots are ignored using wrapping frame-ID order;
        equal IDs must have the same capture timestamp. The first snapshot and
        implausible counter jumps establish a baseline without claiming outcomes.
        A small counter decrease is indistinguishable from wrap and is treated as wrap.

        @param frame_id Echoed wrapping frame identifier.
        @param capture_us Echoed host capture timestamp.
        @param received Cumulative completed-frame counter.
        @param dropped Cumulative dropped-frame counter.
        @return Snapshot deltas and reset state, or None for an older snapshot.
        """
        key = (frame_id, capture_us)
        if self.key is not None and not frame_key_is_newer_or_same(key, self.key):
            return None

        if self.received is None:
            received_delta = dropped_delta = 0
            reset = False
            baseline = True
        else:
            received_delta = (received - self.received) & 0xFFFFFFFF
            dropped_delta = (dropped - self.dropped) & 0xFFFFFFFF
            if key == self.key and max(received_delta, dropped_delta) >= self._HALF_RANGE:
                # The receiver can emit multiple snapshots for one active frame;
                # a regressing duplicate is reordered feedback, not a reboot.
                return None
            reset = max(received_delta, dropped_delta) >= self._HALF_RANGE
            baseline = reset
            if reset:
                received_delta = dropped_delta = 0

        self.key, self.received, self.dropped = key, received, dropped
        return {
            "received_delta": received_delta,
            "dropped_delta": dropped_delta,
            "reset": reset,
            "baseline": baseline,
        }


class Session:
    """@brief Bounded experimental JPEG sender and peer feedback collector."""

    def __init__(
        self,
        sock,
        log,
        fps,
        mbps,
        max_age_ms,
        quality,
        min_quality,
        packet_timing=False,
        *,
        max_jpeg_bytes=MAX_FRAME,
        jpeg_retry_quality_drop=0,
    ):
        """@brief Configure a connected nonblocking UDP socket and per-run log.

        @param sock Connected nonblocking datagram socket for the test peer.
        @param log Open text file for JSONL events.
        @param fps Target capture rate in frames per second.
        @param mbps Maximum MSV1 datagram bitrate, excluding lower-layer overhead.
        @param max_age_ms Capture-to-send deadline in milliseconds.
        @param quality Initial and maximum JPEG quality.
        @param min_quality Minimum adaptation quality.
        @param packet_timing Record per-datagram timing in the bounded event log.
        @param max_jpeg_bytes Maximum complete JPEG bytes for this receiver session.
        @param jpeg_retry_quality_drop One optional quality reduction after size rejection.
        """
        if (
            type(fps) is not int
            or not 1 <= fps <= 30
            or not math.isfinite(mbps)
            or mbps <= 0
            or not math.isfinite(max_age_ms)
            or max_age_ms < 0.000001
            or not 1 <= min_quality <= quality <= 95
            or type(max_jpeg_bytes) is not int
            or not 1 <= max_jpeg_bytes <= MAX_FRAME
            or type(jpeg_retry_quality_drop) is not int
            or not 0 <= jpeg_retry_quality_drop <= 94
        ):
            raise ValueError("Invalid session rate, deadline or quality")
        self.sock, self.log, self.fps = sock, EventLog(log), fps
        self.packet_timing = packet_timing
        self.max_jpeg_bytes = max_jpeg_bytes
        self.jpeg_retry_quality_drop = jpeg_retry_quality_drop
        self.rate = mbps * 1e6 / 8
        self.age_ns = int(max_age_ms * 1e6)
        self.quality = QualityController(quality, min_quality)
        self.recovery_eligible = False
        self.lock = threading.Lock()
        self.pending = OrderedDict()
        self.receiver_counters = ReceiverCounterTracker()
        self.status_pressure_keys = OrderedDict()
        self.counts = Counter()
        self.stop = threading.Event()
        self.pacer = Pacer()
        self.start_ns = time.perf_counter_ns()
        # Capture startup and a paced first frame can be slower than the liveness timeout.
        self.gate = FeedbackGate(None)
        self.controller = ControllerTracker()
        self.feedback_thread = threading.Thread(target=self._feedback_loop, name="gamebub-feedback")
        self.feedback_thread.start()
        self.pipeline = VideoPipeline(
            self._encode, self._send, self.age_ns, max_jpeg_bytes, encode_frame=self._encode_frame
        )

    def _event(self, kind, **fields):
        """@brief Serialize one event under the session lock and return enqueue status."""
        return self.log.submit({"event": kind, **fields})

    def _encode_frame(self, frame):
        """@brief Encode with frame identity and the original monotonic age deadline."""
        return self._encode(
            frame.image,
            frame.captured_ns + self.age_ns,
            frame_id=frame.frame_id,
            capture_us=frame.capture_us,
        )

    def _encode(self, image, deadline_ns=None, *, frame_id=None, capture_us=None):
        """@brief Encode within capacity, optionally retry once, and adapt quality.

        A successful retry lowers the next-frame quality to at most the retry
        quality; concurrent congestion is never undone. Ordinary encoder errors
        are not retried. The pipeline supplies the original frame deadline.

        @param image Owned RGB canvas.
        @param deadline_ns Absolute monotonic deadline, or None for direct encoding.
        @param frame_id Optional frame identifier for log correlation.
        @param capture_us Optional capture timestamp for log correlation.
        @return Validated complete JPEG within the configured receiver capacity.
        @throws TimeoutError If the frame expires before or during encoding.
        """
        with self.lock:
            quality = self.quality.value
        started = time.perf_counter_ns()
        fields = {"frame_id": frame_id, "capture_us": capture_us}
        retry = False

        def check_deadline():
            """@brief Avoid starting a retry or publishing an already expired result."""
            if deadline_ns is not None and time.perf_counter_ns() > deadline_ns:
                raise TimeoutError("Frame expired during JPEG encoding")

        try:
            check_deadline()
            try:
                jpeg = encode_receiver_jpeg(image, quality, self.max_jpeg_bytes)
            except JpegCapacityError as initial:
                with self.lock:
                    self.counts["oversize_initial"] += 1
                    self.quality.congested()
                    self.recovery_eligible = False
                    self._event(
                        "oversize_initial",
                        quality=quality,
                        bytes=initial.actual_bytes,
                        max_jpeg_bytes=self.max_jpeg_bytes,
                        **fields,
                    )
                retry_quality = max(self.quality.minimum, quality - self.jpeg_retry_quality_drop)
                if not self.jpeg_retry_quality_drop or retry_quality >= quality:
                    raise
                check_deadline()
                retry = True
                quality = retry_quality
                with self.lock:
                    self.counts["jpeg_retries"] += 1
                    self._event("jpeg_retry", quality=quality, **fields)
                jpeg = encode_receiver_jpeg(image, quality, self.max_jpeg_bytes)
                with self.lock:
                    self.quality.value = min(self.quality.value, quality)
                    self.quality.headroom_frames = 0
            check_deadline()
        except (OverflowError, OSError, ValueError) as error:
            with self.lock:
                if isinstance(error, JpegCapacityError):
                    self.counts["oversize_dropped"] += 1
                elif isinstance(error, TimeoutError):
                    self.counts["encode_expired"] += 1
                else:
                    self.quality.congested()
                if retry:
                    self.counts["jpeg_retry_failures"] += 1
                self.recovery_eligible = False
                self._event("encode_error", quality=quality, error=str(error), **fields)
            raise
        wire = len(jpeg) + ((len(jpeg) + 1023) // 1024) * VIDEO.size
        with self.lock:
            self.counts["encoded_bytes"] += len(jpeg)
            budget = self.rate / self.fps
            recent_feedback = (
                self.recovery_eligible
                and not self.gate.probing
                and self.gate.last_feedback is not None
                and time.perf_counter_ns() - self.gate.last_feedback <= self.gate.timeout_ns
            )
            self.quality.observe(wire, budget, recent_feedback)
            self._event(
                "encode",
                quality=quality,
                bytes=len(jpeg),
                encode_ms=(time.perf_counter_ns() - started) / 1e6,
                **fields,
            )
        return jpeg

    def _send(self, frame, jpeg):
        """@brief Send a paced frame and track only a bounded set of potential ACKs."""
        key = (frame.frame_id, frame.capture_us)
        queue_age_ms = (time.perf_counter_ns() - frame.encoded_ns) / 1e6
        with self.lock:
            was_probing = self.gate.probing
            allowed, clear_pending = self.gate.offer(key, time.perf_counter_ns())
            if not was_probing and self.gate.probing:
                self.recovery_eligible = False
                self._event("feedback_timeout")
            if clear_pending:
                self.counts["feedback_abandoned"] += len(self.pending)
                self.pending.clear()
            if not allowed:
                self.counts["feedback_suppressed"] += 1
                self._event("send_suppressed", frame_id=frame.frame_id, reason="feedback_silence")
                return False
            self.pending[key] = None
            while len(self.pending) > 512:
                self.pending.popitem(last=False)
                self.counts["feedback_evicted"] += 1
        records = []
        frame_deadline_ns = frame.captured_ns + self.age_ns

        def expire_and_check(now):
            """@brief Check the liveness epoch while holding the session lock."""
            if self.gate.expire(now):
                self.recovery_eligible = False
                self.counts["feedback_abandoned"] += len(self.pending)
                self.pending.clear()
                self._event("feedback_timeout")
            if not self.gate.permit_packet(key, now):
                raise _FeedbackSilenceStop("Feedback silence limit reached")

        class GuardedSocket:
            """@brief Atomically check silence and record successful nonblocking sends."""

            sent_bytes = 0

            def send(_, packet):
                """@brief Send one datagram unless its liveness epoch has expired."""
                with self.lock:
                    now = time.perf_counter_ns()
                    expire_and_check(now)
                    count = self.sock.send(packet)
                    if count == len(packet):
                        _.sent_bytes += count
                        self.gate.packet_sent(key, frame_deadline_ns, time.perf_counter_ns())
                    return count

        guarded_socket = GuardedSocket()

        def guarded_sleep(seconds):
            """@brief Break long pacing waits to observe feedback silence promptly."""
            time.sleep(min(seconds, 0.05))
            if seconds > 0.05:
                with self.lock:
                    expire_and_check(time.perf_counter_ns())

        def record(packet, sent_at):
            """@brief Retain only sent offsets and host times, bounded by frame size."""
            header = VIDEO.unpack_from(packet)
            records.append([header[8], header[9], sent_at])

        try:
            done, sent = send_frame(
                guarded_socket,
                jpeg,
                frame.frame_id,
                frame.capture_us,
                self.rate,
                frame_deadline_ns / 1e9,
                clock=lambda: time.perf_counter_ns() / 1e9,
                sleeper=guarded_sleep,
                pacer=self.pacer,
                on_packet=record if getattr(self, "packet_timing", False) else None,
            )
        except (OSError, ValueError) as error:
            with self.lock:
                self.pending.pop(key, None)
                if isinstance(error, PartialSendError):
                    self.counts["wire_bytes"] += error.sent_bytes
                    if error.sent_bytes:
                        self.gate.sent(time.perf_counter_ns())
                cause = error.original_error if isinstance(error, PartialSendError) else error
                if isinstance(cause, _FeedbackSilenceStop):
                    wire_bytes = (
                        error.sent_bytes
                        if isinstance(error, PartialSendError)
                        else guarded_socket.sent_bytes
                    )
                    if not isinstance(error, PartialSendError):
                        self.counts["wire_bytes"] += wire_bytes
                    self.counts["feedback_suppressed"] += 1
                    self.recovery_eligible = False
                    self._event(
                        "send",
                        frame_id=frame.frame_id,
                        capture_us=frame.capture_us,
                        jpeg_bytes=len(jpeg),
                        wire_bytes=wire_bytes,
                        complete=False,
                        queue_age_ms=queue_age_ms,
                        age_ms=(time.perf_counter_ns() - frame.captured_ns) / 1e6,
                    )
                    self._event(
                        "send_suppressed",
                        frame_id=frame.frame_id,
                        capture_us=frame.capture_us,
                        reason="feedback_silence",
                        wire_bytes=wire_bytes,
                    )
                    return False
                self.counts[
                    "socket_failures" if isinstance(error, OSError) else "packet_failures"
                ] += 1
                self.recovery_eligible = False
                self._event(
                    "send_error",
                    frame_id=frame.frame_id,
                    capture_us=frame.capture_us,
                    wire_bytes=error.sent_bytes if isinstance(error, PartialSendError) else 0,
                    error=str(error),
                )
            raise
        finally:
            with self.lock:
                self.gate.send_finished(key, time.perf_counter_ns())
                if records and not self._event(
                    "packet_timing",
                    frame_id=frame.frame_id,
                    capture_us=frame.capture_us,
                    packets=records,
                ):
                    self.counts["packet_timing_enqueue_dropped"] += 1
        with self.lock:
            self.counts["wire_bytes"] += sent
            if sent:
                self.gate.sent(time.perf_counter_ns())
            if not done:
                self.pending.pop(key, None)
                self.quality.congested()
                self.recovery_eligible = False
            self._event(
                "send",
                frame_id=frame.frame_id,
                capture_us=frame.capture_us,
                jpeg_bytes=len(jpeg),
                wire_bytes=sent,
                complete=done,
                queue_age_ms=queue_age_ms,
                age_ms=(time.perf_counter_ns() - frame.captured_ns) / 1e6,
            )
        return done

    def _feedback_loop(self):
        """@brief Poll the connected peer without blocking the video sender."""
        while not self.stop.is_set():
            with self.lock:
                if self.controller.expire(time.perf_counter_ns()) is not None:
                    self.counts["controller_timeout_releases"] += 1
                    self._event("controller", gamepad_flags=0, reason="timeout")
            try:
                data = self.sock.recv(FEEDBACK.size + 1)
            except BlockingIOError:
                self.stop.wait(0.005)
                continue
            except OSError as error:
                with self.lock:
                    self.counts["feedback_socket_failures"] += 1
                    self.recovery_eligible = False
                    self._event("feedback_error", error=str(error))
                    if self.controller.disconnect() is not None:
                        self._event("controller", gamepad_flags=0, reason="socket_error")
                return
            try:
                feedback = parse_feedback(data)
            except ValueError:
                with self.lock:
                    self.counts["invalid_feedback"] += 1
                continue
            key = (feedback.frame_id, feedback.capture_us)
            with self.lock:
                now = time.perf_counter_ns()
                if self.gate.expire(now):
                    self.recovery_eligible = False
                    self.counts["feedback_abandoned"] += len(self.pending)
                    self.pending.clear()
                    self._event("feedback_timeout")
                matched = key in self.pending
                was_probing = self.gate.probing
                if not self.gate.feedback(key, matched, now):
                    self.counts["unmatched_feedback"] += 1
                    continue
                if not hasattr(self, "receiver_counters"):
                    self.receiver_counters = ReceiverCounterTracker()
                counter_delta = self.receiver_counters.observe(
                    feedback.frame_id,
                    feedback.capture_us,
                    feedback.received_frames,
                    feedback.dropped_frames,
                )
                received_delta = dropped_delta = 0
                if counter_delta is not None:
                    received_delta = counter_delta["received_delta"]
                    dropped_delta = counter_delta["dropped_delta"]
                    if counter_delta["reset"]:
                        self.counts["receiver_counter_resets"] += 1
                    self.counts["receiver_completed_frames_since_baseline"] += received_delta
                    self.counts["receiver_dropped_frames_since_baseline"] += dropped_delta
                    if (
                        received_delta
                        or dropped_delta
                        or counter_delta["baseline"]
                        or counter_delta["reset"]
                    ):
                        self._event(
                            "receiver_counters",
                            frame_id=feedback.frame_id,
                            capture_us=feedback.capture_us,
                            received_frames=feedback.received_frames,
                            dropped_frames=feedback.dropped_frames,
                            received_delta=received_delta,
                            dropped_delta=dropped_delta,
                            reset=counter_delta["reset"],
                            baseline=counter_delta["baseline"],
                        )
                pressure_applied = self._apply_drop_delta(dropped_delta)
                if feedback.status:
                    self._apply_status_pressure(key, feedback.status, counter_delta)
                if was_probing:
                    self._event("feedback_restored", frame_id=feedback.frame_id)
                try:
                    buttons = self.controller.accept(
                        feedback.frame_id, feedback.capture_us, feedback.buttons, now
                    )
                except ValueError:
                    self.counts["invalid_buttons"] += 1
                else:
                    if buttons is not None:
                        self._event("controller", gamepad_flags=buttons, reason="feedback")
                if not matched:
                    self.counts["feedback_heartbeats"] += 1
                    self._event(
                        "heartbeat",
                        frame_id=feedback.frame_id,
                        capture_us=feedback.capture_us,
                        status=feedback.status,
                        received_frames=feedback.received_frames,
                        dropped_frames=feedback.dropped_frames,
                    )
                    if feedback.status:
                        self.recovery_eligible = False
                    continue
                del self.pending[key]
                self.counts[
                    "feedback_accepted" if feedback.status == 0 else "feedback_rejected"
                ] += 1
                if feedback.status:
                    self.recovery_eligible = False
                else:
                    self.recovery_eligible = not pressure_applied
                self._event(
                    "feedback",
                    frame_id=feedback.frame_id,
                    capture_us=feedback.capture_us,
                    status=feedback.status,
                    buttons=feedback.buttons,
                    free_bytes=feedback.free_bytes,
                    received_frames=feedback.received_frames,
                    dropped_frames=feedback.dropped_frames,
                )

    def _apply_drop_delta(self, dropped_delta):
        """@brief Lower quality for newly reported cumulative drops.

        @param dropped_delta Newly observed cumulative receiver drops.
        @return True when drop pressure was applied.
        """
        if dropped_delta <= 0:
            return False
        for _ in range(min(dropped_delta, (self.quality.value - self.quality.minimum + 4) // 5)):
            self.quality.congested()
        self.recovery_eligible = False
        return True

    def _apply_status_pressure(self, key, status, counter_delta):
        """@brief Use negative status only when it adds pressure beyond the drop counter.

        @param key Feedback frame ID and capture timestamp.
        @param status Receiver status code.
        @param counter_delta Accepted cumulative counter update, if any.
        """
        if not hasattr(self, "status_pressure_keys"):
            self.status_pressure_keys = OrderedDict()
        if key in self.status_pressure_keys:
            return
        self.status_pressure_keys[key] = None
        while len(self.status_pressure_keys) > 512:
            self.status_pressure_keys.popitem(last=False)

        # The pinned receiver reports status 1 after incrementing its cumulative
        # drop counter. Use it directly only to seed an otherwise unknown baseline.
        # Later status-1 packets with no counter delta may be duplicate errors for
        # the same dropped frame, even when a prior heartbeat carried that delta.
        if status == 1:
            if counter_delta is not None and counter_delta["baseline"]:
                self.quality.congested()
                self.recovery_eligible = False
            return

        # The pinned firmware does not emit status 2. For other defined negative
        # statuses, don't double count a simultaneous cumulative drop update.
        if counter_delta is None or counter_delta["dropped_delta"] == 0:
            self.quality.congested()
        self.recovery_eligible = False

    def close(self):
        """@brief Drain workers, allow a short ACK grace period and return a summary."""
        self.pipeline.close()
        self.stop.wait(0.3)
        self.stop.set()
        self.feedback_thread.join()
        duration = (time.perf_counter_ns() - self.start_ns) / 1e9
        with self.lock:
            if self.controller.disconnect() is not None:
                self._event("controller", gamepad_flags=0, reason="shutdown")
            result = {
                "scope": "MSV1 video test; feedback is ingress only",
                "end_to_end_verified": False,
                "duration_s": duration,
                "quality_final": self.quality.value,
                "counts": dict(self.counts),
                "pending_feedback": len(self.pending),
                "feedback_probing": self.gate.probing,
                "pipeline": self.pipeline.snapshot(),
            }
            result["wire_mbps"] = self.counts["wire_bytes"] * 8 / duration / 1e6
            result["encoded_mbps"] = self.counts["encoded_bytes"] * 8 / duration / 1e6
            result["encoded_fps"] = result["pipeline"]["counts"].get("encoded", 0) / duration
            result["sent_fps"] = result["pipeline"]["counts"].get("sent", 0) / duration
            self._event("summary", **result)
        result["logging"] = self.log.close()
        return result


def desktop_duplication_frames(fps):
    """@brief Yield Desktop Duplication frames, releasing the device on close.

    @param fps Maximum desktop output rate; unchanged frames may be repeated.
    @return Iterator of software BGRA video frames.
    """
    graph = f"ddagrab=framerate={fps}:dup_frames=1:draw_mouse=0,hwdownload,format=bgra"
    with av.open(graph, format="lavfi") as capture:
        yield from capture.decode(video=0)


def recovering_desktop_frames(fps, on_event, sleeper=time.sleep, clock=time.monotonic):
    """@brief Reopen a failed duplication graph with a bounded retry budget.

    @param fps Requested output rate for each new graph.
    @param on_event Receives structured capture errors and recovery events.
    @param sleeper Wait function used for bounded exponential backoff.
    @param clock Monotonic clock used to measure stable capture.
    @return Iterator of newly acquired frames; no previously returned frame is replayed here.
    @throws OSError If the graph ends unexpectedly or recovery attempts are exhausted.
    @throws av.FFmpegError If an FFmpeg error persists through the retry budget.

    Retry history resets when a frame arrives at least ten seconds after the
    last recovery without an intervening capture failure. This cannot interrupt
    a native graph open or decode call that blocks indefinitely.
    """
    failures = 0
    recovering = False
    stable_since = None
    while True:
        frames = desktop_duplication_frames(fps)
        try:
            while True:
                frame = next(frames)
                if recovering:
                    on_event("capture_restored", attempts=failures)
                    recovering = False
                    stable_since = clock()
                elif failures and clock() - stable_since >= 10:
                    on_event("capture_stable", attempts=failures)
                    failures = 0
                    stable_since = None
                yield frame
        except StopIteration:
            error = OSError("Desktop Duplication graph ended unexpectedly")
        except (OSError, av.FFmpegError) as exc:
            error = exc
        finally:
            frames.close()
        failures += 1
        stable_since = None
        retry = failures <= 3
        on_event("capture_error", attempt=failures, retry=retry, error=str(error))
        if not retry:
            raise error
        recovering = True
        sleeper(0.1 * 2 ** (failures - 1))


def run(args, source=None):
    """@brief Capture a paced clip or desktop and write bounded-queue telemetry.

    @param args Validated options, including explicit destination and log path.
    @param source Optional iterator of images for tests; None uses clip or desktop.
    @return Run summary without any claim of receiver decode or display.
    """
    shift_right_px = getattr(args, "shift_right_px", 0)
    if type(shift_right_px) is not int or not 0 <= shift_right_px < WIDTH:
        raise ValueError("Right shift must be an integer from 0 to 719 pixels")
    dxgi = (
        source is None
        and not args.clip
        and getattr(args, "desktop_backend", "imagegrab") == "ddagrab"
    )

    def capture_event(kind, **fields):
        """@brief Record capture recovery in the sender's bounded event log."""
        with session.lock:
            session._event(kind, **fields)

    frames = (
        source
        if source is not None
        else (
            clip_frames(args.clip, args.fps)
            if args.clip
            else recovering_desktop_frames(args.fps, capture_event)
            if dxgi
            else None
        )
    )
    with (
        args.log.open("x", encoding="utf-8", newline="\n") as log,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
    ):
        sock.bind(("0.0.0.0", getattr(args, "source_port", 0)))
        sock.connect((args.target, args.port))
        sock.setblocking(False)
        session = Session(
            sock,
            log,
            args.fps,
            args.mbps,
            args.max_age_ms,
            args.quality,
            args.min_quality,
            packet_timing=getattr(args, "packet_timing", False),
            max_jpeg_bytes=getattr(args, "max_jpeg_bytes", MAX_FRAME),
            jpeg_retry_quality_drop=getattr(args, "jpeg_retry_quality_drop", 0),
        )
        filter_name = getattr(args, "desktop_filter", "bilinear")
        with session.lock:
            session._event(
                "capture_config",
                source="desktop_ddagrab"
                if dxgi
                else "desktop"
                if frames is None
                else "clip_or_test_source",
                desktop_filter=filter_name if frames is None else None,
            )
            session._event(
                "session_config",
                fps=args.fps,
                cap_mbps=args.mbps,
                max_age_ms=args.max_age_ms,
                initial_quality=args.quality,
                min_quality=args.min_quality,
                frames_target=args.frames,
                source_backend="provided_iterator"
                if source is not None
                else "clip"
                if args.clip
                else "desktop_ddagrab"
                if dxgi
                else "desktop_imagegrab",
                start_frame_id=getattr(args, "start_frame_id", 0),
                packet_timing=bool(getattr(args, "packet_timing", False)),
                max_jpeg_bytes=session.max_jpeg_bytes,
                jpeg_retry_quality_drop=session.jpeg_retry_quality_drop,
                shift_right_px=shift_right_px,
            )
        started = time.perf_counter_ns()
        slot = 0
        try:
            while slot < args.frames:
                due = started + slot * 1_000_000_000 // args.fps
                time.sleep(max(0, (due - time.perf_counter_ns()) / 1e9))
                now = time.perf_counter_ns()
                actual = min(args.frames - 1, (now - started) * args.fps // 1_000_000_000)
                skipped = max(0, actual - slot)
                if frames is not None:
                    for _ in range(1 if dxgi else skipped + 1):
                        image = next(frames)
                else:
                    image = ImageGrab.grab()
                now = time.perf_counter_ns()
                if dxgi:
                    # Startup can be slow; schedule from the first acquired frame.
                    # Later stalls must consume elapsed slots, never replay old IDs.
                    if slot == 0:
                        started = now
                        skipped = 0
                    else:
                        actual = (now - started) * args.fps // 1_000_000_000
                        if actual >= args.frames:
                            with session.lock:
                                session.counts["skipped_slots"] += args.frames - slot
                            break
                        skipped = max(skipped, actual - slot)
                slot += skipped
                stamp_us = time.time_ns() // 1000
                prepared = canvas(image, Image.Resampling[filter_name.upper()])
                if shift_right_px:
                    prepared = shift_canvas_right(prepared, shift_right_px)
                frame_id = (getattr(args, "start_frame_id", 0) + slot) & 0xFFFFFFFF
                session.pipeline.submit(Frame(frame_id, now, stamp_us, prepared))
                with session.lock:
                    session.counts["skipped_slots"] += skipped
                slot += 1
        except StopIteration:
            pass
        finally:
            try:
                if hasattr(frames, "close"):
                    frames.close()
            finally:
                result = session.close()
    return result


def main(argv=None):
    """@brief Parse sender options and run only against the explicitly selected peer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Receiver address on the trusted test LAN")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--clip", type=Path)
    group.add_argument("--desktop", action="store_true")
    parser.add_argument(
        "--desktop-backend",
        choices=("imagegrab", "ddagrab"),
        default="imagegrab",
        help="Experimental Windows Desktop Duplication via FFmpeg; may repeat unchanged frames",
    )
    parser.add_argument(
        "--desktop-filter",
        choices=("bilinear", "box"),
        default="bilinear",
        help="Experimental desktop scaling filter; clip video uses libswscale bilinear",
    )
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument(
        "--packet-timing",
        action="store_true",
        help="Record bounded per-frame datagram send timing in the JSONL log",
    )
    parser.add_argument("--port", type=int, default=5533)
    parser.add_argument(
        "--source-port", type=int, default=0, help="Local UDP port; 0 chooses an ephemeral port"
    )
    parser.add_argument(
        "--start-frame-id", type=int, default=0, help="First unsigned 32-bit frame ID"
    )
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--mbps", type=float, default=20)
    parser.add_argument("--max-age-ms", type=float, default=200)
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--min-quality", type=int, default=20)
    parser.add_argument(
        "--shift-right-px",
        type=int,
        default=0,
        help="Shift content inside 720x480: black left columns and cropped right edge (0..719)",
    )
    parser.add_argument(
        "--max-jpeg-bytes",
        type=int,
        default=MAX_FRAME,
        help="Maximum complete JPEG bytes; must match receiver capacity",
    )
    parser.add_argument(
        "--jpeg-retry-quality-drop",
        type=int,
        default=0,
        help="Retry an oversized JPEG once at lower quality; 0 disables",
    )
    args = parser.parse_args(argv)
    if args.desktop_backend != "imagegrab" and not args.desktop:
        parser.error("--desktop-backend requires --desktop")
    if (
        not 1 <= args.port <= 65535
        or not 0 <= args.source_port <= 65535
        or not 0 <= args.start_frame_id <= 0xFFFFFFFF
        or not 1 <= args.frames <= 108000
        or not 1 <= args.fps <= 30
        or not 1 <= args.min_quality <= args.quality <= 95
        or not 0 <= args.shift_right_px < WIDTH
        or not 1 <= args.max_jpeg_bytes <= MAX_FRAME
        or not 0 <= args.jpeg_retry_quality_drop <= 94
        or any(not math.isfinite(v) or v <= 0 for v in (args.mbps, args.max_age_ms))
    ):
        parser.error("Invalid port, frame count, fps, quality, bitrate or deadline")
    try:
        result = run(args)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, av.FFmpegError) as error:
        parser.error(str(error))
    return 0 if result["counts"].get("feedback_accepted", 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
