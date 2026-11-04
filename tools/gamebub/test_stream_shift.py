"""@brief Regression tests for explicit right-shift selection in the standalone sender."""

import contextlib
import io
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from host import shift_canvas_right
from stream_sender import main, run


class StreamShiftTests(unittest.TestCase):
    """@brief Keep shifting explicit, observable and separate from panel placement."""

    def test_run_shifts_after_letterboxing_and_logs_option(self):
        """@brief A selected shift reaches submitted pixels and session configuration."""
        frames, events = [], []

        class FakeSession:
            """@brief Collect prepared pixels without encoder workers or network traffic."""

            def __init__(self, *args, **kwargs):
                """@brief Supply only session state required by the capture loop."""
                self.max_jpeg_bytes = kwargs["max_jpeg_bytes"]
                self.jpeg_retry_quality_drop = kwargs["jpeg_retry_quality_drop"]
                self.lock, self.counts = threading.Lock(), Counter()
                self.pipeline = SimpleNamespace(submit=frames.append)

            def _event(self, kind, **fields):
                """@brief Retain capture and session settings for assertions."""
                events.append({"event": kind, **fields})

            def close(self):
                """@brief Return a minimal stopped-session result."""
                return {"counts": {}}

        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                target="127.0.0.1",
                port=5533,
                source_port=0,
                log=Path(directory) / "shift.jsonl",
                clip=None,
                fps=5,
                frames=1,
                mbps=2,
                max_age_ms=200,
                quality=25,
                min_quality=25,
                shift_right_px=20,
            )
            source = Image.new("RGB", (1280, 720), "red")
            with (
                patch("stream_sender.Session", FakeSession),
                patch("stream_sender.socket.socket"),
                patch("stream_sender.shift_canvas_right", wraps=shift_canvas_right) as shift,
            ):
                run(args, iter([source]))
            shift.assert_called_once()
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].image.size, (720, 480))
        self.assertEqual(frames[0].image.getbbox(), (20, 37, 720, 442))
        self.assertEqual(frames[0].image.getpixel((19, 240)), (0, 0, 0))
        self.assertEqual(frames[0].image.getpixel((20, 240)), (255, 0, 0))
        config = next(e for e in events if e["event"] == "session_config")
        self.assertEqual(config["shift_right_px"], 20)
        self.assertEqual(source.getpixel((0, 0)), (255, 0, 0))

    def test_invalid_programmatic_shift_is_rejected_before_opening_outputs(self):
        """@brief Direct run callers must also satisfy whole-pixel bounds."""
        for value in (-1, 720, True, 1.5):
            with (
                self.subTest(value=value),
                patch("stream_sender.socket.socket") as sock,
                self.assertRaisesRegex(ValueError, "Right shift"),
            ):
                run(SimpleNamespace(shift_right_px=value))
            sock.assert_not_called()

    def test_cli_validates_and_forwards_shift(self):
        """@brief CLI accepts an explicit shift and rejects out-of-canvas values."""
        argv = ["127.0.0.1", "--desktop", "--log", "unused.jsonl", "--shift-right-px"]
        for value in ("-1", "720"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([*argv, value])
        with (
            patch("stream_sender.run", return_value={"counts": {"feedback_accepted": 1}}) as run_,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main([*argv, "20"]), 0)
        self.assertEqual(run_.call_args.args[0].shift_right_px, 20)
