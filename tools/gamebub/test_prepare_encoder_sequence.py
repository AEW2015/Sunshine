"""@brief Verify bounded saved-clip export and truthful nonrepeated source provenance."""

import hashlib
import io
import json
import math
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import prepare_encoder_sequence as sequence


class EncoderSequenceExporterTests(unittest.TestCase):
    """@brief Exercise export without relying on a decoder or large moving-video assets."""

    def setUp(self):
        """@brief Use a private source file and exclusively owned output directory."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.clip = self.root / "test.webm"
        self.clip.write_bytes(b"saved clip bytes")
        self.output = self.root / "sequence"
        self.digest = hashlib.sha256(self.clip.read_bytes()).hexdigest()

    def frames(self, times):
        """@brief Supply generator-close-compatible stand-in source timestamps."""
        return (SimpleNamespace(time=stamp) for stamp in times)

    def canvas(self, frame):
        """@brief Distinguish selected source frames with deterministic RGB values."""
        value = round(frame.time * 30) % 256
        return Image.new("RGB", (720, 480), (value, 40, 90))

    def export(self, times=(0, 1 / 30, 2 / 30), **kwargs):
        """@brief Reuse production validation and I/O around controlled decoded frames."""
        with (
            patch.object(sequence, "clip_frames", return_value=self.frames(times)),
            patch.object(sequence, "native_frames", return_value=self.frames(times)),
            patch.object(sequence, "native_rate", return_value={"numerator": 30, "denominator": 1}),
            patch.object(sequence, "canvas", side_effect=self.canvas),
        ):
            return sequence.export(self.clip, self.output, **kwargs)

    def test_hash_bound_unique_frames_and_complete_manifest(self):
        """@brief Publish exact RGB files and their hashes only after the sequence completes."""
        result = self.export(frames=3, expected_sha256=self.digest)
        self.assertEqual(result["schema"], sequence.SCHEMA)
        self.assertEqual(result["source"]["sha256"], self.digest)
        self.assertFalse(result["source"]["loop"])
        self.assertEqual([row["pts_us"] for row in result["frames"]], [0, 33333, 66667])
        self.assertEqual([row["id"] for row in result["frames"]], [0, 1, 2])
        for row in result["frames"]:
            descriptor = row["rgb"]
            raw = (self.output / descriptor["path"]).read_bytes()
            self.assertEqual(len(raw), sequence.FRAME_BYTES)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), descriptor["sha256"])
            self.assertEqual(descriptor["shape"], [480, 720, 3])
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), result)

    def test_offset_rounds_up_to_existing_sampling_grid(self):
        """@brief Preserve absolute source/sample identities when skipping to a requested offset."""
        result = self.export((0, 1 / 30, 2 / 30, 3 / 30), frames=2, offset_us=33334)
        self.assertEqual(result["source"]["first_sample_index"], 2)
        self.assertEqual(result["source"]["pts_origin_us"], 0)
        self.assertEqual(result["source"]["requested_offset_us"], 33334)
        self.assertEqual([row["id"] for row in result["frames"]], [2, 3])
        self.assertEqual(result["frames"][0]["sample_time_us"], 66666)

    def test_native_selection_keeps_original_pts_and_skips_by_relative_time(self):
        """@brief Native mode never invents a sample timeline or repeats original source frames."""
        result = self.export(
            (0.007, 0.040, 0.074, 0.107), frames=2, selection="native-decoded", offset_us=50000
        )
        self.assertEqual(result["source"]["native_rate"], {"numerator": 30, "denominator": 1})
        self.assertIsNone(result["source"]["sample_fps"])
        self.assertIsNone(result["source"]["first_sample_index"])
        self.assertEqual(result["source"]["first_decoded_id"], 2)
        self.assertEqual(result["source"]["pts_origin_us"], 7000)
        self.assertEqual([row["pts_us"] for row in result["frames"]], [74000, 107000])
        self.assertEqual([row["relative_pts_us"] for row in result["frames"]], [67000, 100000])
        self.assertNotIn("sample_time_us", result["frames"][0])

    def test_native_selection_and_duplicate_pts_are_checked(self):
        """@brief Unsupported modes or FPS overrides fail rather than silently resampling."""
        with self.assertRaisesRegex(ValueError, "selection mode"):
            self.export(frames=1, selection="unknown")
        with self.assertRaisesRegex(ValueError, "no resampling FPS"):
            self.export(frames=1, fps=30, selection="native-decoded")
        with self.assertRaisesRegex(ValueError, "nonmonotonic native"):
            self.export((0.007, 0.040, 0.040), frames=3, selection="native-decoded")
        self.assertFalse((self.output / "manifest.json").exists())

    def test_native_decoder_helpers_preserve_rate_and_aspect_contract(self):
        """@brief Native metadata and frames come from one declared stream with no scaling trick."""
        stream = SimpleNamespace(average_rate=Fraction(30000, 1001), sample_aspect_ratio=1)

        @contextmanager
        def container():
            """@brief Yield one fake stream and finite decoder in a closeable context."""
            yield SimpleNamespace(
                streams=SimpleNamespace(video=[stream]), decode=lambda target: iter(["frame"])
            )

        with patch.object(sequence.av, "open", side_effect=lambda path: container()):
            self.assertEqual(
                sequence.native_rate(self.clip), {"numerator": 30000, "denominator": 1001}
            )
            self.assertEqual(list(sequence.native_frames(self.clip)), ["frame"])
            stream.sample_aspect_ratio = 2
            with self.assertRaisesRegex(ValueError, "nonsquare"):
                list(sequence.native_frames(self.clip))
            for rate in (None, Fraction(0), Fraction(1_000_001)):
                stream.average_rate = rate
                with self.assertRaisesRegex(ValueError, "nominal rate"):
                    sequence.native_rate(self.clip)

    def test_invalid_limits_reject_before_creating_output(self):
        """@brief Reject bools, excessive frame/rate work and unsupported offsets."""
        for kwargs in (
            {"frames": 0},
            {"frames": 1801},
            {"frames": True},
            {"fps": 0},
            {"fps": 31},
            {"fps": True},
            {"offset_us": -1},
            {"offset_us": 86_400_000_001},
            {"offset_us": True},
        ):
            with self.assertRaisesRegex(ValueError, "bounds"):
                self.export(**kwargs)
            self.assertFalse(self.output.exists())

    def test_source_hash_and_existing_output_fail_before_decode(self):
        """@brief Preserve prior evidence and fail provenance without decoder side effects."""
        for value in ("x", "A" * 64, 0):
            with self.assertRaisesRegex(ValueError, "format"):
                self.export(frames=1, expected_sha256=value)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.export(frames=1, expected_sha256="0" * 64)
        self.output.mkdir()
        (self.output / "preserved.txt").write_text("existing")
        with self.assertRaises(FileExistsError):
            self.export(frames=1)
        self.assertEqual((self.output / "preserved.txt").read_text(), "existing")

    def test_empty_source_and_missing_clip_are_not_published(self):
        """@brief Never publish source provenance for empty or absent inputs."""
        self.clip.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.export(frames=1)
        self.clip.unlink()
        with self.assertRaises(FileNotFoundError):
            self.export(frames=1)
        self.assertFalse(self.output.exists())

    def test_repeated_or_backward_pts_never_publish_manifest(self):
        """@brief Upsampled repeats cannot masquerade as distinct source frames."""
        for index, times in enumerate(((0, 0), (0.1, 0.05))):
            self.output = self.root / f"repeat-{index}"
            with self.assertRaisesRegex(ValueError, "Repeated/nonmonotonic"):
                self.export(times, frames=2)
            self.assertFalse((self.output / "manifest.json").exists())

    def test_bad_timestamp_and_canvas_fail_without_manifest(self):
        """@brief Bound source times and exact RGB8 storage independently of decoder claims."""
        for stamp in (None, math.inf, -1):
            with self.assertRaisesRegex(ValueError, "timestamps"):
                self.export((stamp,), frames=1)
        with self.assertRaisesRegex(ValueError, "timestamp bound"):
            self.export((2**63,), frames=1)
        with (
            patch.object(sequence, "clip_frames", return_value=self.frames((0,))),
            patch.object(sequence, "canvas", return_value=Image.new("RGB", (1, 1))),
            self.assertRaisesRegex(ValueError, "RGB8"),
        ):
            sequence.export(self.clip, self.output, frames=1)
        self.assertFalse((self.output / "manifest.json").exists())
        with (
            patch.object(sequence, "clip_frames", return_value=self.frames((0,))),
            patch.object(sequence, "canvas", return_value=Image.new("L", (720, 480))),
            self.assertRaisesRegex(ValueError, "RGB8"),
        ):
            sequence.export(self.clip, self.output, frames=1)

    def test_short_clip_and_offset_past_end_do_not_loop(self):
        """@brief Incomplete exports leave only private partial files, never a valid manifest."""
        with self.assertRaisesRegex(ValueError, "ended"):
            self.export((0,), frames=2)
        self.assertFalse((self.output / "manifest.json").exists())
        self.output = self.root / "past-end"
        with self.assertRaisesRegex(ValueError, "ended"):
            self.export((0,), frames=1, offset_us=1_000_000)
        self.assertFalse(self.output.exists())

    def test_file_hash_uses_multiple_bounded_reads(self):
        """@brief Large saved files are hashed without loading the complete clip."""
        raw = b"z" * (1024 * 1024 + 2)
        self.clip.write_bytes(raw)
        self.assertEqual(
            sequence.file_identity(self.clip), (len(raw), hashlib.sha256(raw).hexdigest())
        )

    def test_cli_reports_source_identity(self):
        """@brief Exercise command options around the production exporter entry point."""
        output = io.StringIO()
        with (
            patch.object(sequence, "clip_frames", return_value=self.frames((0,))),
            patch.object(sequence, "canvas", side_effect=self.canvas),
            redirect_stdout(output),
        ):
            self.assertEqual(
                sequence.main(
                    [
                        "--clip",
                        str(self.clip),
                        "--output-dir",
                        str(self.output),
                        "--frames",
                        "1",
                        "--fps",
                        "30",
                        "--expected-sha256",
                        self.digest,
                    ]
                ),
                0,
            )
        self.assertFalse(json.loads(output.getvalue())["hardware_verified"])


if __name__ == "__main__":
    unittest.main()
