"""@brief Test safe normalization of pinned v20 encoder fixture metadata."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_v20_encoder_cases as normalizer


def digest(raw: bytes) -> str:
    """@brief Hash fixture bytes as SHA-256."""
    return hashlib.sha256(raw).hexdigest()


def prepare_fixture(source: Path, output: Path, **kwargs) -> dict:
    """@brief Pin test exports to their constructed source bytes without changing CLI defaults."""
    kwargs.setdefault(
        "expected_source_results_sha256", digest((source / "source-results.json").read_bytes())
    )
    return normalizer.prepare(source, output, **kwargs)


def write_fixture(root: Path) -> None:
    """@brief Build a minimal byte-hashed source export with one encoder decision."""
    cases_dir = root / "cases"
    cases_dir.mkdir(parents=True)
    case = {
        "scene": "scene-a", "policy": "mandatory", "id": 3, "untouched": [1, 2],
        "geometry": {"width": 720, "height": 480}, "key": True, "promoted": False,
        "state": {
            "reference_bank": 255, "reference_id": 4294967295,
            "reference_tag": "0" * 32, "destination_bank": 0, "stored_tag": "a" * 32,
        },
    }
    byte_files = {
        "packet": ("case.ar03", b"packet"),
        "ack": ("case.af03", b"ack"),
        "source_rgb": ("case.rgb", b"rgb"),
        "display_rgb565": ("case.rgb565", b"565"),
    }
    for field, (name, raw) in byte_files.items():
        (cases_dir / name).write_bytes(raw)
        case[field] = {"path": name, "bytes": len(raw), "sha256": digest(raw)}
    case["decoded_yuv"] = []
    for index, raw in enumerate((b"y", b"u", b"v")):
        name = f"case.yuv{index}"
        (cases_dir / name).write_bytes(raw)
        case["decoded_yuv"].append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    case["pre_banks"] = {"0": None, "1": None}
    case_raw = json.dumps(case, indent=2).encode() + b"\n"
    (cases_dir / "case.json").write_bytes(case_raw)
    source_case = {
        "scene": "scene-a",
        "policy": "mandatory",
        "manifest": {"target_width": 720, "target_height": 480},
        "vectors": [{"id": 3, "key": True, "promoted": False}],
        "rows": [{
            "id": 3, "selected_profile": [8, 32], "inner_bytes": 1200,
            "patch_bytes": 800, "packet_bytes": len(b"packet"),
            "candidate_control_id": 17, "key": True, "promoted": False,
            "reference_bank": 255, "reference_id": 4294967295,
            "reference_tag": "0" * 32, "destination_bank": 0,
            "stored_tag": "a" * 32, "packet_sha256": digest(b"packet"),
            "attempts": [
                {"roi_scale": 8, "background_scale": 16, "attempted_complete_bytes": 50000, "accepted": False},
                {"roi_scale": 8, "background_scale": 32, "attempted_complete_bytes": 2050, "accepted": True},
            ],
        }],
    }
    results_raw = json.dumps({"schema": "gamebub-mandatory-hud-v1", "cases": [source_case]}).encode()
    (root / "source-results.json").write_bytes(results_raw)
    manifest = {
        "schema": "gamebub-v20-body-fixtures-v1",
        "source_commit": normalizer.PINNED_SOURCE_COMMIT,
        "source_results_sha256": digest(results_raw),
        "cases": [{"case_path": "cases/case.json", "case_sha256": digest(case_raw)}],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "extra.bin").write_bytes(b"original bytes")


def oracle_data() -> tuple[dict, dict]:
    """@brief Construct minimal pinned encoder row and matching vector metadata."""
    return (
        {
            "manifest": {"target_width": 720, "target_height": 480},
            "rows": [{
                "id": 3, "selected_profile": [8, 32], "inner_bytes": 1200,
                "patch_bytes": 800, "packet_bytes": 2050,
                "candidate_control_id": 17, "key": True, "promoted": False,
                "reference_bank": 255, "reference_id": 4294967295,
                "reference_tag": "0" * 32, "destination_bank": 0,
                "stored_tag": "a" * 32, "packet_sha256": "b" * 64,
                "attempts": [
                    {"roi_scale": 8, "background_scale": 16, "attempted_complete_bytes": 50000, "accepted": False},
                    {"roi_scale": 8, "background_scale": 32, "attempted_complete_bytes": 2050, "accepted": True},
                ],
            }],
        },
        {"id": 3, "key": True, "promoted": False},
    )


class EncoderCaseNormalizationTest(unittest.TestCase):
    """@brief Verify source integrity, byte preservation, oracle extraction, and path safety."""

    def test_normalizes_profile_attempts_and_provenance_without_changing_source(self):
        """@brief Copy original files and attach the selected quantmap/promotion oracle."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "derived"
            source.mkdir()
            write_fixture(source)
            original = (source / "cases/case.json").read_bytes()
            manifest = prepare_fixture(source, output, expected_cases=1)
            case = json.loads((output / "cases/case.json").read_text(encoding="utf-8"))
            oracle = case["encoder_oracle"]
            self.assertEqual((source / "cases/case.json").read_bytes(), original)
            self.assertFalse((output / "extra.bin").exists())
            self.assertEqual((output / "cases/case.ar03").read_bytes(), b"packet")
            self.assertEqual(oracle["roi_quantmap"], {"roi_scale": 8, "background_scale": 32})
            self.assertEqual(oracle["selected_profile"], [8, 32])
            self.assertEqual(oracle["candidate_control_id"], 17)
            self.assertEqual(oracle["reference"]["geometry"], {"width": 720, "height": 480})
            self.assertEqual(oracle["attempts"], [
                {"roi_scale": 8, "background_scale": 16, "attempted_complete_bytes": 50000, "accepted": False},
                {"roi_scale": 8, "background_scale": 32, "attempted_complete_bytes": 2050, "accepted": True},
            ])
            self.assertEqual(manifest["schema"], "gamebub-v20-encoder-cases-v1")
            self.assertEqual(manifest["body_manifest_sha256"], digest((source / "manifest.json").read_bytes()))
            self.assertEqual(manifest["cases"][0]["case_sha256"], digest((output / "cases/case.json").read_bytes()))

    def test_refuses_tampered_source_result_hash_and_leaves_no_output(self):
        """@brief Verify the original pinned source-results digest before writing output."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "derived"
            source.mkdir()
            write_fixture(source)
            (source / "source-results.json").write_text(
                '{"schema":"gamebub-mandatory-hud-v1","cases":[]}', encoding="utf-8"
            )
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "source-results hash"):
                prepare_fixture(source, output, expected_cases=1)
            self.assertFalse(output.exists())

    def test_default_pin_rejects_self_consistent_source_results_tamper(self):
        """@brief Do not accept a changed source-results file just because its manifest was edited."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "derived"
            source.mkdir()
            write_fixture(source)
            results_path = source / "source-results.json"
            changed = results_path.read_bytes() + b" "
            results_path.write_bytes(changed)
            manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
            manifest["source_results_sha256"] = digest(changed)
            (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "pinned source-results hash"):
                normalizer.prepare(source, output, expected_cases=1)
            self.assertFalse(output.exists())

    def test_refuses_tampered_case_hash(self):
        """@brief Prevent normalizing a modified exported case."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "derived"
            source.mkdir()
            write_fixture(source)
            (source / "cases/case.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "case digest"):
                prepare_fixture(source, output, expected_cases=1)
            self.assertTrue(output.exists())
            self.assertFalse((output / "manifest.json").exists())

    def test_rejects_unsafe_case_path_and_preexisting_output(self):
        """@brief Reject traversal paths and never overwrite an existing destination."""
        self.assertEqual(normalizer._safe_relative("cases/a.json").as_posix(), "cases/a.json")
        for unsafe in ("../outside", "/absolute", "cases\\escape", ""):
            with self.subTest(path=unsafe), self.assertRaises(normalizer.EncoderCaseError):
                normalizer._safe_relative(unsafe)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "derived"
            source.mkdir()
            output.mkdir()
            write_fixture(source)
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "new directory"):
                prepare_fixture(source, output)

    def test_json_and_row_helpers_reject_invalid_shapes_and_identity(self):
        """@brief Cover malformed JSON values and missing/ambiguous source decision rows."""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            for raw, message in ((b"\xff", "invalid JSON"), (b"[]", "expected JSON object")):
                path.write_bytes(raw)
                with self.subTest(raw=raw), self.assertRaisesRegex(normalizer.EncoderCaseError, message):
                    normalizer._json(path)
        for case in ({}, {"rows": []}, {"rows": [{"id": 3}, {"id": 3}]}):
            with self.subTest(case=case), self.assertRaises(normalizer.EncoderCaseError):
                normalizer._case_row(case, {"id": 3})
        for unsafe in (None, "a:b", "a\0b", "cases//double"):
            with self.assertRaises(normalizer.EncoderCaseError):
                normalizer._safe_relative(unsafe)
        with self.assertRaisesRegex(normalizer.EncoderCaseError, "invalid relative artifact path"):
            normalizer._safe_relative(None)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "large.json"
            path.write_bytes(b"{} ")
            with patch.object(normalizer, "MAX_CASE_BYTES", 2), self.assertRaisesRegex(
                normalizer.EncoderCaseError, "size limit"
            ):
                normalizer._json(path)

    def test_descendant_and_descriptor_helpers_confine_and_validate_files(self):
        """@brief Bound declared data paths and reject symlink escapes and malformed arrays."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "file.bin").write_bytes(b"x")
            (root / "subdir").mkdir()
            self.assertEqual(normalizer._descendant(root, "file.bin"), root / "file.bin")
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "regular file"):
                normalizer._descendant(root, "subdir")
            outside = Path(temporary) / "outside.bin"
            outside.write_bytes(b"outside")
            original_resolve = Path.resolve

            def resolve_escape(path, *args, **kwargs):
                if path.name == "link.bin":
                    return outside
                return original_resolve(path, *args, **kwargs)

            with (
                patch.object(Path, "resolve", autospec=True, side_effect=resolve_escape),
                self.assertRaisesRegex(normalizer.EncoderCaseError, "escapes source root"),
            ):
                normalizer._descendant(root, "link.bin")
        case = {
            "packet": {"path": "p", "bytes": 0, "sha256": "0" * 64},
            "ack": {"path": "a", "bytes": 0, "sha256": "0" * 64},
            "source_rgb": {"path": "s", "bytes": 0, "sha256": "0" * 64},
            "display_rgb565": {"path": "d", "bytes": 0, "sha256": "0" * 64},
            "decoded_yuv": [], "pre_banks": {"0": None, "1": None},
        }
        self.assertEqual(len(normalizer._descriptors(case)), 4)
        with_bank = {**case, "pre_banks": {"0": {"planes": [case["packet"]]}, "1": None}}
        self.assertEqual(len(normalizer._descriptors(with_bank)), 5)
        for invalid in (
            {**case, "decoded_yuv": None},
            {**case, "pre_banks": []},
            {**case, "pre_banks": {"0": {"planes": None}, "1": None}},
            {**case, "packet": None},
            {**case, "packet": {"path": "p", "bytes": True, "sha256": "0" * 64}},
            {**case, "packet": {"path": "../p", "bytes": 1, "sha256": "0" * 64}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(normalizer.EncoderCaseError):
                normalizer._descriptors(invalid)

    def test_precondition_helper_checks_geometry_identity_flags_and_reference_banks(self):
        """@brief Reject source/body mismatch in geometry, bank identity, key flags, or preloads."""
        source_case, vector = oracle_data()
        case = {
            "state": {
                "reference_bank": 255, "reference_id": 4294967295, "reference_tag": "0" * 32,
                "destination_bank": 0, "stored_tag": "a" * 32,
            },
            "geometry": {"width": 720, "height": 480}, "key": True, "promoted": False,
            "pre_banks": {"0": None, "1": None},
        }
        row = source_case["rows"][0]
        normalizer._validate_preconditions(case, source_case, vector, row)
        invalids = [
            {**case, "state": None},
            {**case, "geometry": {"width": 1, "height": 1}},
            {**case, "state": {**case["state"], "reference_tag": "c" * 32}},
            {**case, "key": False},
        ]
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(normalizer.EncoderCaseError):
                normalizer._validate_preconditions(invalid, source_case, vector, row)
        p_row = {**row, "reference_bank": 0, "reference_id": 9, "reference_tag": "c" * 32}
        p_case = {
            **case,
            "state": {**case["state"], "reference_bank": 0, "reference_id": 9, "reference_tag": "c" * 32},
            "pre_banks": {"0": {"id": 8, "tag": "c" * 32}, "1": None},
        }
        with self.assertRaisesRegex(normalizer.EncoderCaseError, "bank precondition"):
            normalizer._validate_preconditions(p_case, source_case, vector, p_row)
        p_case["pre_banks"]["0"] = {"id": 9, "tag": "c" * 32}
        normalizer._validate_preconditions(p_case, source_case, vector, p_row)
        p_case["pre_banks"]["0"]["tag"] = "d" * 32
        with self.assertRaisesRegex(normalizer.EncoderCaseError, "bank precondition"):
            normalizer._validate_preconditions(p_case, source_case, vector, p_row)

    def test_oracle_rejects_each_required_decision_field_and_attempt(self):
        """@brief Validate profiles, sizes, identities, flags, and ordered attempt facts."""
        source_case, vector = oracle_data()
        row = source_case["rows"][0]
        invalid_rows = [
            {"selected_profile": [8]},
            {"inner_bytes": True},
            {"reference_tag": "not-a-tag"},
            {"packet_sha256": "b" * 32},
            {"promoted": 0},
            {"attempts": None},
            {"attempts": [None]},
            {"attempts": [{"roi_scale": 0, "background_scale": 32, "attempted_complete_bytes": 10, "accepted": True}]},
            {"attempts": [{"roi_scale": 8, "background_scale": 32, "attempted_complete_bytes": 10, "accepted": 1}]},
        ]
        for update in invalid_rows:
            with self.subTest(update=update):
                broken = dict(row)
                broken.update(update)
                source_case["rows"] = [broken]
                with self.assertRaises(normalizer.EncoderCaseError):
                    normalizer._oracle(source_case, vector)
        source_case["rows"] = [row]
        with self.assertRaisesRegex(normalizer.EncoderCaseError, "decision row"):
            normalizer._oracle(source_case, {"id": 99})

    def test_prepare_rejects_wrong_pin_index_and_vector_metadata_and_cleans_output(self):
        """@brief Reject incompatible source/schema linkage and remove partial derived exports."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for mutation, message, created in (
                (lambda manifest, results: manifest.update(source_commit="0" * 40), "unsupported fixture schema", False),
                (lambda manifest, results: results.update(schema="wrong"), "unsupported fixture schema", False),
                (lambda manifest, results: manifest.update(cases=[None]), "invalid fixture index row", True),
                (lambda manifest, results: manifest.update(cases=[{"case_path": "../escape", "case_sha256": "x"}]), "unsafe relative artifact path", True),
            ):
                source = root / f"src-{len(list(root.iterdir()))}"
                output = root / f"out-{len(list(root.iterdir()))}"
                source.mkdir()
                write_fixture(source)
                manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
                results = json.loads((source / "source-results.json").read_text(encoding="utf-8"))
                mutation(manifest, results)
                results_raw = json.dumps(results).encode()
                (source / "source-results.json").write_bytes(results_raw)
                manifest["source_results_sha256"] = digest(results_raw)
                (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.subTest(message=message), self.assertRaisesRegex(normalizer.EncoderCaseError, message):
                    prepare_fixture(source, output, expected_cases=1)
                self.assertEqual(output.exists(), created)
                self.assertFalse((output / "manifest.json").exists())

    def test_prepare_rejects_unmatched_source_and_duplicate_vector_after_creation(self):
        """@brief Leave an incomplete directory without a manifest when metadata matching fails."""
        for duplicate in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, output = root / "source", root / "output"
                source.mkdir()
                write_fixture(source)
                results = json.loads((source / "source-results.json").read_text(encoding="utf-8"))
                if duplicate:
                    results["cases"][0]["vectors"].append(results["cases"][0]["vectors"][0])
                    expected = "pinned vector"
                else:
                    results["cases"][0]["scene"] = "other"
                    expected = "pinned source case"
                raw = json.dumps(results).encode()
                (source / "source-results.json").write_bytes(raw)
                manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
                manifest["source_results_sha256"] = digest(raw)
                (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(normalizer.EncoderCaseError, expected):
                    prepare_fixture(source, output, expected_cases=1)
                self.assertTrue(output.exists())
                self.assertFalse((output / "manifest.json").exists())

    def test_prepare_rejects_count_policy_blob_and_packet_crosscheck(self):
        """@brief Enforce 20-case policy and integrity ties across descriptors, rows, and packets."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            write_fixture(source)
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "case count"):
                prepare_fixture(source, root / "count")
            changes = (
                ("body-policy", lambda case, manifest, results: case.update(policy="bad"), "body case policy"),
                ("source-policy", lambda case, manifest, results: results["cases"][0].update(policy="bad"), "source case policy"),
                ("data-hash", lambda case, manifest, results: None, "length/hash"),
                ("packet-row", lambda case, manifest, results: results["cases"][0]["rows"][0].update(packet_bytes=100), "packet oracle"),
            )
            for name, change, expected in changes:
                fixture = root / name
                fixture.mkdir()
                write_fixture(fixture)
                case_path = fixture / "cases/case.json"
                case = json.loads(case_path.read_text(encoding="utf-8"))
                manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
                results = json.loads((fixture / "source-results.json").read_text(encoding="utf-8"))
                change(case, manifest, results)
                if name == "data-hash":
                    (fixture / "cases/case.rgb").write_bytes(b"bad")
                if name == "body-policy":
                    case_path.write_text(json.dumps(case), encoding="utf-8")
                    manifest["cases"][0]["case_sha256"] = digest(case_path.read_bytes())
                if name != "data-hash":
                    raw = json.dumps(results).encode()
                    (fixture / "source-results.json").write_bytes(raw)
                    manifest["source_results_sha256"] = digest(raw)
                (fixture / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.subTest(name=name), self.assertRaisesRegex(normalizer.EncoderCaseError, expected):
                    prepare_fixture(fixture, root / f"output-{name}", expected_cases=1)

    def test_prepare_rejects_malformed_source_case_index(self):
        """@brief Reject a non-list source case index before copying any files."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            write_fixture(source)
            results = {"schema": "gamebub-mandatory-hud-v1", "cases": None}
            raw = json.dumps(results).encode()
            (source / "source-results.json").write_bytes(raw)
            manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
            manifest["source_results_sha256"] = digest(raw)
            (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(normalizer.EncoderCaseError, "source case index"):
                prepare_fixture(source, root / "output", expected_cases=1)

    def test_command_entrypoint_writes_json_summary(self):
        """@brief Exercise argument parsing and summary output without weakening the production pin."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "source", root / "output"
            source.mkdir()
            write_fixture(source)
            expected_hash = digest((source / "source-results.json").read_bytes())
            with (
                contextlib.redirect_stdout(io.StringIO()) as captured,
                patch.object(normalizer.common, "PINNED_SOURCE_RESULTS_SHA256", expected_hash),
                patch.object(
                    sys,
                    "argv",
                    ["prepare_v20_encoder_cases.py", "--source", str(source), "--output", str(output), "--expected-cases", "1"],
                ),
                self.assertRaises(SystemExit) as exit_info,
            ):
                runpy.run_module("prepare_v20_encoder_cases", run_name="__main__")
            self.assertEqual(exit_info.exception.code, 0)
            self.assertEqual(json.loads(captured.getvalue())["cases"], 1)
            self.assertTrue((output / "manifest.json").exists())
        with patch.object(sys, "argv", ["prepare_v20_encoder_cases.py"]), self.assertRaises(SystemExit):
            runpy.run_module("prepare_v20_encoder_cases", run_name="__main__")


if __name__ == "__main__":
    unittest.main()
