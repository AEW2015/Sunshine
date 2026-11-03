"""Tests for optional normalized sender frame telemetry."""

import threading
import io
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from frame_telemetry import FrameTelemetry
from pipeline import Frame, VideoPipeline
from stream_sender import Session, run


class MemorySink:
    def __init__(self):
        self.events = []

    def submit(self, event):
        self.events.append(dict(event))
        return True


class FrameTelemetryTests(unittest.TestCase):
    def test_wall_time_is_metadata_and_monotonic_stages_remain_separate(self):
        sink = MemorySink()
        telemetry = FrameTelemetry(sink, "session-one", "hardware")
        frame = Frame(
            0xFFFFFFFF, 1_000_000_000, 1_800_000_000_000_000,
            Image.new("RGB", (720, 480)), frame_seq=17,
            capture_end_ns=1_015_000_000,
        )
        self.assertTrue(telemetry.capture(frame, frame.capture_us))
        self.assertTrue(telemetry.send_complete(frame, 1_040_000_000, 12345))
        capture, send = sink.events
        self.assertEqual(capture["clock_domain"], "host_monotonic")
        self.assertEqual(capture["timestamp_ns"], 1_000_000_000)
        self.assertEqual(capture["capture_start_ns"], 1_000_000_000)
        self.assertEqual(capture["capture_end_ns"], 1_015_000_000)
        self.assertEqual(capture["capture_wall_us"], 1_800_000_000_000_000)
        self.assertEqual(send["timestamp_ns"], 1_040_000_000)
        self.assertEqual(send["send_complete_ns"], 1_040_000_000)
        self.assertEqual(send["frame_seq"], 17)
        self.assertEqual(send["frame_id"], 0xFFFFFFFF)
        self.assertEqual(send["evidence_kind"], "hardware")
        self.assertNotIn("presented", {event["stage"] for event in sink.events})
        self.assertNotIn("ingress", {event["stage"] for event in sink.events})

    def test_invalid_clock_domains_or_frame_identity_are_rejected(self):
        with self.assertRaises(ValueError):
            FrameTelemetry(MemorySink(), "", "simulated")
        with self.assertRaises(ValueError):
            FrameTelemetry(MemorySink(), "session", "unknown")
        telemetry = FrameTelemetry(MemorySink(), "session")
        frame = Frame(4, 100, 200, Image.new("RGB", (720, 480)), frame_seq=None,
                      capture_end_ns=110)
        with self.assertRaises(ValueError):
            telemetry.capture(frame, 200)

    def test_wall_timestamp_must_be_kept_separate_and_consistent(self):
        telemetry = FrameTelemetry(MemorySink(), "session")
        frame = Frame(9, 10, 20, Image.new("RGB", (720, 480)), frame_seq=0,
                      capture_end_ns=15)
        with self.assertRaisesRegex(ValueError, "wire timestamp"):
            telemetry.capture(frame, frame.captured_ns)

    def test_invalid_rate_session_or_evidence_starts_no_logger_workers(self):
        settings = (None, io.StringIO(), 30, 20.0, 200.0, 75, 20)
        telemetry_output = io.StringIO()
        invalid_options = (
            {"telemetry_session_id": "", "telemetry_evidence_kind": "simulated"},
            {"telemetry_session_id": "run", "telemetry_evidence_kind": "unknown"},
            {"fps": 0, "telemetry_session_id": "run", "telemetry_evidence_kind": "hardware"},
        )
        for options in invalid_options:
            with self.subTest(options=options), patch("stream_sender.EventLog") as logger:
                arguments = dict(options)
                fps = arguments.pop("fps", 30)
                with self.assertRaises(ValueError):
                    Session(*settings[:2], fps, *settings[3:],
                            frame_telemetry_output=telemetry_output, **arguments)
                logger.assert_not_called()

    def test_run_rejects_invalid_telemetry_before_opening_files_or_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                log=Path(directory) / "events.jsonl",
                frame_telemetry=Path(directory) / "frames.jsonl",
                telemetry_session_id="coordinated-run",
                telemetry_evidence_kind="simulated",
                target="127.0.0.1", port=5533, fps=0, mbps=20.0,
                max_age_ms=200.0, quality=75, min_quality=20,
            )
            with patch("stream_sender.EventLog") as logger:
                with self.assertRaises(ValueError):
                    run(args, iter(()))
                logger.assert_not_called()
            self.assertFalse(args.log.exists())
            self.assertFalse(args.frame_telemetry.exists())

    def test_telemetry_sender_test_process_exits_after_success(self):
        test_dir = Path(__file__).resolve().parent
        completed = subprocess.run(
            [
                sys.executable, "-m", "unittest", "-q",
                "test_stream_sender.StreamSenderTests.test_loopback_frames_and_feedback",
            ],
            cwd=test_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_skipped_wire_ids_and_replaced_captures_remain_observable(self):
        sink = MemorySink()
        telemetry = FrameTelemetry(sink, "replacement-session", "simulated")
        encode_entered, release_encode = threading.Event(), threading.Event()
        first_send_done = threading.Event()
        encoded = 0
        sent = []

        def encode(_image):
            nonlocal encoded
            encoded += 1
            if encoded == 1:
                encode_entered.set()
                if not release_encode.wait(5):
                    raise TimeoutError("test failed to release encoder")
            elif encoded == 2 and not first_send_done.wait(5):
                raise TimeoutError("sender did not consume first encoded frame")
            return b"jpeg"

        def send(frame, _payload):
            sent.append((frame.frame_seq, frame.frame_id))
            telemetry.send_complete(frame, time.perf_counter_ns(), 4)
            first_send_done.set()
            return True

        pipeline = VideoPipeline(encode, send, 10_000_000_000, 1024)
        try:
            image = Image.new("RGB", (720, 480))
            # Wire IDs 101 and 103 are skipped scheduler slots. Captured seq 1
            # is replaced in the one-deep raw slot by captured seq 2.
            frames = []
            for sequence, frame_id in enumerate((100, 102, 104)):
                capture_start = time.perf_counter_ns()
                frames.append(Frame(
                    frame_id, capture_start, 1_000 + sequence, image,
                    frame_seq=sequence, capture_end_ns=capture_start,
                ))
            for frame in frames:
                telemetry.capture(frame, frame.capture_us)
                self.assertTrue(pipeline.submit(frame))
                if frame.frame_seq == 0:
                    self.assertTrue(encode_entered.wait(5))
            release_encode.set()
            with pipeline.condition:
                completed = pipeline.condition.wait_for(
                    lambda: pipeline.counts["sent"] == 2, timeout=5
                )
                self.assertTrue(completed, pipeline.snapshot())
        finally:
            release_encode.set()
            pipeline.close()

        capture_events = [event for event in sink.events if event["stage"] == "capture"]
        send_events = [event for event in sink.events if event["stage"] == "send"]
        self.assertEqual([(e["frame_seq"], e["frame_id"]) for e in capture_events],
                         [(0, 100), (1, 102), (2, 104)])
        self.assertEqual([(e["frame_seq"], e["frame_id"]) for e in send_events],
                         [(0, 100), (2, 104)])
        self.assertEqual(sent, [(0, 100), (2, 104)])
        self.assertEqual(pipeline.snapshot()["counts"]["raw_replaced"], 1)


if __name__ == "__main__":
    unittest.main()
