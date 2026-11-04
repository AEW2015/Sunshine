"""@brief Regression tests for the native v20 fixture verification harness."""

import hashlib
import json
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verify_v20_native as verify


class VerifyV20NativeTests(unittest.TestCase):
    """@brief Exercise manifest validation and checked native command results."""

    def make_fixtures(self, root: Path) -> Path:
        """@brief Write a minimal valid manifest suitable for unit-level verification."""
        root.mkdir(parents=True)
        (root / "inverse").mkdir()
        (root / "contracts").mkdir()
        (root / "ar03").mkdir()
        input_data = bytes(256)
        expected_data = bytes([1]) * 256
        ar03 = b"AR03" + bytes(61)
        af03 = b"AF03" + bytes(39)
        files = {
            "inverse/tiny.input.i32le.bin": input_data,
            "inverse/tiny.expected.i32le.bin": expected_data,
            "contracts/wire-contract.json": b"{}\n",
            "contracts/development-profile.json": b"{}\n",
            "ar03/tiny.ar03": ar03,
            "ar03/tiny.af03": af03,
        }
        for rel, content in files.items():
            (root / rel).write_bytes(content)
        digest = lambda content: hashlib.sha256(content).hexdigest()
        manifest = {
            "schema": verify.MANIFEST_SCHEMA,
            "source": {"moonbub_commit": verify.MOONBUB_COMMIT, "sunshine_commit": verify.SUNSHINE_COMMIT},
            "scope": verify.MANIFEST_SCOPE,
            "inverse": {"schema": "gamebub-v20-native-inverse-fixtures-v1", "datasets": [{
                "name": "tiny", "blocks": 1, "bytes_per_block": 256,
                "input_path": "inverse/tiny.input.i32le.bin", "input_sha256": digest(input_data),
                "expected_path": "inverse/tiny.expected.i32le.bin", "expected_sha256": digest(expected_data),
            }]},
            "contracts": {
                "wire-contract.json": {"path": "contracts/wire-contract.json", "sha256": digest(files["contracts/wire-contract.json"])},
                "development-profile.json": {"path": "contracts/development-profile.json", "sha256": digest(files["contracts/development-profile.json"])},
            },
            "ar03_fixtures": [{
                "label": "tiny", "ar03_path": "ar03/tiny.ar03", "ar03_bytes": len(ar03), "ar03_sha256": digest(ar03),
                "af03_path": "ar03/tiny.af03", "af03_bytes": len(af03), "af03_sha256": digest(af03),
            }],
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def runner(self, calls):
        """@brief Return a subprocess mock with correct scopes and rejection for temp packets."""
        def run(command, **kwargs):
            calls.append((command, kwargs))
            if Path(command[-1]).name.startswith("gamebub-v20-"):
                return SimpleNamespace(returncode=1, stdout="", stderr="rejected")
            option = command[1]
            if option == "--inverse":
                output = {"scope": "inverse_only", "blocks": 1, "samples": 64}
            else:
                output = {"scope": "envelope_only", "bytes": 65 if option == "--ar03" else 43}
            return SimpleNamespace(returncode=0, stdout=json.dumps(output), stderr="")
        return run

    def assert_manifest_rejected(self, change, match=""):
        """@brief Confirm malformed metadata is rejected before the mocked child runs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            change(manifest)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            calls = []
            with self.assertRaises(verify.VerificationError) as caught:
                verify.verify_fixtures(root, exe, runner=self.runner(calls), expected_inverse_datasets=1, expected_envelopes=1)
            if match:
                self.assertIn(match, str(caught.exception))
            self.assertEqual(calls, [])

    def test_verifies_manifest_native_counts_and_corruption_rejections(self):
        """@brief Counts exact inverse work separately from envelope-only checks."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            calls = []
            report = verify.verify_fixtures(root, exe, runner=self.runner(calls), expected_inverse_datasets=1, expected_envelopes=1)
        self.assertEqual(report["scope"], {"inverse": "inverse_only", "envelopes": "envelope_only"})
        self.assertEqual(report["inverse"], {"datasets": [{"dataset": "tiny", "blocks": 1, "samples": 64}], "blocks": 1, "samples": 64})
        self.assertEqual(report["envelopes"], {"ar03": 1, "af03": 1})
        self.assertEqual(report["negative_envelope_checks"], 4)
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(call[1]["timeout"] == 60 for call in calls))

    def test_tampered_fixture_fails_before_native_execution(self):
        """@brief Reject changed packet bytes from their manifest digest before subprocess."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            with (root / "ar03/tiny.ar03").open("ab") as stream:
                stream.write(b"x")
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            calls = []
            with self.assertRaisesRegex(verify.VerificationError, "byte length mismatch"):
                verify.verify_fixtures(root, exe, runner=self.runner(calls), expected_inverse_datasets=1, expected_envelopes=1)
            self.assertEqual(calls, [])

    def test_invalid_child_output_fails_closed(self):
        """@brief Do not accept a zero exit when the native report is not valid JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            def invalid_output(_command, **_kwargs):
                return SimpleNamespace(returncode=0, stdout="not json", stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "invalid JSON"):
                verify.verify_fixtures(root, exe, runner=invalid_output, expected_inverse_datasets=1, expected_envelopes=1)

    def test_manifest_rejects_wrong_pins_schemas_rows_paths_and_lengths(self):
        """@brief Exercise manifest guards before untrusted paths reach subprocess."""
        mutations = [
            (lambda value: value.update(schema="wrong"), "schema"),
            (lambda value: value.update(scope="wrong"), "scope"),
            (lambda value: value["source"].update(moonbub_commit="wrong"), "pin"),
            (lambda value: value["inverse"].update(schema="wrong"), "inverse schema"),
            (lambda value: value["inverse"]["datasets"][0].update(blocks=True), "dimensions"),
            (lambda value: value["inverse"]["datasets"][0].update(input_path=["oops"]), "path"),
            (lambda value: value["inverse"]["datasets"][0].update(expected_path="../escape"), "path"),
            (lambda value: value["inverse"]["datasets"][0].update(expected_path="inverse/tiny.input.i32le.bin"), "duplicate"),
            (lambda value: value["inverse"]["datasets"][0].update(input_sha256="bad"), "SHA-256"),
            (lambda value: value.update(contracts={}), "contract manifest"),
            (lambda value: value["contracts"].update({"wire-contract.json": []}), "contract entry"),
            (lambda value: value.update(ar03_fixtures=[]), "envelope fixture count"),
            (lambda value: value["ar03_fixtures"][0].update(ar03_bytes=True), "envelope length"),
            (lambda value: value["ar03_fixtures"][0].update(ar03_path="../packet"), "path"),
            (lambda value: value["ar03_fixtures"][0].update(ar03_path="inverse/tiny.input.i32le.bin"), "duplicate"),
            (lambda value: value["ar03_fixtures"][0].update(af03_bytes=42), "envelope length"),
            (lambda value: value["inverse"].update(datasets=[None]), "dataset row"),
            (lambda value: value["ar03_fixtures"].__setitem__(0, None), "envelope fixture row"),
            (lambda value: value["ar03_fixtures"][0].update(ar03_bytes=49_153), "byte cap"),
            (lambda value: value["contracts"]["wire-contract.json"].update(path="../contract"), "path"),
        ]
        for change, expected in mutations:
            with self.subTest(expected=expected):
                self.assert_manifest_rejected(change, expected)

    def test_manifest_rejects_invalid_json_oversize_and_hash_mismatch(self):
        """@brief Bound the manifest and verify exact bytes against every digest."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            manifest_path = root / "manifest.json"
            manifest_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(verify.VerificationError, "invalid fixture manifest"):
                verify._load_manifest(root, 1, 1)
            manifest_path.write_bytes(b" " * (4 * 1024 * 1024 + 1))
            with self.assertRaisesRegex(verify.VerificationError, "size limit"):
                verify._load_manifest(root, 1, 1)
            (root / "ar03/tiny.ar03").write_bytes(b"Z" * 65)
            # Exercise the digest guard directly; no subprocess is involved.
            with self.assertRaisesRegex(verify.VerificationError, "SHA-256 mismatch"):
                verify._verified_bytes(root, "ar03/tiny.ar03", 65, hashlib.sha256(b"x" * 65).hexdigest(), "tampered")

    def test_executable_file_and_dataset_count_are_required(self):
        """@brief Fail before execution when the binary or fixture count is wrong."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            with self.assertRaisesRegex(verify.VerificationError, "dataset count"):
                verify.verify_fixtures(root, exe, runner=self.runner([]), expected_inverse_datasets=2, expected_envelopes=1)
            with self.assertRaisesRegex(verify.VerificationError, "not a file"):
                verify.verify_fixtures(root, root, runner=self.runner([]), expected_inverse_datasets=1, expected_envelopes=1)

    def test_path_resolution_rejects_escape_and_nonfiles(self):
        """@brief Keep resolved paths under fixture root and require regular files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.write_text("x", encoding="utf-8")
            original_resolve = Path.resolve
            def fake_resolve(path, strict=False):
                return outside if path.name == "link" else original_resolve(path, strict=strict)
            with patch.object(Path, "resolve", fake_resolve), self.assertRaisesRegex(verify.VerificationError, "escapes root"):
                verify._relative_file(root, "link")
            (root / "directory").mkdir()
            with self.assertRaisesRegex(verify.VerificationError, "not a file"):
                verify._relative_file(root, "directory")
            for bad in (None, [], "", "a\\b", "../escape", "C:/escape", "a//b"):
                with self.subTest(path=bad), self.assertRaises(verify.VerificationError):
                    verify._safe_relative_name(bad)

    def test_native_nonzero_timeout_bad_json_nonobject_and_wrong_counts_fail(self):
        """@brief Reject broken native invocations and reports rather than counting passes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            runners = [
                (lambda *_a, **_k: SimpleNamespace(returncode=2, stdout="", stderr="no"), "rejected"),
                (lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="{", stderr=""), "invalid JSON"),
                (lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="[]", stderr=""), "invalid report"),
                (lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired("native", 60)), "failed to run"),
                (lambda *_a, **_k: (_ for _ in ()).throw(OSError("missing")), "failed to run"),
            ]
            for run, expected in runners:
                with self.subTest(expected=expected), self.assertRaisesRegex(verify.VerificationError, expected):
                    verify.verify_fixtures(root, exe, runner=run, expected_inverse_datasets=1, expected_envelopes=1)

            calls = []
            def wrong_counts(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(returncode=0, stdout=json.dumps({"scope": "inverse_only", "blocks": 2, "samples": 128}), stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "scope/count"):
                verify.verify_fixtures(root, exe, runner=wrong_counts, expected_inverse_datasets=1, expected_envelopes=1)

    def test_negative_native_must_return_exact_rejection_code(self):
        """@brief Reject corruption probes that exit with a noncanonical status."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            def accepted_negative(command, **_kwargs):
                if Path(command[-1]).name.startswith("gamebub-v20-"):
                    return SimpleNamespace(returncode=2, stdout="", stderr="rejected")
                if command[1] == "--inverse":
                    report = {"scope": "inverse_only", "blocks": 1, "samples": 64}
                else:
                    report = {"scope": "envelope_only", "bytes": 65 if command[1] == "--ar03" else 43}
                return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "AR03 corruption"):
                verify.verify_fixtures(root, exe, runner=accepted_negative, expected_inverse_datasets=1, expected_envelopes=1)

    def test_envelope_report_mismatch_and_negative_spawn_failure_fail(self):
        """@brief Require correct per-kind byte reports and handle failed corruption probes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            self.make_fixtures(root)
            exe = Path(tmp) / "native.exe"
            exe.write_bytes(b"mock executable")
            def wrong_envelope(command, **_kwargs):
                if command[1] == "--inverse":
                    return SimpleNamespace(returncode=0, stdout=json.dumps({"scope": "inverse_only", "blocks": 1, "samples": 64}), stderr="")
                return SimpleNamespace(returncode=0, stdout=json.dumps({"scope": "envelope_only", "bytes": 0}), stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "scope/length"):
                verify.verify_fixtures(root, exe, runner=wrong_envelope, expected_inverse_datasets=1, expected_envelopes=1)

            def failed_negative(command, **_kwargs):
                if Path(command[-1]).name.startswith("gamebub-v20-"):
                    raise OSError("cannot execute")
                if command[1] == "--inverse":
                    report = {"scope": "inverse_only", "blocks": 1, "samples": 64}
                else:
                    report = {"scope": "envelope_only", "bytes": 65 if command[1] == "--ar03" else 43}
                return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "negative envelope check"):
                verify.verify_fixtures(root, exe, runner=failed_negative, expected_inverse_datasets=1, expected_envelopes=1)

            def bad_af03_negative(command, **_kwargs):
                if Path(command[-1]).name.startswith("gamebub-v20-"):
                    return SimpleNamespace(returncode=2 if Path(command[-1]).suffix == ".af03" else 1, stdout="", stderr="rejected")
                if command[1] == "--inverse":
                    report = {"scope": "inverse_only", "blocks": 1, "samples": 64}
                else:
                    report = {"scope": "envelope_only", "bytes": 65 if command[1] == "--ar03" else 43}
                return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "AF03 corruption"):
                verify.verify_fixtures(root, exe, runner=bad_af03_negative, expected_inverse_datasets=1, expected_envelopes=1)

            def af03_spawn_failure(command, **_kwargs):
                if Path(command[-1]).name.startswith("gamebub-v20-") and Path(command[-1]).suffix == ".af03":
                    raise OSError("cannot execute")
                if Path(command[-1]).name.startswith("gamebub-v20-"):
                    return SimpleNamespace(returncode=1, stdout="", stderr="rejected")
                if command[1] == "--inverse":
                    report = {"scope": "inverse_only", "blocks": 1, "samples": 64}
                else:
                    report = {"scope": "envelope_only", "bytes": 65 if command[1] == "--ar03" else 43}
                return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")
            with self.assertRaisesRegex(verify.VerificationError, "negative envelope check"):
                verify.verify_fixtures(root, exe, runner=af03_spawn_failure, expected_inverse_datasets=1, expected_envelopes=1)

    def test_main_writes_report_and_reports_errors(self):
        """@brief Cover the command-line report write and useful error path."""
        report = {"scope": {"inverse": "inverse_only", "envelopes": "envelope_only"}}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested/report.json"
            with patch.object(verify, "verify_fixtures", return_value=report), patch("sys.stdout"):
                self.assertEqual(verify.main(["--fixtures", "f", "--executable", "x", "--report", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)
            with patch.object(verify, "verify_fixtures", side_effect=verify.VerificationError("bad fixtures")), self.assertRaises(SystemExit) as caught:
                verify.main(["--fixtures", "f", "--executable", "x", "--report", str(output)])
            self.assertEqual(caught.exception.code, 2)

            output.write_text("preserve", encoding="utf-8")
            with patch.object(verify, "verify_fixtures", return_value=report), patch("sys.stdout"), self.assertRaises(SystemExit) as caught:
                verify.main(["--fixtures", "f", "--executable", "x", "--report", str(output)])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

        with patch("sys.argv", ["verify_v20_native.py", "--help"]), patch("sys.stdout"), self.assertRaises(SystemExit) as caught:
            runpy.run_path(verify.__file__, run_name="__main__")
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
