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

from PIL import Image, ImageGrab

from host import Profile, canvas, clip_frames, encode
from msv1 import FEEDBACK, MAX_FRAME, VIDEO, Pacer, parse_feedback, send_frame
from pipeline import Frame, VideoPipeline


class Session:
    """@brief Bounded experimental JPEG sender and peer feedback collector."""

    def __init__(self, sock, log, fps, mbps, max_age_ms, quality, min_quality):
        """@brief Configure a connected nonblocking UDP socket and per-run log.

        @param sock Connected nonblocking datagram socket for the test peer.
        @param log Open text file for JSONL events.
        @param fps Target capture rate in frames per second.
        @param mbps Maximum MSV1 datagram bitrate, excluding lower-layer overhead.
        @param max_age_ms Capture-to-send deadline in milliseconds.
        @param quality Initial and maximum JPEG quality.
        @param min_quality Minimum adaptation quality.
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
        self.sock, self.log, self.fps = sock, log, fps
        self.rate = mbps * 1e6 / 8
        self.age_ns = int(max_age_ms * 1e6)
        self.quality, self.max_quality, self.min_quality = quality, quality, min_quality
        self.lock = threading.Lock()
        self.pending = OrderedDict()
        self.counts = Counter()
        self.stop = threading.Event()
        self.pacer = Pacer()
        self.start_ns = time.monotonic_ns()
        self.feedback_thread = threading.Thread(target=self._feedback_loop, name="gamebub-feedback")
        self.feedback_thread.start()
        self.pipeline = VideoPipeline(self._encode, self._send, self.age_ns, MAX_FRAME)

    def _event(self, kind, **fields):
        """@brief Serialize one event under the session lock."""
        self.log.write(json.dumps({"event": kind, **fields}) + "\n")
        self.log.flush()

    def _encode(self, image):
        """@brief Encode a frame and slowly adapt quality to the per-frame wire budget."""
        with self.lock:
            quality = self.quality
        started = time.monotonic_ns()
        try:
            jpeg, _ = encode(image, quality, Profile(huffman_sha256=None))
        except (OverflowError, OSError, ValueError) as error:
            with self.lock:
                self.quality = max(self.min_quality, self.quality - 5)
                self._event("encode_error", quality=quality, error=str(error))
            raise
        wire = len(jpeg) + ((len(jpeg) + 1023) // 1024) * VIDEO.size
        with self.lock:
            self.counts["encoded_bytes"] += len(jpeg)
            budget = self.rate / self.fps
            if wire > budget * 0.9:
                self.quality = max(self.min_quality, self.quality - 5)
            elif wire < budget * 0.7:
                self.quality = min(self.max_quality, self.quality + 1)
            self._event(
                "encode",
                quality=quality,
                bytes=len(jpeg),
                encode_ms=(time.monotonic_ns() - started) / 1e6,
            )
        return jpeg

    def _send(self, frame, jpeg):
        """@brief Send a paced frame and track only a bounded set of potential ACKs."""
        key = (frame.frame_id, frame.capture_us)
        queue_age_ms = (time.monotonic_ns() - frame.encoded_ns) / 1e6
        with self.lock:
            self.pending[key] = None
            while len(self.pending) > 512:
                self.pending.popitem(last=False)
                self.counts["feedback_evicted"] += 1
        try:
            done, sent = send_frame(
                self.sock,
                jpeg,
                frame.frame_id,
                frame.capture_us,
                self.rate,
                (frame.captured_ns + self.age_ns) / 1e9,
                clock=lambda: time.monotonic_ns() / 1e9,
                pacer=self.pacer,
            )
        except OSError:
            with self.lock:
                self.pending.pop(key, None)
                self.counts["socket_failures"] += 1
            raise
        with self.lock:
            self.counts["wire_bytes"] += sent
            if not done:
                self.pending.pop(key, None)
                self.quality = max(self.min_quality, self.quality - 5)
            self._event(
                "send",
                frame_id=frame.frame_id,
                capture_us=frame.capture_us,
                jpeg_bytes=len(jpeg),
                wire_bytes=sent,
                complete=done,
                queue_age_ms=queue_age_ms,
                age_ms=(time.monotonic_ns() - frame.captured_ns) / 1e6,
            )
        return done

    def _feedback_loop(self):
        """@brief Poll the connected peer without blocking the video sender."""
        while not self.stop.is_set():
            try:
                data = self.sock.recv(FEEDBACK.size + 1)
            except BlockingIOError:
                self.stop.wait(0.005)
                continue
            except OSError as error:
                with self.lock:
                    self.counts["feedback_socket_failures"] += 1
                    self._event("feedback_error", error=str(error))
                return
            try:
                feedback = parse_feedback(data)
            except ValueError:
                with self.lock:
                    self.counts["invalid_feedback"] += 1
                continue
            key = (feedback.frame_id, feedback.capture_us)
            with self.lock:
                if key not in self.pending:
                    self.counts["unmatched_feedback"] += 1
                    continue
                del self.pending[key]
                self.counts[
                    "feedback_accepted" if feedback.status == 0 else "feedback_rejected"
                ] += 1
                if feedback.status:
                    self.quality = max(self.min_quality, self.quality - 5)
                self._event(
                    "feedback",
                    frame_id=feedback.frame_id,
                    capture_us=feedback.capture_us,
                    status=feedback.status,
                    buttons=feedback.buttons,
                    free_bytes=feedback.free_bytes,
                )

    def close(self):
        """@brief Drain workers, allow a short ACK grace period and return a summary."""
        self.pipeline.close()
        self.stop.wait(0.3)
        self.stop.set()
        self.feedback_thread.join()
        duration = (time.monotonic_ns() - self.start_ns) / 1e9
        with self.lock:
            result = {
                "scope": "MSV1 video test; feedback is ingress only",
                "end_to_end_verified": False,
                "duration_s": duration,
                "quality_final": self.quality,
                "counts": dict(self.counts),
                "pending_feedback": len(self.pending),
                "pipeline": self.pipeline.snapshot(),
            }
            result["wire_mbps"] = self.counts["wire_bytes"] * 8 / duration / 1e6
            result["encoded_mbps"] = self.counts["encoded_bytes"] * 8 / duration / 1e6
            result["encoded_fps"] = result["pipeline"]["counts"].get("encoded", 0) / duration
            result["sent_fps"] = result["pipeline"]["counts"].get("sent", 0) / duration
            self._event("summary", **result)
            return result


def run(args, source=None):
    """@brief Capture a paced clip or desktop and write bounded-queue telemetry.

    @param args Validated options, including explicit destination and log path.
    @param source Optional iterator of images for tests; None uses clip or desktop.
    @return Run summary without any claim of receiver decode or display.
    """
    frames = (
        source if source is not None else (clip_frames(args.clip, args.fps) if args.clip else None)
    )
    with (
        args.log.open("x", encoding="utf-8") as log,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
    ):
        sock.connect((args.target, args.port))
        sock.setblocking(False)
        session = Session(
            sock, log, args.fps, args.mbps, args.max_age_ms, args.quality, args.min_quality
        )
        started = time.monotonic_ns()
        slot = 0
        try:
            while slot < args.frames:
                due = started + slot * 1_000_000_000 // args.fps
                time.sleep(max(0, (due - time.monotonic_ns()) / 1e9))
                now = time.monotonic_ns()
                actual = min(args.frames - 1, (now - started) * args.fps // 1_000_000_000)
                skipped = max(0, actual - slot)
                if frames is not None:
                    for _ in range(skipped + 1):
                        image = next(frames)
                else:
                    image = ImageGrab.grab()
                slot += skipped
                stamp_us = time.time_ns() // 1000
                prepared = canvas(image, Image.Resampling.BILINEAR)
                session.pipeline.submit(Frame(slot & 0xFFFFFFFF, now, stamp_us, prepared))
                with session.lock:
                    session.counts["skipped_slots"] += skipped
                slot += 1
        except StopIteration:
            pass
        finally:
            if hasattr(frames, "close"):
                frames.close()
            result = session.close()
    return result


def main(argv=None):
    """@brief Parse sender options and run only against the explicitly selected peer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Receiver address on the trusted test LAN")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--clip", type=Path)
    group.add_argument("--desktop", action="store_true")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--port", type=int, default=5533)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--mbps", type=float, default=20)
    parser.add_argument("--max-age-ms", type=float, default=200)
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--min-quality", type=int, default=20)
    args = parser.parse_args(argv)
    if (
        not 1 <= args.port <= 65535
        or not 1 <= args.frames <= 108000
        or not 1 <= args.fps <= 30
        or not 1 <= args.min_quality <= args.quality <= 95
        or any(not math.isfinite(v) or v <= 0 for v in (args.mbps, args.max_age_ms))
    ):
        parser.error("Invalid port, frame count, fps, quality, bitrate or deadline")
    try:
        result = run(args)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0 if result["counts"].get("feedback_accepted", 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
