"""@brief Exercise native encoder harness trust boundaries without a device or compiler."""

import copy
import hashlib
import json
import runpy
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verify_v20_encoder as v
from test_verify_v20_body import make_case


def fixture(root, mandatory=True):
    """@brief Build one self-contained hashed oracle for mocked process tests."""
    path, case, exe = make_case(root, "mandatory" if mandatory else "baseline")
    case["scene"] = "scene"
    case["geometry"] = {"width": 720, "height": 480}
    rgb = bytes(1036800)
    (path.parent / case["source_rgb"]["path"]).write_bytes(rgb)
    case["source_rgb"].update(
        bytes=len(rgb), shape=[480, 720, 3], sha256=hashlib.sha256(rgb).hexdigest()
    )
    packet = bytearray(115)
    packet[:6] = b"AR03\x03\x01"
    struct.pack_into("<I", packet, 6, 1)
    packet[14] = 255
    struct.pack_into("<I", packet, 16, 0xFFFFFFFF)
    struct.pack_into("<I", packet, 52, 50)
    (path.parent / case["packet"]["path"]).write_bytes(packet)
    case["packet"].update(bytes=len(packet), sha256=hashlib.sha256(packet).hexdigest())
    case.update(key=True, promoted=False, selected_rectangles=[], epoch=1)
    case["encoder_oracle"] = {
        "inner_bytes": 50,
        "patch_bytes": 0,
        "packet_bytes": 115,
        "packet_sha256": case["packet"]["sha256"],
        "key": True,
        "promoted": False,
        "selected_profile": [8, 16],
        "roi_quantmap": {"roi_scale": 8, "background_scale": 16},
        "reference": {
            "bank": 255,
            "id": 0xFFFFFFFF,
            "tag": "00" * 16,
            "geometry": {"width": 720, "height": 480},
        },
        "destination": {"bank": 0, "tag": "00" * 16},
        "attempts": [
            {
                "roi_scale": 8,
                "background_scale": 16,
                "attempted_complete_bytes": 115,
                "accepted": True,
            }
        ],
    }
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["schema"] = v.MANIFEST_SCHEMA
    row = manifest["cases"][0]
    row.update(scene="scene", packet_sha256=case["packet"]["sha256"])
    save(root, path, case, manifest)
    report = {
        "scope": "native_encoder_fixture",
        "label": case["label"],
        "id": 0,
        "inner_bytes": 50,
        "packet_bytes": 115,
        "selected_patch_count": 0,
        "inner_byte_exact": True,
        "patches_byte_exact": True,
        "ar03_byte_exact": True,
        "profiling_not_playback": True,
        "mandatory_policy_verified": mandatory,
        "policy_attempts": (
            [
                {
                    "roi": 8,
                    "background": 16,
                    "complete_bytes": 115,
                    "accepted": True,
                    "build_ns": 3,
                    "validation_ns": 2,
                    "discard_ns": 0,
                }
            ]
            if mandatory
            else []
        ),
        "frozen_decode": {
            "scope": "full_body_fixture",
            "label": case["label"],
            "id": 0,
            "yuv_samples": 518400,
            "display_words": 345600,
            "mandatory_hud_words_verified": 21120 if mandatory else 0,
            "af03_exact": True,
            "post_banks_exact": True,
        },
    }
    return path, case, exe, manifest, report


def save(root, path, case, manifest):
    """@brief Refresh only intended metadata hashes after a controlled mutation."""
    path.write_text(json.dumps(case))
    manifest["cases"][0]["case_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest))


class EncoderVerifierTests(unittest.TestCase):
    """@brief Reject malformed evidence before trusting child success flags."""

    def setUp(self):
        """@brief Isolate each harness invocation and its exclusive output files."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path, self.case, self.exe, self.manifest, self.report = fixture(self.root)

    def run_verify(self, **kwargs):
        """@brief Supply a deterministic successful native report unless overridden."""
        runner = kwargs.pop(
            "runner", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(self.report))
        )
        kwargs.setdefault(
            "expected_source_results_sha256",
            hashlib.sha256((self.root / "source-results.json").read_bytes()).hexdigest(),
        )
        return v.verify(self.root, self.exe, expected_cases=1, runner=runner, **kwargs)

    def test_success_and_baseline(self):
        result = self.run_verify()
        self.assertEqual(result["policy_attempt_count"], 1)
        self.assertEqual(
            result["policy_cost_ns"], {"build_ns": 3, "validation_ns": 2, "discard_ns": 0}
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, exe, _, report = fixture(root, False)
            result = v.verify(
                root,
                exe,
                expected_cases=1,
                expected_source_results_sha256=hashlib.sha256(
                    (root / "source-results.json").read_bytes()
                ).hexdigest(),
                runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(report)),
            )
            self.assertEqual(result["mandatory_case_count"], 0)

    def test_integer_bounds(self):
        for value in (True, -1, 2**63, 1.0, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                v.integer(value)

    def test_manifest_failures(self):
        for key, value in (
            ("schema", "wrong"),
            ("source_commit", "wrong"),
            ("source_results_sha256", "wrong"),
            ("cases", []),
            ("cases", None),
        ):
            data = copy.deepcopy(self.manifest)
            data[key] = value
            (self.root / "manifest.json").write_text(json.dumps(data))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_verify()
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            v.verify(self.root, self.root, expected_cases=1)
        source = self.root / "source-results.json"
        with source.open("r+b") as stream:
            stream.truncate(16 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "source-results hash"):
            self.run_verify()

    def test_duplicate_cases_rejected_before_child(self):
        self.manifest["cases"] *= 2
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            v.verify(
                self.root,
                self.exe,
                expected_cases=2,
                expected_source_results_sha256=hashlib.sha256(
                    (self.root / "source-results.json").read_bytes()
                ).hexdigest(),
                runner=lambda *a, **k: self.fail("child ran"),
            )

    def test_requires_ten_mandatory_cases_in_full_campaign(self):
        self.manifest["cases"] *= 20
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "ten mandatory"):
            v.verify(
                self.root,
                self.exe,
                expected_source_results_sha256=hashlib.sha256(
                    (self.root / "source-results.json").read_bytes()
                ).hexdigest(),
                runner=lambda *a, **k: self.fail("child ran"),
            )

    def test_default_pinned_source_results_hash_rejects_self_consistent_tamper(self):
        """@brief Reject substituted source-results even when attacker updates its manifest hash."""
        source = self.root / "source-results.json"
        changed = source.read_bytes() + b" "
        source.write_bytes(changed)
        self.manifest["source_results_sha256"] = hashlib.sha256(changed).hexdigest()
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "source-results hash"):
            v.verify(self.root, self.exe, expected_cases=1)

    def test_unsafe_path_and_hashes(self):
        row = self.manifest["cases"][0]
        row["case_path"] = "../outside.json"
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            self.run_verify()
        row["case_path"] = "cases/case.json"
        row["case_sha256"] = "wrong"
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, "metadata hash"):
            self.run_verify()
        save(self.root, self.path, self.case, self.manifest)
        descriptor = self.case["source_rgb"]
        (self.path.parent / descriptor["path"]).write_bytes(b"short")
        with self.assertRaisesRegex(ValueError, "byte count"):
            self.run_verify()
        (self.path.parent / descriptor["path"]).write_bytes(bytes([1]) * descriptor["bytes"])
        with self.assertRaisesRegex(ValueError, "raw fixture hash"):
            self.run_verify()

    def test_case_preflight_mutations(self):
        mutations = [
            lambda c: c.update(schema="wrong"),
            lambda c: c["source_rgb"].update(dtype="<u2"),
            lambda c: c["encoder_oracle"].update(inner_bytes=49),
            lambda c: c["encoder_oracle"].update(key=False),
            lambda c: c["encoder_oracle"].update(selected_profile=[1, 1]),
            lambda c: c["encoder_oracle"].update(attempts=[]),
            lambda c: c["encoder_oracle"]["attempts"][0].update(accepted=False),
            lambda c: c["encoder_oracle"]["attempts"][0].update(roi_scale=16),
            lambda c: c["encoder_oracle"]["attempts"][0].update(attempted_complete_bytes=116),
        ]
        for mutate in mutations:
            case = copy.deepcopy(self.case)
            mutate(case)
            save(self.root, self.path, case, self.manifest)
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.run_verify(runner=lambda *a, **k: self.fail("child ran"))
        case = copy.deepcopy(self.case)
        packet = self.path.parent / case["packet"]["path"]
        packet.write_bytes(b"bad")
        case["packet"].update(bytes=3, sha256=hashlib.sha256(b"bad").hexdigest())
        self.manifest["cases"][0]["packet_sha256"] = case["packet"]["sha256"]
        save(self.root, self.path, case, self.manifest)
        with self.assertRaisesRegex(ValueError, "header"):
            self.run_verify()

    def test_process_failure_and_options(self):
        def runner(command, **options):
            self.assertEqual(command[1], "--encoder-case")
            self.assertEqual(
                options, {"capture_output": True, "text": True, "timeout": 60, "check": False}
            )
            return SimpleNamespace(returncode=1, stderr="failure")

        with self.assertRaisesRegex(ValueError, "Native encoder failed"):
            self.run_verify(runner=runner)

    def test_duplicated_oracle_mutations_reject_before_child(self):
        changes = [
            ("reference", "bank", 0),
            ("reference", "bank", True),
            ("reference", "id", 1),
            ("reference", "id", False),
            ("reference", "tag", "11" * 16),
            ("destination", "bank", 1),
            ("destination", "bank", False),
            ("destination", "tag", "11" * 16),
            ("roi_quantmap", "roi_scale", 16),
            ("roi_quantmap", "roi_scale", True),
            ("roi_quantmap", "background_scale", 32),
            ("roi_quantmap", "background_scale", False),
        ]
        for section, field, value in changes:
            case = copy.deepcopy(self.case)
            case["encoder_oracle"][section][field] = value
            save(self.root, self.path, case, self.manifest)
            with (
                self.subTest(section=section, field=field, value=value),
                self.assertRaises(ValueError),
            ):
                self.run_verify(runner=lambda *a, **k: self.fail("child ran"))
        for field, value in (("width", 718), ("height", 478), ("width", True), ("height", False)):
            case = copy.deepcopy(self.case)
            case["encoder_oracle"]["reference"]["geometry"][field] = value
            save(self.root, self.path, case, self.manifest)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.run_verify(runner=lambda *a, **k: self.fail("child ran"))

    def test_packet_epoch_frame_identity_checked_before_child(self):
        for epoch in (2, True):
            case = copy.deepcopy(self.case)
            case["epoch"] = epoch
            save(self.root, self.path, case, self.manifest)
            with self.subTest(epoch=epoch), self.assertRaises(ValueError):
                self.run_verify(runner=lambda *a, **k: self.fail("child ran"))
        case = copy.deepcopy(self.case)
        case["id"] = 1
        self.manifest["cases"][0]["id"] = 1
        save(self.root, self.path, case, self.manifest)
        with self.assertRaisesRegex(ValueError, "epoch/frame"):
            self.run_verify(runner=lambda *a, **k: self.fail("child ran"))

    def test_report_failures(self):
        mutations = [
            lambda r: r.update(scope="wrong"),
            lambda r: r.update(inner_byte_exact=1),
            lambda r: r.update(mandatory_policy_verified=False),
            lambda r: r["frozen_decode"].update(scope="wrong"),
            lambda r: r["frozen_decode"].update(af03_exact=False),
            lambda r: r.update(policy_attempts=[]),
            lambda r: r["policy_attempts"][0].update(roi=16),
            lambda r: r["policy_attempts"][0].update(build_ns=-1),
        ]
        for mutate in mutations:
            report = copy.deepcopy(self.report)
            mutate(report)
            with self.subTest(report=report), self.assertRaises(ValueError):
                v.check_report(report, self.case)
        with self.assertRaises(ValueError):
            v.check_report([], self.case)

    def test_main_exclusive_output_and_errors(self):
        output = self.root / "nested/report.json"
        args = [
            "--fixtures",
            str(self.root),
            "--executable",
            str(self.exe),
            "--report",
            str(output),
        ]
        with patch.object(v, "verify", return_value={"cases": []}), patch("builtins.print"):
            self.assertEqual(v.main(args), 0)
        with (
            patch.object(v, "verify", side_effect=AssertionError("must not run")),
            self.assertRaises(SystemExit),
        ):
            v.main(args)
        output.unlink()
        with (
            patch.object(v, "verify", side_effect=ValueError("bad")),
            self.assertRaises(SystemExit),
        ):
            v.main(args)
        with patch.object(sys, "argv", ["verify_v20_encoder"]), self.assertRaises(SystemExit):
            runpy.run_module("verify_v20_encoder", run_name="__main__")


if __name__ == "__main__":
    unittest.main()
