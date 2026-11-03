"""@brief Tests for offline JPEG quality and bandwidth calculations."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from quality_budget import main, psnr, run, summarize, viewport


class QualityBudgetTests(unittest.TestCase):
    """@brief Verify content geometry, metrics and genuine JPEG encoding."""

    def test_viewport_and_psnr(self):
        """@brief Exclude borders and identify identical versus changed RGB content."""
        self.assertEqual(viewport(1920, 1080), (0, 37, 720, 442))
        self.assertEqual(viewport(1024, 600), (14, 37, 705, 442))
        for dims in ((0, 1), (1, -1), (True, 1)):
            with self.subTest(dims=dims), self.assertRaises(ValueError):
                viewport(*dims)
        original = Image.new("RGB", (720, 480), "black")
        changed = Image.new("RGB", (720, 480), (1, 1, 1))
        self.assertIsNone(psnr(original, original, (0, 37, 720, 442)))
        self.assertAlmostEqual(psnr(original, changed, (0, 37, 720, 442)), 48.1308, places=3)

    def test_summary_and_invalid_options(self):
        """@brief Quantiles are nearest-rank and invalid workloads are rejected."""
        self.assertEqual(summarize([1, 3, 2])["p95"], 3)
        with self.assertRaises(ValueError):
            summarize([])
        for options in (
            {"samples": 0},
            {"skip": -1},
            {"fps": 31},
            {"qualities": ()},
            {"qualities": (20, 20)},
            {"qualities": (True,)},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                run(Path("unused"), Path("unused"), frames=iter(()), **options)

    def test_real_jpegs_generate_bounded_rate_statistics(self):
        """@brief Encode real frames at two qualities and verify payload accounting."""
        source = [Image.new("RGB", (1280, 720), color) for color in ("red", "blue", "green")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            result = run(
                Path("unused"),
                path,
                samples=5,
                skip=1,
                fps=30,
                qualities=(20, 75),
                frames=iter(source),
            )
            saved = json.loads(path.read_text())
            self.assertEqual(result, saved)
            self.assertEqual(saved["samples"], 2)
            self.assertEqual(saved["requested_samples"], 5)
            self.assertTrue(saved["source_exhausted"])
            self.assertFalse(saved["end_to_end_verified"])
            for item in saved["qualities"].values():
                self.assertGreater(item["msv1_bytes"]["mean"], item["jpeg_bytes"]["mean"])
                self.assertAlmostEqual(
                    item["mean_msv1_mbps_at_target"], item["msv1_bytes"]["mean"] * 30 * 8 / 1e6
                )
            with self.assertRaises(FileExistsError):
                run(Path("unused"), path, samples=1, skip=0, qualities=(75,), frames=iter(source))

    def test_empty_input_closes_and_missing_source_fails(self):
        """@brief Empty sources do not produce a misleading measurement."""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            with self.assertRaisesRegex(ValueError, "No source frames"):
                run(Path("unused"), output, samples=1, skip=0, frames=iter(()))
            self.assertFalse(output.exists())
            with self.assertRaises(FileNotFoundError):
                run(Path(directory) / "missing", output)

    def test_file_source_hash_and_decoder_are_used(self):
        """@brief Record source provenance while allowing an injected clip decoder."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "clip"
            source.write_bytes(b"abc")
            frame = Image.new("RGB", (720, 480), "red")
            with patch("quality_budget.clip_frames", return_value=(x for x in [frame])):
                result = run(
                    source, Path(directory) / "out.json", samples=1, skip=0, qualities=(75,)
                )
            self.assertEqual(
                result["source_sha256"],
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )

    def test_identical_frames_are_reported_without_infinite_json_values(self):
        """@brief Identical pixels use an explicit count instead of an infinite PSNR."""
        with tempfile.TemporaryDirectory() as directory:
            image = Image.new("RGB", (720, 480), "red")
            with patch("quality_budget.psnr", return_value=None):
                result = run(
                    Path("unused"),
                    Path(directory) / "out.json",
                    samples=1,
                    skip=0,
                    qualities=(75,),
                    frames=iter([image]),
                )
        self.assertEqual(result["qualities"]["75"]["identical_frames"], 1)
        self.assertIsNone(result["qualities"]["75"]["rgb_content_psnr_db"])

    def test_cli_parses_qualities_and_surfaces_errors(self):
        """@brief Forward explicit qualities and reject missing or invalid sources."""
        with (
            patch("quality_budget.run", return_value={"samples": 1}) as benchmark,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["--clip", "a", "--output", "b", "--qualities", "1", "20"]), 0)
        self.assertEqual(benchmark.call_args.args[-1], (1, 20))
        with (
            patch("quality_budget.run", side_effect=ValueError("invalid")),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            main(["--clip", "a", "--output", "b"])


if __name__ == "__main__":
    unittest.main()
