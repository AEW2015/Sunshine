"""@brief Test the bounded full-body fixture verifier and its command-line report handling."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_v20_body as verify


def make_case(root: Path, policy: str = "baseline") -> tuple[Path, dict, Path]:
    """@brief Create one tiny isolated full-body case with matching raw files and hashes."""
    case_dir = root / "cases"
    case_dir.mkdir(parents=True)
    raw = {
        "packet": b"packet",
        "ack": bytes(43),
        "source.rgb": bytes(12),
        "display.rgb565": bytes(8),
        "y.bin": bytes(8),
        "u.bin": bytes(2),
        "v.bin": bytes(2),
        "bank-y.bin": bytes(8),
        "bank-u.bin": bytes(2),
        "bank-v.bin": bytes(2),
    }
    descriptors = {}
    for name, data in raw.items():
        (case_dir / name).write_bytes(data)
        descriptors[name.split(".")[0]] = {
            "path": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    case = {
        "schema": verify.BODY_SCHEMA,
        "label": "scene-baseline-00",
        "scene": "scene",
        "policy": policy,
        "id": 0,
        "geometry": {"width": 2, "height": 2},
        "packet": descriptors["packet"],
        "ack": descriptors["ack"],
        "source_rgb": {"dtype": "|u1", "shape": [2, 2, 3], **descriptors["source"]},
        "decoded_yuv": [
            {"dtype": "<i2", "shape": [2, 2], **descriptors["y"]},
            {"dtype": "<i2", "shape": [1, 1], **descriptors["u"]},
            {"dtype": "<i2", "shape": [1, 1], **descriptors["v"]},
        ],
        "display_rgb565": {"dtype": "<u2", "shape": [2, 2], **descriptors["display"]},
        "pre_banks": {
            "0": None,
            "1": {
                "id": 3,
                "tag": "a" * 32,
                "planes": [
                    {"dtype": "<i2", "shape": [2, 2], **descriptors["bank-y"]},
                    {"dtype": "<i2", "shape": [1, 1], **descriptors["bank-u"]},
                    {"dtype": "<i2", "shape": [1, 1], **descriptors["bank-v"]},
                ],
            },
        },
        "post_banks": {},
    }
    case_path = case_dir / "case.json"
    case_bytes = json.dumps(case).encode()
    case_path.write_bytes(case_bytes)
    source_bytes = b"source-result"
    (root / "source-results.json").write_bytes(source_bytes)
    manifest = {
        "schema": verify.MANIFEST_SCHEMA,
        "source_commit": verify.MOONBUB_COMMIT,
        "source_results_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "cases": [
            {
                "case_path": "cases/case.json",
                "case_sha256": hashlib.sha256(case_bytes).hexdigest(),
                "label": case["label"],
                "policy": policy,
                "id": 0,
                "packet_sha256": case["packet"]["sha256"],
                "ack_sha256": case["ack"]["sha256"],
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    executable = root / "native.exe"
    executable.write_bytes(b"native stub")
    return case_path, case, executable


def native_report(case: dict) -> dict:
    """@brief Return a scoped successful native report for the tiny geometry."""
    return {
        "scope": "full_body_fixture",
        "id": case["id"],
        "label": case["label"],
        "yuv_samples": 6,
        "display_words": 4,
        "mandatory_hud_words_verified": 21120 if case["policy"] == "mandatory" else 0,
        "af03_exact": True,
        "post_banks_exact": True,
    }


class VerifyV20BodyTest(unittest.TestCase):
    """@brief Exercise pinned fixture validation, native reporting, negatives, and CLI safety."""

    def test_happy_path_replays_one_case_and_two_private_corruptions(self):
        """@brief Aggregate a full-body case and require exact child timeout and scope."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            _case_path, case, executable = make_case(root)
            with self.assertRaisesRegex(ValueError, "regular file"):
                verify.verify(root, root, expected_cases=1)
            calls = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                if Path(command[-1]).name == "negative.json":
                    return SimpleNamespace(returncode=1, stdout="", stderr="body decode: rejected")
                return SimpleNamespace(
                    returncode=0, stdout=json.dumps(native_report(case)), stderr=""
                )

            report = verify.verify(root, executable, runner=runner, expected_cases=1)
            self.assertEqual(report["case_count"], 1)
            self.assertEqual(report["negative_body_replays"], 2)
            self.assertEqual(report["yuv_samples"], 6)
            self.assertEqual(report["display_words"], 4)
            self.assertEqual(report["mandatory_hud_words_verified"], 0)
            self.assertEqual(len(calls), 3)
            self.assertTrue(all(call[1]["timeout"] == 60 for call in calls))
            self.assertEqual(
                report["executable_sha256"], hashlib.sha256(executable.read_bytes()).hexdigest()
            )

    def test_mandatory_case_counts_hud_words(self):
        """@brief Account expected mandatory HUD verification independently of raster counts."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            _case_path, case, executable = make_case(root, "mandatory")
            run = lambda command, **_kwargs: SimpleNamespace(
                returncode=1 if Path(command[-1]).name == "negative.json" else 0,
                stdout=""
                if Path(command[-1]).name == "negative.json"
                else json.dumps(native_report(case)),
                stderr="body decode: rejected",
            )
            report = verify.verify(root, executable, runner=run, expected_cases=1)
            self.assertEqual(report["mandatory_hud_words_verified"], 21120)

    def test_bounded_json_and_canonical_descendants(self):
        """@brief Bound metadata reads and reject traversal, missing, and directory paths."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "object.json"
            valid.write_text("{}", encoding="utf-8")
            self.assertEqual(verify.bounded_json(valid), {})
            with self.assertRaisesRegex(ValueError, "exceeds bound"):
                verify.bounded_json(valid, 1)
            valid.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(TypeError, "must be an object"):
                verify.bounded_json(valid)
            valid.write_text("{", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                verify.bounded_json(valid)
            with self.assertRaises(ValueError):
                verify.descendant(root, "../escape")
            with self.assertRaises(FileNotFoundError):
                verify.descendant(root, "missing")
            (root / "folder").mkdir()
            with self.assertRaisesRegex(ValueError, "regular file"):
                verify.descendant(root, "folder")

    def test_symlink_escape_is_rejected_after_resolution(self):
        """@brief Reject a canonical-looking path whose resolved target leaves the fixture root."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            outside = Path(temporary) / "outside"
            outside.write_bytes(b"x")
            original = Path.resolve

            def resolve(path, strict=False):
                return outside if path.name == "link" else original(path, strict=strict)

            with patch.object(Path, "resolve", resolve), self.assertRaises(ValueError):
                verify.descendant(root, "link")

    def test_invoke_passes_case_argument_timeout_and_nonchecking_mode(self):
        """@brief Keep child invocation bounded and collect nonzero reports for validation."""
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=3)

        result = verify.invoke(Path("native"), Path("case.json"), runner)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(calls[0][0], ["native", "--body-case", "case.json"])
        self.assertEqual(
            calls[0][1], {"capture_output": True, "text": True, "timeout": 60, "check": False}
        )

    def test_descriptor_enumeration_includes_bank_planes(self):
        """@brief Include every raw oracle required to reconstruct each bank precondition."""
        case = {
            "packet": 1,
            "ack": 2,
            "source_rgb": 3,
            "display_rgb565": 4,
            "decoded_yuv": [5, 6, 7],
            "pre_banks": {"0": None, "1": {"planes": [8, 9, 10]}},
        }
        self.assertEqual(list(verify.descriptors(case)), list(range(1, 11)))

    def test_negative_callback_rejects_zero_exit_or_missing_native_decode_error(self):
        """@brief Require corrupted packets to reach the native decoder and fail exactly."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            case_path, case, executable = make_case(root)
            for result in (
                SimpleNamespace(returncode=0, stdout="", stderr="body decode: rejected"),
                SimpleNamespace(returncode=1, stdout="", stderr="hash mismatch"),
            ):
                with (
                    self.subTest(result=result),
                    self.assertRaisesRegex(ValueError, "Corrupted body"),
                ):
                    verify.negative_replays(
                        executable, case_path, case, lambda *_a, value=result, **_k: value
                    )

    def test_verify_rejects_source_pin_and_manifest_errors_before_native_call(self):
        """@brief Stop on wrong pins, changed source bytes, count, and malformed case rows."""
        mutations = (
            (lambda manifest: manifest.update(schema="bad"), "schema/source pin"),
            (lambda manifest: manifest.update(source_commit="bad"), "schema/source pin"),
            (
                lambda manifest: manifest.update(source_results_sha256="0" * 64),
                "source-results mismatch",
            ),
            (lambda manifest: manifest.update(cases=[]), "case count"),
            (lambda manifest: manifest["cases"].append(None), "case_path"),
        )
        for mutate, message in mutations:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "fixtures"
                root.mkdir()
                _case_path, _case, executable = make_case(root)
                path = root / "manifest.json"
                manifest = json.loads(path.read_text())
                mutate(manifest)
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises((ValueError, KeyError)):
                    verify.verify(
                        root,
                        executable,
                        runner=lambda *_a, **_k: self.fail("native called"),
                        expected_cases=1,
                    )

    def test_verify_rejects_case_identity_native_status_json_and_report_fields(self):
        """@brief Validate case identity, report JSON, decoder status, and every oracle count."""
        report_changes = (
            {"scope": "wrong"},
            {"id": 2},
            {"label": "wrong"},
            {"yuv_samples": 5},
            {"display_words": 3},
            {"mandatory_hud_words_verified": 1},
            {"af03_exact": False},
            {"post_banks_exact": False},
        )
        for patch_report in report_changes:
            with (
                self.subTest(patch_report=patch_report),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary) / "fixtures"
                root.mkdir()
                _case_path, case, executable = make_case(root)
                report = native_report(case) | patch_report
                run = lambda *_a, value=report, **_k: SimpleNamespace(
                    returncode=0, stdout=json.dumps(value), stderr=""
                )
                with self.assertRaisesRegex(ValueError, "report scope/oracle"):
                    verify.verify(root, executable, runner=run, expected_cases=1)

        for output, status, stderr in (("[]", 0, ""), ("{", 0, ""), ("{}", 1, "decode rejected")):
            with (
                self.subTest(output=output, status=status),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary) / "fixtures"
                root.mkdir()
                _case_path, _case, executable = make_case(root)
                runner = lambda *_a, code=status, data=output, error_text=stderr, **_k: (
                    SimpleNamespace(returncode=code, stdout=data, stderr=error_text)
                )
                with self.assertRaises(ValueError):
                    verify.verify(root, executable, runner=runner, expected_cases=1)

    def test_verify_rejects_case_row_identity_and_duplicate_label(self):
        """@brief Detect duplicate labels and mismatches between manifest and case metadata."""
        for row_update, case_update in (
            ({"label": "different"}, {}),
            ({"id": 1}, {}),
            ({"packet_sha256": "x"}, {}),
            ({"ack_sha256": "x"}, {}),
            ({"policy": "mandatory"}, {}),
            ({}, {"label": "changed"}),
        ):
            with (
                self.subTest(row_update=row_update, case_update=case_update),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary) / "fixtures"
                root.mkdir()
                case_path, _case, executable = make_case(root)
                manifest_path = root / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["cases"][0].update(row_update)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                if case_update:
                    case = json.loads(case_path.read_text())
                    case.update(case_update)
                    case_bytes = json.dumps(case).encode()
                    case_path.write_bytes(case_bytes)
                    manifest["cases"][0]["case_sha256"] = hashlib.sha256(case_bytes).hexdigest()
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(ValueError):
                    verify.verify(
                        root,
                        executable,
                        runner=lambda *_a, **_k: self.fail("native called"),
                        expected_cases=1,
                    )

    def test_case_bytes_must_match_manifest_digest_before_json_use(self):
        """@brief Reject serialized case tampering before decoding or invoking native code."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            case_path, case, executable = make_case(root)
            case["policy"] = "mandatory"
            case_path.write_text(json.dumps(case), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "case metadata hash mismatch"):
                verify.verify(
                    root,
                    executable,
                    runner=lambda *_a, **_k: self.fail("native called"),
                    expected_cases=1,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            _case_path, _case, executable = make_case(root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["cases"].append(manifest["cases"][0])
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            def run(command, **_kwargs):
                if Path(command[-1]).name == "negative.json":
                    return SimpleNamespace(returncode=1, stdout="", stderr="body decode: rejected")
                report = native_report(json.loads((root / "cases/case.json").read_text()))
                return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")

            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                verify.verify(root, executable, runner=run, expected_cases=2)

    def test_verify_propagates_timeout_and_spawn_errors_to_cli_handler(self):
        """@brief Preserve timeout and launch errors for the CLI's user-facing handler."""
        import subprocess

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixtures"
            root.mkdir()
            _case_path, _case, executable = make_case(root)
            for error in (subprocess.TimeoutExpired("native", 60), OSError("missing")):
                with self.subTest(error=error), self.assertRaises(type(error)):
                    verify.verify(
                        root,
                        executable,
                        runner=lambda *_a, failure=error, **_k: (_ for _ in ()).throw(failure),
                        expected_cases=1,
                    )

    def test_cli_creates_report_exclusively_and_converts_expected_errors(self):
        """@brief Write a new report, preserve existing evidence, and report expected failures."""
        import subprocess

        report = {"schema": "v1", "cases": [{"label": "tiny"}]}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested/report.json"
            with patch.object(verify, "verify", return_value=report), patch("sys.stdout"):
                self.assertEqual(
                    verify.main(["--fixtures", "f", "--executable", "x", "--report", str(output)]),
                    0,
                )
            self.assertEqual(json.loads(output.read_text()), report)
            output.write_text("preserve", encoding="utf-8")
            for error in (
                OSError("io"),
                ValueError("bad"),
                KeyError("key"),
                TypeError("type"),
                subprocess.TimeoutExpired("child", 60),
            ):
                with (
                    self.subTest(error=error),
                    patch.object(verify, "verify", side_effect=error),
                    patch("sys.stderr"),
                    self.assertRaises(SystemExit) as raised,
                ):
                    verify.main(["--fixtures", "f", "--executable", "x", "--report", str(output)])
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_cli_help_entrypoint(self):
        """@brief Execute the script entrypoint's help path without creating a report."""
        with (
            patch("sys.argv", [str(Path(verify.__file__)), "--help"]),
            patch("sys.stdout"),
            self.assertRaises(SystemExit) as raised,
        ):
            runpy.run_path(verify.__file__, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
