"""@brief Capacity, deadline and real-bitstream regressions for the JPEG sender."""

import io
import json
import random
import socket
import tempfile
import threading
import time
import unittest
import zlib
from collections import Counter
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from msv1 import MAX_FRAME, VIDEO, JpegCapacityError, encode_receiver_jpeg, validate_receiver_jpeg
from pipeline import Frame, VideoPipeline
from quality import QualityController
from stream_sender import FeedbackGate, Session, main, run


class JpegRetryTests(unittest.TestCase):
    """@brief Retry size failures once without relaxing final JPEG or age limits."""

    def session(self, quality=95, minimum=20, capacity=MAX_FRAME, drop=20):
        """@brief Construct only the encoder state without background threads or sockets."""
        session = Session.__new__(Session)
        session.lock = threading.Lock()
        session.log = Mock()
        session.max_jpeg_bytes, session.jpeg_retry_quality_drop = capacity, drop
        session.quality = QualityController(quality, minimum)
        session.rate, session.fps, session.age_ns = 100_000_000, 30, 100
        session.recovery_eligible = True
        session.gate = FeedbackGate(None)
        session.counts = Counter()
        return session

    def test_real_oversize_retries_and_loopback_receives_valid_crc(self):
        """@brief An initial JPEG above MAX_FRAME is rescued and packetized whole."""
        image = Image.frombytes("RGB", (720, 480), random.Random(42).randbytes(720 * 480 * 3))
        session = self.session()
        jpeg = session._encode(image, frame_id=71, capture_us=123)
        validate_receiver_jpeg(jpeg)
        self.assertEqual(jpeg, encode_receiver_jpeg(image, 75))
        self.assertEqual(session.counts["jpeg_retries"], 1)
        self.assertEqual(session.quality.value, 75)
        events = [call.args[0] for call in session.log.submit.call_args_list]
        self.assertGreater(events[0]["bytes"], MAX_FRAME)
        self.assertTrue(all(event["frame_id"] == 71 for event in events))

        # Use the real bounded pipeline and sender, not mocked JPEG packet bytes.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1_048_576)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.connect(receiver.getsockname())
                sender.setblocking(False)
                log = io.StringIO()
                live = Session(sender, log, 1, 10, 3000, 95, 20, jpeg_retry_quality_drop=20)
                try:
                    live.pipeline.submit(Frame(72, time.perf_counter_ns(), 456, image))
                    assembled = bytearray()
                    while len(assembled) < len(jpeg):
                        packet = receiver.recv(2048)
                        header = VIDEO.unpack_from(packet)
                        self.assertEqual(
                            (header[4], header[7], header[8]), (72, len(jpeg), len(assembled))
                        )
                        self.assertEqual(header[11], zlib.crc32(jpeg) & 0xFFFFFFFF)
                        assembled.extend(packet[VIDEO.size :])
                    self.assertEqual(bytes(assembled), jpeg)
                finally:
                    result = live.close()
                self.assertEqual(result["pipeline"]["counts"].get("sent"), 1)
                self.assertEqual(result["counts"].get("jpeg_retries"), 1)
                self.assertTrue(
                    any(
                        json.loads(line)["event"] == "encode"
                        for line in log.getvalue().splitlines()
                    )
                )

    def test_size_rejection_disabled_minimum_and_failed_retry(self):
        """@brief Capacity failures never escape as truncated or partly valid output."""
        for quality, minimum, drop, errors, calls in (
            (95, 20, 0, [JpegCapacityError(300000, MAX_FRAME)], 1),
            (20, 20, 20, [JpegCapacityError(300000, MAX_FRAME)], 1),
            (
                95,
                20,
                20,
                [JpegCapacityError(300000, MAX_FRAME), JpegCapacityError(270000, MAX_FRAME)],
                2,
            ),
        ):
            with self.subTest(quality=quality, drop=drop):
                session = self.session(quality, minimum, drop=drop)
                with (
                    patch("stream_sender.encode_receiver_jpeg", side_effect=errors) as encode,
                    self.assertRaises(JpegCapacityError),
                ):
                    session._encode(None)
                self.assertEqual(encode.call_count, calls)
                self.assertEqual(session.counts["oversize_dropped"], 1)
                self.assertEqual(session.counts["encoded_bytes"], 0)
                self.assertEqual(session.counts["jpeg_retry_failures"], calls - 1)

    def test_invalid_jpeg_and_retry_encoder_failure_are_not_size_retries(self):
        """@brief Only explicit capacity rejection enables the lower-quality attempt."""
        for errors, calls in (
            ([ValueError("bad JPEG")], 1),
            ([JpegCapacityError(300000, MAX_FRAME), OSError("encoder")], 2),
        ):
            session = self.session()
            with (
                patch("stream_sender.encode_receiver_jpeg", side_effect=errors) as encode,
                self.assertRaises((OSError, ValueError)),
            ):
                session._encode(None)
            self.assertEqual(encode.call_count, calls)
            self.assertEqual(session.counts["jpeg_retry_failures"], calls - 1)
            self.assertEqual(session.counts["oversize_dropped"], 0)

    def test_deadlines_before_encode_before_retry_and_after_retry(self):
        """@brief Controlled clock expiry stops work and never invokes the sender."""
        for expiry, calls in (("before", 0), ("retry", 1), ("after", 2), ("single", 1)):
            with self.subTest(expiry=expiry):
                now = [101 if expiry == "before" else 0]
                session = self.session()

                def encode(*args, expiry=expiry, now=now):
                    """@brief Advance the clock at the selected encoder boundary."""
                    if encode_mock.call_count == 1 and expiry != "single":
                        now[0] = 101 if expiry == "retry" else 1
                        raise JpegCapacityError(300000, MAX_FRAME)
                    now[0] = 101
                    return b"jpeg"

                with (
                    patch("stream_sender.time.perf_counter_ns", side_effect=lambda now=now: now[0]),
                    patch("stream_sender.encode_receiver_jpeg", side_effect=encode) as encode_mock,
                    self.assertRaises(TimeoutError),
                ):
                    session._encode_frame(Frame(9, 0, 99, Image.new("RGB", (720, 480))))
                self.assertEqual(encode_mock.call_count, calls)
                self.assertEqual(session.counts["encode_expired"], 1)
                self.assertEqual(session.counts["encoded_bytes"], 0)

        session = self.session()
        send = Mock()
        with patch("stream_sender.encode_receiver_jpeg", side_effect=TimeoutError("expired")):
            pipeline = VideoPipeline(
                session._encode,
                send,
                100,
                MAX_FRAME,
                clock=lambda: 0,
                encode_frame=session._encode_frame,
            )
            try:
                pipeline.submit(Frame(1, 0, 1, Image.new("RGB", (720, 480))))
            finally:
                pipeline.close()
        send.assert_not_called()
        self.assertEqual(pipeline.snapshot()["counts"]["encode_failures"], 1)

    def test_retry_does_not_undo_concurrent_quality_pressure(self):
        """@brief Successful retries retain a more conservative concurrent quality."""
        session = self.session()

        def encode(*args):
            """@brief Simulate feedback lowering quality during the retry."""
            if encode_mock.call_count == 1:
                raise JpegCapacityError(300000, MAX_FRAME)
            session.quality.value = 50
            return b"jpeg"

        with patch("stream_sender.encode_receiver_jpeg", side_effect=encode) as encode_mock:
            session._encode(None)
        self.assertEqual(session.quality.value, 50)

    def test_configuration_rejects_invalid_capacity_and_retry(self):
        """@brief Invalid options are rejected before any session workers are started."""
        for key, values in (
            ("max_jpeg_bytes", (0, MAX_FRAME + 1, True, 1.5)),
            ("jpeg_retry_quality_drop", (-1, 95, True, 1.5)),
        ):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    Session(None, None, 30, 20, 200, 75, 20, **{key: value})

    def test_custom_capacity_accepts_exact_jpeg_and_rejects_one_byte_less(self):
        """@brief A configured capacity is inclusive and rejects the next smaller bound."""
        image = Image.new("RGB", (720, 480), "navy")
        jpeg = encode_receiver_jpeg(image, 75)
        self.assertEqual(encode_receiver_jpeg(image, 75, len(jpeg)), jpeg)
        with self.assertRaises(JpegCapacityError) as raised:
            encode_receiver_jpeg(image, 75, len(jpeg) - 1)
        self.assertEqual(raised.exception.actual_bytes, len(jpeg))
        self.assertEqual(raised.exception.max_bytes, len(jpeg) - 1)

    def test_invalid_encoded_bytes_fail_jpeg_validation_before_send(self):
        """@brief Malformed bytes emitted by the codec never reach the pipeline sender."""
        session = self.session(quality=75, capacity=MAX_FRAME, drop=0)
        send = Mock()

        def save_junk(image, output, **kwargs):
            """@brief Replace codec output with invalid bytes."""
            output.write(b"junk")

        with (
            patch("msv1.Image.Image.save", autospec=True, side_effect=save_junk),
            patch("stream_sender.time.perf_counter_ns", return_value=0),
        ):
            pipeline = VideoPipeline(
                session._encode,
                send,
                10_000_000,
                MAX_FRAME,
                clock=lambda: 0,
                encode_frame=session._encode_frame,
            )
            try:
                pipeline.submit(Frame(6, 0, 17, Image.new("RGB", (720, 480))))
            finally:
                pipeline.close()
        send.assert_not_called()
        self.assertEqual(pipeline.snapshot()["counts"]["encode_failures"], 1)
        self.assertIn("ValueError", pipeline.snapshot()["last_error"])

    def test_cli_rejects_invalid_capacity_and_retry_values(self):
        """@brief Invalid command-line capacity and retry limits fail argument validation."""
        for option, value in (("--max-jpeg-bytes", "0"), ("--jpeg-retry-quality-drop", "-1")):
            with self.subTest(option=option), redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit) as raised:
                    main(
                        [
                            "127.0.0.1",
                            "--clip",
                            "unused.mp4",
                            "--log",
                            "unused.jsonl",
                            option,
                            value,
                        ]
                    )
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("Invalid port", error.getvalue())

    def test_run_passes_capacity_configuration_to_session_and_log(self):
        """@brief Run forwards configured limits and records them in session configuration."""
        captured, events = {}, []

        class FakeSession:
            """@brief Capture run-time session options without starting workers."""

            def __init__(self, sock, log, fps, mbps, max_age_ms, quality, minimum, **kwargs):
                captured.update(kwargs)
                self.max_jpeg_bytes = kwargs["max_jpeg_bytes"]
                self.jpeg_retry_quality_drop = kwargs["jpeg_retry_quality_drop"]
                self.lock = threading.Lock()
                self.counts = Counter()
                self.pipeline = SimpleNamespace(submit=Mock())

            def _event(self, kind, **fields):
                events.append({"event": kind, **fields})

            def close(self):
                return {"counts": {"feedback_accepted": 0}}

        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                clip=None,
                desktop_backend="imagegrab",
                fps=1,
                mbps=2,
                max_age_ms=100,
                quality=80,
                min_quality=20,
                log=Path(directory) / "run.jsonl",
                target="127.0.0.1",
                port=5533,
                source_port=0,
                frames=1,
                desktop_filter="bilinear",
                packet_timing=False,
                start_frame_id=3,
                max_jpeg_bytes=49152,
                jpeg_retry_quality_drop=12,
            )
            with patch("stream_sender.Session", FakeSession):
                run(args, iter([Image.new("RGB", (720, 480), "black")]))

        self.assertEqual(captured["max_jpeg_bytes"], 49152)
        self.assertEqual(captured["jpeg_retry_quality_drop"], 12)
        session_config = next(event for event in events if event["event"] == "session_config")
        self.assertEqual(session_config["max_jpeg_bytes"], 49152)
        self.assertEqual(session_config["jpeg_retry_quality_drop"], 12)
