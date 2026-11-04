"""@brief Regression tests for local speaker-loopback setup and deterministic PCM."""

import runpy
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import windows_audio as audio


class WindowsAudioTests(unittest.TestCase):
    """@brief Validate source selection, bounds, stream faults and silence accounting."""

    def backend(self, channels=8, rate=48000, loopback=True):
        """@brief Return a fake WASAPI device; never touch a microphone or speaker."""
        backend = MagicMock()
        device = {
            "index": 3,
            "maxInputChannels": channels,
            "defaultSampleRate": rate,
            "isLoopbackDevice": loopback,
            "name": "test speakers",
        }
        driver = backend.PyAudio.return_value.__enter__.return_value
        driver.get_default_wasapi_loopback.return_value = device
        stream = driver.open.return_value.__enter__.return_value
        stream.read.side_effect = lambda n, **kwargs: bytes(n * min(channels, 2) * 2)
        return backend, driver, stream

    def test_capture_stereo_and_mono(self):
        """@brief Request stereo from a surround endpoint and preserve short final blocks."""
        for channels in (8, 1):
            with self.subTest(channels=channels), tempfile.TemporaryDirectory() as directory:
                backend, driver, stream = self.backend(channels)
                output = Path(directory) / "capture.wav"
                result = audio.capture(0.015, output, backend)
                self.assertEqual((result["frames"], result["peak"], result["rms"]), (720, 0, 0))
                self.assertEqual(driver.open.call_args.kwargs["channels"], min(channels, 2))
                self.assertEqual(stream.read.call_count, 2)
                with wave.open(str(output)) as wav:
                    self.assertEqual(wav.getnframes(), 720)
                with self.assertRaises(FileExistsError):
                    audio.capture(0.01, output, backend)

    def test_bad_device_and_bad_duration(self):
        """@brief Reject non-loopback/unsupported endpoints and invalid capture durations."""
        for seconds in (0, -1, 61, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                audio.capture(seconds, "unused")
        for kwargs in ({"loopback": False}, {"channels": 3}, {"rate": 1}, {"rate": 192001}):
            backend, _, _ = self.backend(**kwargs)
            with self.assertRaises(ValueError):
                audio.capture(0.01, "unused", backend)

    def test_short_block_and_overflow_fail(self):
        """@brief Never claim continuous successful capture after truncation or overflow."""
        for failure in (b"x", OSError("input overflow")):
            with tempfile.TemporaryDirectory() as directory:
                backend, _, stream = self.backend()
                stream.read.side_effect = failure if isinstance(failure, OSError) else None
                stream.read.return_value = failure
                with self.assertRaises((ValueError, OSError)):
                    audio.capture(0.01, Path(directory) / "failed.wav", backend)

    def test_stats_tone_and_cli(self):
        """@brief Tones differ by channel and signed extremes are accounted correctly."""
        self.assertEqual(audio.pcm_stats(b"")["peak"], 0)
        self.assertEqual(audio.pcm_stats(b"\x00\x80")["peak"], 32768)
        for invalid in (None, b"x"):
            with self.assertRaises(ValueError):
                audio.pcm_stats(invalid)
        with patch("sys.byteorder", "big"):
            self.assertEqual(audio.pcm_stats(b"\x01\x00")["peak"], 256)
        self.assertEqual(len(audio.test_tone()), 1920)
        self.assertGreater(audio.pcm_stats(audio.test_tone())["rms"], 1000)
        for frames, rate in (
            (0, 48000),
            (True, 48000),
            (480001, 48000),
            (1, True),
            (1, 1),
            (1, 192001),
        ):
            with self.assertRaises(ValueError):
                audio.test_tone(frames, rate)
        with patch.object(audio, "capture", return_value={}), patch("builtins.print"):
            audio.main(["--output", "unused", "--seconds", "1"])

    def test_optional_backend_import(self):
        """@brief The optional hardware dependency is loaded only for capture."""
        backend, _, _ = self.backend()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict("sys.modules", {"pyaudiowpatch": backend}),
        ):
            self.assertEqual(audio.capture(0.01, Path(directory) / "x.wav")["frames"], 480)

    def test_command_entrypoint(self):
        """@brief The real CLI captures only from the injected loopback device."""
        backend, _, _ = self.backend()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict("sys.modules", {"pyaudiowpatch": backend}),
            patch(
                "sys.argv",
                [
                    "windows_audio.py",
                    "--seconds",
                    ".01",
                    "--output",
                    str(Path(directory) / "cli.wav"),
                ],
            ),
            patch("builtins.print"),
        ):
            runpy.run_path(str(Path(audio.__file__)), run_name="__main__")


if __name__ == "__main__":
    unittest.main()
