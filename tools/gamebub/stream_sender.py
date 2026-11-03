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
from host import canvas, clip_frames
from msv1 import FEEDBACK, MAX_FRAME, VIDEO, Pacer, encode_receiver_jpeg, parse_feedback, send_frame
from pipeline import Frame, VideoPipeline
from quality import QualityController


class FeedbackGate:
    """@brief Limit sends during feedback silence while retaining recovery probes.

    Only matching feedback from the current session confirms liveness. Once
    silence exceeds the deadline, only feedback for a newly sent probe can
    resume normal sending; old ACKs and heartbeats cannot revive the session.
    """

    def __init__(self, now_ns, timeout_ns=750_000_000, probe_ns=1_000_000_000):
        """@brief Set fixed monotonic durations; None defers the initial grace period.

        @param now_ns Initial grace timestamp, or None to defer it until traffic is sent.
        @param timeout_ns Maximum feedback silence before probing.
        @param probe_ns Minimum interval between recovery probes.
        """
        if timeout_ns <= 0 or probe_ns <= 0:
            raise ValueError("Feedback timing must be positive")
        self.last_feedback = now_ns
        self.timeout_ns, self.probe_ns = timeout_ns, probe_ns
        self.probing = False
        self.next_probe = now_ns
        self.probe_key = None
        self.heartbeat_key = None

    def expire(self, now_ns):
        """@brief Enter probing once and indicate when old pending ACKs must be cleared."""
        if (
            self.last_feedback is not None
            and not self.probing
            and now_ns - self.last_feedback > self.timeout_ns
        ):
            self.probing = True
            self.next_probe = now_ns
            self.probe_key = None
            self.heartbeat_key = None
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
        return True, True

    def sent(self, now_ns):
        """@brief Arm initial grace after transmission, preserving any earlier feedback.

        @param now_ns Monotonic time after a send which transmitted at least one byte.
        """
        if self.last_feedback is None:
            self.last_feedback = now_ns

    def feedback(self, key, matched, now_ns):
        """@brief Process a matching ACK or current heartbeat and report liveness."""
        if self.probing:
            if not matched or key != self.probe_key:
                return False
            self.probing = False
            self.probe_key = None
        elif not matched and key != self.heartbeat_key:
            return False
        self.last_feedback = now_ns
        self.heartbeat_key = key
        return True


class Session:
    """@brief Bounded experimental JPEG sender and peer feedback collector."""

    def __init__(self, sock, log, fps, mbps, max_age_ms, quality, min_quality, packet_timing=False):
        """@brief Configure a connected nonblocking UDP socket and per-run log.

        @param sock Connected nonblocking datagram socket for the test peer.
        @param log Open text file for JSONL events.
        @param fps Target capture rate in frames per second.
        @param mbps Maximum MSV1 datagram bitrate, excluding lower-layer overhead.
        @param max_age_ms Capture-to-send deadline in milliseconds.
        @param quality Initial and maximum JPEG quality.
        @param min_quality Minimum adaptation quality.
        @param packet_timing Record per-datagram timing in the bounded event log.
        """
        if (
            type(fps) is not int
            or not 1 <= fps <= 30
            or not math.isfinite(mbps)
            or mbps <= 0
            or not math.isfinite(max_age_ms)
            or max_age_ms < 0.000001
            or not 1 <= min_quality <= quality <= 95
        ):
            raise ValueError("Invalid session rate, deadline or quality")
        self.sock, self.log, self.fps = sock, EventLog(log), fps
        self.packet_timing = packet_timing
        self.rate = mbps * 1e6 / 8
        self.age_ns = int(max_age_ms * 1e6)
        self.quality = QualityController(quality, min_quality)
        self.recovery_eligible = False
        self.lock = threading.Lock()
        self.pending = OrderedDict()
        self.counts = Counter()
        self.stop = threading.Event()
        self.pacer = Pacer()
        self.start_ns = time.perf_counter_ns()
        # Capture startup and a paced first frame can be slower than the liveness timeout.
        self.gate = FeedbackGate(None)
        self.controller = ControllerTracker()
        self.feedback_thread = threading.Thread(target=self._feedback_loop, name="gamebub-feedback")
        self.feedback_thread.start()
        self.pipeline = VideoPipeline(self._encode, self._send, self.age_ns, MAX_FRAME)

    def _event(self, kind, **fields):
        """@brief Serialize one event under the session lock and return enqueue status."""
        return self.log.submit({"event": kind, **fields})

    def _encode(self, image):
        """@brief Encode a frame and slowly adapt quality to the per-frame wire budget."""
        with self.lock:
            quality = self.quality.value
        started = time.perf_counter_ns()
        try:
            jpeg = encode_receiver_jpeg(image, quality)
        except (OverflowError, OSError, ValueError) as error:
            with self.lock:
                self.quality.congested()
                self.recovery_eligible = False
                self._event("encode_error", quality=quality, error=str(error))
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

        def record(packet, sent_at):
            """@brief Retain only sent offsets and host times, bounded by frame size."""
            header = VIDEO.unpack_from(packet)
            records.append([header[8], header[9], sent_at])

        try:
            done, sent = send_frame(
                self.sock,
                jpeg,
                frame.frame_id,
                frame.capture_us,
                self.rate,
                (frame.captured_ns + self.age_ns) / 1e9,
                clock=lambda: time.perf_counter_ns() / 1e9,
                pacer=self.pacer,
                on_packet=record if getattr(self, "packet_timing", False) else None,
            )
        except (OSError, ValueError) as error:
            with self.lock:
                self.pending.pop(key, None)
                self.counts[
                    "socket_failures" if isinstance(error, OSError) else "packet_failures"
                ] += 1
                self.recovery_eligible = False
                self._event(
                    "send_error",
                    frame_id=frame.frame_id,
                    capture_us=frame.capture_us,
                    error=str(error),
                )
            raise
        finally:
            if records:
                with self.lock:
                    if not self._event(
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
                    continue
                del self.pending[key]
                self.counts[
                    "feedback_accepted" if feedback.status == 0 else "feedback_rejected"
                ] += 1
                if feedback.status:
                    self.quality.congested()
                    self.recovery_eligible = False
                else:
                    self.recovery_eligible = True
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
