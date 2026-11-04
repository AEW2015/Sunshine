"""@brief Test safe export and validation of complete GameBub body fixtures."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_v20_body_fixtures as body


def descriptor(raw: bytes, dtype: str, shape: list[int]) -> dict:
    """@brief Build a raw content-addressed array descriptor for exporter tests."""
    return {"dtype": dtype, "shape": shape, "blob": {"raw_bytes": len(raw)}}


def fixture_results() -> dict:
    """@brief Construct all 20 compact decoder vectors for complete export tests."""
    cases = []
    for scene, policy in (
        ("scene-a", "baseline"),
        ("scene-a", "mandatory"),
        ("scene-b", "baseline"),
        ("scene-b", "mandatory"),
    ):
        vectors, rows = [], []
        for frame_id in range(5):
            raw_rgb, raw_y, raw_c, raw_rgb565 = bytes(12), bytes(8), bytes(2), bytes(8)
            vectors.append(
                {
                    "id": frame_id,
                    "key": frame_id == 0,
                    "promoted": False,
                    "packet": {"raw": b"P".hex()},
                    "ack": {"raw": (b"A" * 43).hex()},
                    "source": {
                        "dtype": "|u1",
                        "shape": [2, 2, 3],
                        "blob": {"raw_bytes": len(raw_rgb), "raw": raw_rgb.hex()},
                    },
                    "decoded_yuv": [
                        {
                            "dtype": "<i2",
                            "shape": [2, 2],
                            "blob": {"raw_bytes": len(raw_y), "raw": raw_y.hex()},
                        },
                        {
                            "dtype": "<i2",
                            "shape": [1, 1],
                            "blob": {"raw_bytes": len(raw_c), "raw": raw_c.hex()},
                        },
                        {
                            "dtype": "<i2",
                            "shape": [1, 1],
                            "blob": {"raw_bytes": len(raw_c), "raw": raw_c.hex()},
                        },
                    ],
                    "display_rgb565": {
                        "dtype": "<u2",
                        "shape": [2, 2],
                        "blob": {"raw_bytes": len(raw_rgb565), "raw": raw_rgb565.hex()},
                    },
                    "pre_banks": {"0": None, "1": None},
                    "post_banks": {"0": {"id": frame_id, "tag": "a" * 32}, "1": None},
                    "selected_rectangles": [],
                    "omitted_rectangles": [],
                    "rgb_sha256": "b" * 64,
                }
            )
            rows.append(
                {
                    "id": frame_id,
                    "reference_bank": 255,
                    "reference_id": 0xFFFFFFFF,
                    "reference_tag": "0" * 32,
                    "destination_bank": 0,
                    "stored_tag": "a" * 32,
                    "state_before": {"last_issued": frame_id - 1},
                }
            )
        cases.append(
            {
                "scene": scene,
                "policy": policy,
                "manifest": {"target_width": 2, "target_height": 2},
                "rows": rows,
                "vectors": vectors,
            }
        )
    return {"schema": "gamebub-mandatory-hud-v1", "cases": cases}


class BodyFixtureExportTest(unittest.TestCase):
    """@brief Cover supported shapes, exact byte preservation, and unsafe metadata rejection."""

    def test_array_shape_checks_explicit_dtype_dimensions_and_byte_count(self):
        """@brief Enforce shape-derived raw lengths and the accepted explicit dtype set."""
        valid = descriptor(bytes(12), "<i2", [2, 3])
        self.assertEqual(body._array_shape(valid, "test"), ("<i2", [2, 3], 12))
        for invalid in (
            None,
            {**valid, "dtype": "=i2"},
            {**valid, "shape": [2, 0]},
            {**valid, "shape": [True, 3]},
            {**valid, "blob": []},
            {**valid, "blob": {"raw_bytes": 10}},
            {"dtype": "<i2", "shape": [5000], "blob": {"raw_bytes": 10000}},
            {"dtype": "<i2", "shape": [4096, 4096, 3], "blob": {"raw_bytes": 100663296}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(body.BodyFixtureError):
                body._array_shape(invalid, "test")

    def test_array_helpers_reject_wrong_return_size_and_geometry(self):
        """@brief Reject blob lengths and normalized shapes that disagree with descriptors."""
        exporter = body.BodyExporter(Path("moon"))
        exporter._blob = lambda *_args, **_kwargs: b"x"
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(body.BodyFixtureError):
            body._array(exporter, descriptor(bytes(2), "<i2", [1]), Path(temporary), "a", "case")
        with self.assertRaises(body.BodyFixtureError):
            body._require_array_shape({"dtype": "<i2", "shape": [1]}, "<u2", [1], "case")

    def test_array_writes_raw_bytes_and_records_digest(self):
        """@brief Preserve raw little-endian bytes and describe their content hash."""
        raw = b"\x01\x00\xff\x7f"
        exporter = body.BodyExporter(Path("moon"))
        exporter._blob = lambda *_args, **_kwargs: raw
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = body._array(exporter, descriptor(raw, "<i2", [2]), root, "input", "case")
            self.assertEqual((root / "input.bin").read_bytes(), raw)
        self.assertEqual(
            result,
            {
                "dtype": "<i2",
                "shape": [2],
                "path": "input.bin",
                "bytes": 4,
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
        )

    def test_export_writes_complete_manifest_last_and_exact_raw_arrays(self):
        """@brief Export all 20 vectors, preserving source metadata and array hashes."""
        exporter = body.BodyExporter(Path("moon"))
        results = fixture_results()
        exporter.read_moonbub = lambda *_args, **_kwargs: json.dumps(results).encode()
        exporter._blob = lambda value, *_args, **_kwargs: bytes.fromhex(value.get("raw", ""))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixtures"
            manifest = exporter.export(output)
            self.assertEqual(len(manifest["cases"]), 20)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text())["schema"], body.MANIFEST_SCHEMA
            )
            self.assertEqual(json.loads((output / "source-results.json").read_text()), results)
            case_path = output / manifest["cases"][0]["case_path"]
            case = json.loads(case_path.read_text())
            self.assertEqual(
                manifest["cases"][0]["case_sha256"],
                hashlib.sha256(case_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(manifest["cases"][0]["policy"], case["policy"])
            source = case["source_rgb"]
            self.assertEqual((case_path.parent / source["path"]).read_bytes(), bytes(12))
            self.assertEqual(source["sha256"], hashlib.sha256(bytes(12)).hexdigest())
            self.assertEqual(case["last_frame"], -1)
            self.assertEqual(case["state"]["encoder_last_issued"], -1)

    def test_bank_with_planes_exports_each_plane_and_keeps_u32_identity(self):
        """@brief Export real bank planes and accept contract-sized 32-bit bank IDs."""
        exporter = body.BodyExporter(Path("moon"))
        raw_y, raw_c = bytes(8), bytes(2)
        planes = [
            {"dtype": "<i2", "shape": [2, 2], "blob": {"raw_bytes": 8, "raw": raw_y.hex()}},
            {"dtype": "<i2", "shape": [1, 1], "blob": {"raw_bytes": 2, "raw": raw_c.hex()}},
            {"dtype": "<i2", "shape": [1, 1], "blob": {"raw_bytes": 2, "raw": raw_c.hex()}},
        ]
        exporter._blob = lambda value, *_args, **_kwargs: bytes.fromhex(value["raw"])
        with tempfile.TemporaryDirectory() as temporary:
            result = body._banks(
                exporter,
                {"0": {"id": 0xFFFFFFFF, "tag": "c" * 32, "planes": planes}, "1": None},
                Path(temporary),
                "bankcase",
                "bankcase",
                True,
                2,
                2,
            )
        self.assertEqual(result["0"]["id"], 0xFFFFFFFF)

    def test_export_refuses_existing_destination_and_requires_twenty_cases(self):
        """@brief Keep existing directories intact and reject incomplete mandatory indexes."""
        exporter = body.BodyExporter(Path("moon"))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "present"
            output.mkdir()
            sentinel = output / "keep"
            sentinel.write_text("untouched", encoding="utf-8")
            with self.assertRaises(body.BodyFixtureError):
                exporter.export(output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "untouched")

        exporter = body.BodyExporter(Path("moon"))
        exporter.read_moonbub = lambda *_args, **_kwargs: json.dumps(
            {
                "schema": "gamebub-mandatory-hud-v1",
                "cases": [],
            }
        ).encode()
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(body.BodyFixtureError):
            exporter.export(Path(temporary) / "new")

    def test_safe_case_identity_and_bank_metadata_are_rejected(self):
        """@brief Reject malformed bank sets and identities before exporting their planes."""
        exporter = body.BodyExporter(Path("moon"))
        with tempfile.TemporaryDirectory() as temporary:
            for value in (
                {},
                {"0": {"id": 0, "tag": "x"}, "1": {"id": 1, "tag": "0" * 32}},
                {"0": {"id": -1, "tag": "a" * 32}, "1": None},
                {"0": {"id": 0x100000000, "tag": "a" * 32}, "1": None},
                {"0": 5, "1": None},
            ):
                with self.subTest(value=value), self.assertRaises(body.BodyFixtureError):
                    body._banks(exporter, value, Path(temporary), "case", "case", False, 2, 2)

    def test_bank_plane_count_is_validated(self):
        """@brief Reject malformed plane lists before accessing any object descriptors."""
        exporter = body.BodyExporter(Path("moon"))
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(body.BodyFixtureError):
            body._banks(
                exporter,
                {"0": {"id": 1, "tag": "a" * 32, "planes": []}, "1": None},
                Path(temporary),
                "case",
                "case",
                True,
                2,
                2,
            )

    def test_bank_normalization_preserves_empty_slots_and_rejects_wrong_plane_geometry(self):
        """@brief Preserve empty reference slots and validate all serialized bank planes."""
        exporter = body.BodyExporter(Path("moon"))
        banks = {"0": None, "1": {"id": 4, "tag": "a" * 32}}
        self.assertEqual(
            body._banks(exporter, banks, Path("."), "unused", "case", False, 2, 2),
            {"0": None, "1": {"id": 4, "tag": "a" * 32}},
        )
        raw_plane = bytes(8)
        exporter._blob = lambda *_args, **_kwargs: raw_plane
        bank = {
            "id": 4,
            "tag": "a" * 32,
            "planes": [
                descriptor(raw_plane, "<i2", [2, 2]),
                descriptor(raw_plane, "<i2", [1, 2]),
                descriptor(raw_plane, "<i2", [1, 2]),
            ],
        }
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(body.BodyFixtureError):
            body._banks(
                exporter, {"0": bank, "1": None}, Path(temporary), "case", "case", True, 4, 2
            )

    def test_case_rejects_invalid_metadata_and_array_contracts(self):
        """@brief Exercise defensive checks around fixture identity, arrays, and state rows."""
        valid_case = fixture_results()["cases"][0]
        valid_vector = valid_case["vectors"][0]

        def reject(case=valid_case, vector=valid_vector):
            exporter = body.BodyExporter(Path("moon"))
            exporter._blob = lambda value, *_args, **_kwargs: bytes.fromhex(value.get("raw", ""))
            with (
                tempfile.TemporaryDirectory() as temporary,
                self.assertRaises(body.BodyFixtureError),
            ):
                exporter._case(case, vector, Path(temporary))

        reject(case=None)
        reject(vector=None)
        reject(case={**valid_case, "scene": "../bad"})
        reject(case={**valid_case, "policy": "unknown"})
        reject(vector={**valid_vector, "id": True})
        reject(case={**valid_case, "manifest": None})
        reject(case={**valid_case, "manifest": {"target_width": 3, "target_height": 2}})
        reject(case={**valid_case, "rows": None})
        reject(case={**valid_case, "rows": []})
        reject(vector={**valid_vector, "packet": {"raw": ""}})
        reject(vector={**valid_vector, "ack": {"raw": "00"}})
        reject(vector={**valid_vector, "source": {**valid_vector["source"], "shape": [2, 2]}})
        reject(vector={**valid_vector, "decoded_yuv": []})
        bad_y = {**valid_vector["decoded_yuv"][0], "shape": [1, 2]}
        reject(vector={**valid_vector, "decoded_yuv": [bad_y, *valid_vector["decoded_yuv"][1:]]})
        reject(
            vector={
                **valid_vector,
                "display_rgb565": {**valid_vector["display_rgb565"], "dtype": "<i2"},
            }
        )
        reject(vector={**valid_vector, "post_banks": {"0": {"id": 1, "tag": "bad"}, "1": None}})
        reject(case={**valid_case, "rows": [{**valid_case["rows"][0], "reference_tag": None}]})
        reject(case={**valid_case, "rows": [{**valid_case["rows"][0], "state_before": None}]})
        reject(vector={**valid_vector, "key": 1})
        reject(case={**valid_case, "rows": [{**valid_case["rows"][0], "reference_bank": 0x10000}]})

    def test_export_rejects_bad_indexes_and_duplicate_labels(self):
        """@brief Reject malformed result indexes and repeated mandatory case names."""
        for results in (
            [],
            {"schema": "wrong", "cases": []},
            {"schema": "gamebub-mandatory-hud-v1", "cases": None},
        ):
            exporter = body.BodyExporter(Path("moon"))
            exporter.read_moonbub = lambda *_args, value=results: json.dumps(value).encode()
            with (
                tempfile.TemporaryDirectory() as temporary,
                self.assertRaises(body.common.FixtureError),
            ):
                exporter.export(Path(temporary) / "out")

        duplicate = fixture_results()
        malformed = fixture_results()
        malformed["cases"][0] = None
        exporter = body.BodyExporter(Path("moon"))
        exporter.read_moonbub = lambda *_args: json.dumps(malformed).encode()
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(body.BodyFixtureError):
            exporter.export(Path(temporary) / "out")

        duplicate = fixture_results()
        duplicate["cases"].append(duplicate["cases"][0])
        exporter = body.BodyExporter(Path("moon"))
        exporter.read_moonbub = lambda *_args: json.dumps(duplicate).encode()
        exporter._blob = lambda value, *_args, **_kwargs: bytes.fromhex(value.get("raw", ""))
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(body.BodyFixtureError):
            exporter.export(Path(temporary) / "out")

    def test_script_entrypoint_reaches_argparse(self):
        """@brief Execute the standalone guard and verify required command-line arguments."""
        with patch("sys.argv", [str(Path(body.__file__))]), self.assertRaises(SystemExit) as raised:
            runpy.run_path(str(Path(body.__file__)), run_name="__main__")
        self.assertEqual(raised.exception.code, 2)

    def test_cli_reports_count_and_uses_requested_reference(self):
        """@brief Exercise CLI argument parsing and concise export summary."""

        class StubExporter:
            """@brief Substitute an exporter while testing CLI serialization."""

            def __init__(self, reference):
                self.reference = reference

            def export(self, _output):
                return {"cases": [{} for _ in range(body.MAX_CASES)]}

        with (
            patch.object(body, "BodyExporter", StubExporter),
            patch("builtins.print") as print_call,
        ):
            self.assertEqual(body.main(["--reference-repo", "moon", "--output", "out"]), 0)
        self.assertEqual(json.loads(print_call.call_args.args[0])["cases"], body.MAX_CASES)


if __name__ == "__main__":
    unittest.main()
