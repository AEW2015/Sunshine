"""@brief Tests for the bounded sequential localhost rate sweep."""

import argparse
import io
import json
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import rate_sweep


class RateSweepTests(unittest.TestCase):
    """@brief Verify explicit inputs, output isolation, and truthful stage records."""

    def make_args(self, root, rates=(1.0, 2.0, 5.0), output_name="sweep"):
        """@brief Create explicit valid options under a temporary parent directory."""
        clip = root / "clip.mp4"
        clip.write_bytes(b"clip")
        reference_repo = root / "reference"
        reference_repo.mkdir(exist_ok=True)
        return SimpleNamespace(
            reference_repo=reference_repo,
            clip=clip,
            output_dir=root / output_name,
            rates=rates,
            frames=10,
            fps=5,
            quality=75,
            min_quality=20,
            max_age_ms=250.0,
        )

    def test_parse_rates_requires_bounded_increasing_values(self):
        """@brief Reject malformed, duplicate, unordered, nonfinite, and excessive caps."""
        self.assertEqual(rate_sweep.parse_rates("1, 2.5, 10"), (1.0, 2.5, 10.0))
        for invalid in ("", "1,nope", "2,1", "1,1", "nan", "inf", "0.01", "1001"):
            with self.subTest(invalid=invalid), self.assertRaises(argparse.ArgumentTypeError):
                rate_sweep.parse_rates(invalid)
        with self.assertRaises(argparse.ArgumentTypeError):
            rate_sweep.parse_rates(",".join(str(i) for i in range(1, 34)))

    def test_sequential_sweep_uses_same_explicit_clip_options_and_records_failure(self):
        """@brief Run all caps in order, retaining their separate logs and exact options."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self.make_args(root)
            calls = []

            def runner(stage_args):
                """@brief Save the supplied configuration and create an exclusive mock log."""
                calls.append(stage_args)
                self.assertFalse(stage_args.log.exists())
                with stage_args.log.open("x", encoding="utf-8") as log:
                    log.write("mock stage log\n")
                if stage_args.mbps == 2.0:
                    raise OSError("simulated local capture failure")
                return {"receiver": {"complete": 1}, "hardware_playback_verified": False}

            summary = rate_sweep.run_sweep(args, runner)
            self.assertEqual([call.mbps for call in calls], [1.0, 2.0, 5.0])
            self.assertTrue(all(call.clip == args.clip.resolve() for call in calls))
            self.assertTrue(all(call.fps == 5 and call.frames == 10 for call in calls))
            self.assertTrue(all(call.quality == 75 and call.min_quality == 20 for call in calls))
            self.assertTrue(all(call.max_age_ms == 250.0 and call.loop for call in calls))
            self.assertEqual(len({call.log for call in calls}), 3)
            self.assertTrue(all(call.log.parent == args.output_dir.resolve() for call in calls))
            self.assertTrue(all(call.log.is_file() for call in calls))
            self.assertEqual(
                (summary["completed"], summary["failed"], summary["not_run"]), (2, 1, 0)
            )
            self.assertFalse(summary["interrupted"])

            records = [
                json.loads(line)
                for line in (args.output_dir / "results.jsonl").read_text().splitlines()
            ]
            self.assertEqual(
                records[0]["scope"],
                "pinned localhost receiver ingress only; no physical network, hardware decode, or display claim",
            )
            stages = [record for record in records if record["event"] == "stage"]
            outcomes = [record for record in stages if record["status"] not in ("running",)]
            self.assertEqual(
                [record["status"] for record in outcomes], ["completed", "failed", "completed"]
            )
            self.assertEqual(outcomes[1]["error_type"], "OSError")
            self.assertEqual(outcomes[1]["error"], "simulated local capture failure")
            self.assertEqual(records[-1]["event"], "sweep_summary")
            self.assertFalse(records[-1]["hardware_playback_verified"])

    def test_existing_output_directory_is_never_overwritten(self):
        """@brief Refuse an existing directory before invoking any stage."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self.make_args(root)
            args.output_dir.mkdir()
            sentinel = args.output_dir / "keep.txt"
            sentinel.write_text("existing", encoding="utf-8")
            runner = Mock()
            with self.assertRaises(FileExistsError):
                rate_sweep.run_sweep(args, runner)
            runner.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing")

    def test_interruption_marks_current_and_remaining_stages(self):
        """@brief Preserve completed work and label interrupted and unrun caps accurately."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self.make_args(root)
            calls = []

            def runner(stage_args):
                """@brief Complete one stage and interrupt during the next."""
                calls.append(stage_args.mbps)
                if len(calls) == 2:
                    raise KeyboardInterrupt
                return {"receiver": {"complete": 1}}

            summary = rate_sweep.run_sweep(args, runner)
            self.assertEqual(calls, [1.0, 2.0])
            self.assertTrue(summary["interrupted"])
            self.assertEqual(
                (summary["completed"], summary["failed"], summary["not_run"]), (1, 0, 1)
            )
            records = [
                json.loads(line)
                for line in (args.output_dir / "results.jsonl").read_text().splitlines()
            ]
            outcomes = [
                record["status"]
                for record in records
                if record["event"] == "stage" and record["status"] != "running"
            ]
            self.assertEqual(outcomes, ["completed", "interrupted", "not_run"])

    def test_validation_happens_before_output_creation(self):
        """@brief Invalid long-run inputs cannot leave a partial output directory."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self.make_args(root, rates=(5.0, 1.0))
            with self.assertRaisesRegex(ValueError, "increasing"):
                rate_sweep.run_sweep(args, Mock())
            self.assertFalse(args.output_dir.exists())
            args.rates = (1.0, 2.0)
            args.frames = rate_sweep.MAX_TOTAL_FRAMES // 2 + 1
            with self.assertRaisesRegex(ValueError, "Total sweep frames"):
                rate_sweep.run_sweep(args, Mock())
            self.assertFalse(args.output_dir.exists())
            args.rates = (1.0,)
            args.frames = rate_sweep.MAX_FRAMES + 1
            with self.assertRaisesRegex(ValueError, "Frame count"):
                rate_sweep.run_sweep(args, Mock())
            self.assertFalse(args.output_dir.exists())

            invalid_configs = (
                ("fps", 0, "FPS"),
                ("quality", 96, "JPEG quality"),
                ("min_quality", 76, "JPEG quality"),
                ("max_age_ms", float("inf"), "Maximum age"),
            )
            for name, value, message in invalid_configs:
                with self.subTest(name=name):
                    args = self.make_args(root, output_name=f"invalid-{name}")
                    setattr(args, name, value)
                    with self.assertRaisesRegex(ValueError, message):
                        rate_sweep.run_sweep(args, Mock())
                    self.assertFalse(args.output_dir.exists())

            args = self.make_args(root, output_name="missing-reference")
            args.reference_repo = root / "missing-reference-repo"
            with self.assertRaisesRegex(ValueError, "Reference repository"):
                rate_sweep.run_sweep(args, Mock())
            self.assertFalse(args.output_dir.exists())
            args = self.make_args(root, output_name="missing-clip")
            args.clip = root / "missing-clip.mp4"
            with self.assertRaisesRegex(ValueError, "Clip is not a file"):
                rate_sweep.run_sweep(args, Mock())
            self.assertFalse(args.output_dir.exists())

    def test_cli_requires_explicit_long_run_inputs_and_reports_summary(self):
        """@brief CLI has no implicit rate/frame defaults and returns sweep status."""
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            rate_sweep.main([])
        result = {
            "status": "finished",
            "completed": 2,
            "failed": 0,
            "not_run": 0,
            "interrupted": False,
            "results": "results.jsonl",
            "output_dir": "sweep",
            "hardware_playback_verified": False,
        }
        args = [
            "--reference-repo",
            "reference",
            "--clip",
            "clip.mp4",
            "--output-dir",
            "sweep",
            "--rates",
            "1,2",
            "--frames",
            "2",
            "--fps",
            "5",
            "--quality",
            "75",
            "--min-quality",
            "20",
            "--max-age-ms",
            "250",
        ]
        with (
            patch("rate_sweep.run_sweep", return_value=result),
            patch("builtins.print") as output,
        ):
            self.assertEqual(rate_sweep.main(args), 0)
        output.assert_called_once()

        result["interrupted"] = True
        with patch("rate_sweep.run_sweep", return_value=result), patch("builtins.print"):
            self.assertEqual(rate_sweep.main(args), 130)
        result["interrupted"] = False
        result["failed"] = 1
        with patch("rate_sweep.run_sweep", return_value=result), patch("builtins.print"):
            self.assertEqual(rate_sweep.main(args), 1)

    def test_cli_reports_operational_errors_and_module_entry_point(self):
        """@brief Convert setup errors to argparse diagnostics and exercise script entry."""
        args = [
            "--reference-repo",
            "reference",
            "--clip",
            "clip.mp4",
            "--output-dir",
            "sweep",
            "--rates",
            "1",
            "--frames",
            "2",
            "--fps",
            "5",
            "--quality",
            "75",
            "--min-quality",
            "20",
            "--max-age-ms",
            "250",
        ]
        with (
            patch("rate_sweep.run_sweep", side_effect=FileExistsError("already exists")),
            patch("sys.stderr", new_callable=io.StringIO),
            self.assertRaises(SystemExit) as error,
        ):
            rate_sweep.main(args)
        self.assertEqual(error.exception.code, 2)

        with (
            patch("sys.argv", ["rate_sweep.py", "--help"]),
            self.assertRaises(SystemExit) as entry_error,
        ):
            runpy.run_path(rate_sweep.__file__, run_name="__main__")
        self.assertEqual(entry_error.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
