"""@brief Regression tests for bounded, pinned v20 fixture preparation."""

import hashlib
import io
import json
import runpy
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import prepare_v20_fixtures as prep


def packed(raw):
    """@brief Build a complete descriptor for a tiny zlib fixture."""
    return {
        "path": f"objects/{hashlib.sha256(zlib.compress(raw)).hexdigest()}.blob",
        "encoding": "zlib",
        "raw_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "stored_sha256": hashlib.sha256(zlib.compress(raw)).hexdigest(),
    }


class PrepareV20FixturesTests(unittest.TestCase):
    """@brief Check export layout, immutable source access, and rejection guards."""

    def fixture_exporter(self):
        """@brief Return an exporter backed by deterministic in-memory Git objects."""
        values = [[i % 256 for i in range(256)] for _ in range(2)]
        raw_in = bytes(values[0] * 2)
        raw_out = bytes((value + 1) % 256 for value in raw_in)
        in_desc, out_desc = packed(raw_in), packed(raw_out)
        index = {
            "schema": "gamebub-v20-inverse-golden-v1",
            "datasets": [{
                "name": "tiny",
                "blocks": 2,
                "arrays": {
                    "dequantized": {**in_desc, "dtype": "<i4", "shape": [2, 8, 8]},
                    "residual": {**out_desc, "dtype": "<i4", "shape": [2, 8, 8]},
                },
            }],
        }
        study = {"cases": []}
        for case_n in range(4):
            case = {"scene": f"scene{case_n // 2}", "policy": f"policy{case_n % 2}", "vectors": []}
            for fixture_id in (0, 1, 8, 24, 25):
                packet_raw = bytes([case_n, fixture_id, 1, 2, 3])
                ack_raw = bytes(43)
                case["vectors"].append({
                    "id": fixture_id,
                    "packet": packed(packet_raw),
                    "ack": packed(ack_raw),
                })
            study["cases"].append(case)
        moon_files = {
            f"{prep.KIT}/golden-index.json": json.dumps(index).encode(),
            f"{prep.STUDY}/results.json": json.dumps(study).encode(),
        }
        # Each descriptor in this fixture uses the same path/hash; expected differs in raw hash,
        # so build path-specific compressed contents for each distinct raw payload.
        raw_blobs = {raw_in: zlib.compress(raw_in), raw_out: zlib.compress(raw_out)}
        for case_n in range(4):
            for fixture_id in (0, 1, 8, 24, 25):
                packet_raw = bytes([case_n, fixture_id, 1, 2, 3])
                raw_blobs[packet_raw] = zlib.compress(packet_raw)
                raw_blobs[bytes(43)] = zlib.compress(bytes(43))

        def read_moonbub(_self, path, limit=prep.MAX_JSON_BYTES):
            if path in moon_files:
                return moon_files[path]
            suffix = path.rsplit("/", 1)[-1].removesuffix(".blob")
            for blob in raw_blobs.values():
                if hashlib.sha256(blob).hexdigest() == suffix:
                    return blob
            raise FileNotFoundError(path)

        exporter = prep.Exporter(Path("moon"), Path("sunshine"))
        exporter.read_moonbub = read_moonbub.__get__(exporter)

        def fake_show(_repo, revision, path, _limit):
            self.assertEqual(revision, prep.SUNSHINE_COMMIT)
            self.assertIn(path, ("tools/gamebub/v20/wire-contract.json", "tools/gamebub/v20/development-profile.json"))
            return b"{}\n"

        return exporter, fake_show, raw_in, raw_out

    def test_export_contains_all_inverse_pairs_contracts_and_envelopes(self):
        """@brief Export emits raw inverse pairs and all 20 exact envelope file pairs."""
        exporter, fake_show, raw_in, raw_out = self.fixture_exporter()
        with tempfile.TemporaryDirectory() as temporary, patch.object(prep, "_git_show", side_effect=fake_show):
            output = Path(temporary) / "prepared"
            manifest = exporter.export(output)
            self.assertEqual(len(manifest["ar03_fixtures"]), 20)
            self.assertEqual((output / "inverse/tiny.input.i32le.bin").read_bytes(), raw_in)
            self.assertEqual((output / "inverse/tiny.expected.i32le.bin").read_bytes(), raw_out)
            self.assertEqual((output / "manifest.json").read_bytes(), (json.dumps(manifest, indent=2) + "\n").encode())
            for row in manifest["ar03_fixtures"]:
                self.assertEqual((output / row["af03_path"]).stat().st_size, 43)
                packet = (output / row["ar03_path"]).read_bytes()
                self.assertEqual(len(packet), row["ar03_bytes"])
                self.assertEqual(hashlib.sha256(packet).hexdigest(), row["ar03_sha256"])

    def test_existing_output_is_refused(self):
        """@brief Never overwrite a caller's existing fixture directory."""
        exporter, _, _, _ = self.fixture_exporter()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            with self.assertRaises(prep.FixtureError):
                exporter.export(output)

    def test_safe_paths_reject_traversal_and_windows_separators(self):
        """@brief Reject paths that could escape the pinned repository or output root."""
        for path in ("../escape", "a/../../escape", "C:/outside", "a\\b", "a//b", "a/./b", ""):
            with self.subTest(path=path), self.assertRaises(prep.FixtureError):
                prep._safe_relpath(path)

    def test_git_object_size_is_checked_before_contents_are_read(self):
        """@brief Reject oversized pinned objects before running git show."""
        with (
            patch.object(prep.subprocess, "run", return_value=SimpleNamespace(stdout="99\n")) as run,
            self.assertRaises(prep.FixtureError),
        ):
            prep._git_show(Path("repo"), "commit", "safe/file", 10)
        self.assertEqual(run.call_count, 1)
        self.assertIn("cat-file", run.call_args.args[0])

    def test_git_metadata_parse_and_show_size_paths(self):
        """@brief Cover malformed Git size metadata and the bounded object-read result."""
        with (
            patch.object(prep.subprocess, "run", return_value=SimpleNamespace(stdout="bad")),
            self.assertRaises(prep.FixtureError),
        ):
            prep._git_show(Path("repo"), "commit", "safe/file", 10)
        with patch.object(
            prep.subprocess,
            "run",
            side_effect=[
                SimpleNamespace(stdout="3\n"),
                SimpleNamespace(stdout=b"abc"),
            ],
        ) as run:
            self.assertEqual(prep._git_show(Path("repo"), "commit", "safe/file", 3), b"abc")
        self.assertEqual(run.call_count, 2)
        with (
            patch.object(
                prep.subprocess,
                "run",
                side_effect=[
                    SimpleNamespace(stdout="2\n"),
                    SimpleNamespace(stdout=b"too long"),
                ],
            ),
            self.assertRaises(prep.FixtureError),
        ):
            prep._git_show(Path("repo"), "commit", "safe/file", 2)

    def test_exporter_reads_pinned_source_through_git_helper(self):
        """@brief Ensure MoonBub reads always use the fixed revision and supplied repo."""
        exporter = prep.Exporter(Path("moon"), Path("sun"))
        with patch.object(prep, "_git_show", return_value=b"data") as show:
            self.assertEqual(exporter.read_moonbub("safe/file", 20), b"data")
        self.assertEqual(show.call_args.args, (exporter.moonbub_repo, prep.MOONBUB_COMMIT, "safe/file", 20))

    def test_blob_rejects_stored_hash_mismatch_and_trailing_zlib_data(self):
        """@brief Reject tampered storage metadata and concatenated zlib payloads."""
        exporter, _, _, _ = self.fixture_exporter()
        descriptor = packed(b"payload")
        exporter.read_moonbub = lambda _path, _limit: zlib.compress(b"tampered")
        with self.assertRaises(prep.FixtureError):
            exporter._blob(descriptor, prep.KIT)
        compressed = zlib.compress(b"payload") + zlib.compress(b"extra")
        descriptor["path"] = "objects/combined.blob"
        descriptor["stored_sha256"] = hashlib.sha256(compressed).hexdigest()
        exporter.read_moonbub = lambda _path, _limit: compressed
        with self.assertRaises(prep.FixtureError):
            exporter._blob(descriptor, prep.KIT)

    def test_blob_rejects_encoding_hash_and_aggregate_errors(self):
        """@brief Reject unsupported encodings, incorrect raw hashes, and aggregate bombs."""
        exporter, _, _, _ = self.fixture_exporter()
        descriptor = packed(b"payload")
        with self.assertRaises(prep.FixtureError):
            exporter._blob({**descriptor, "encoding": "gzip"}, prep.KIT)
        exporter.read_moonbub = lambda _path, _limit: zlib.compress(b"payload")
        with self.assertRaises(prep.FixtureError):
            exporter._blob({**descriptor, "raw_sha256": "0" * 64}, prep.KIT)
        exporter.total_raw_bytes = prep.MAX_TOTAL_RAW_BYTES
        with self.assertRaises(prep.FixtureError):
            exporter._blob(descriptor, prep.KIT)

    def test_blob_validates_raw_size_and_uncompressed_encoding(self):
        """@brief Exercise the uncompressed blob route and reject size/hash mismatches."""
        exporter, _, _, _ = self.fixture_exporter()
        raw = b"raw bytes"
        descriptor = {
            "path": "objects/raw.bin",
            "encoding": "raw",
            "raw_bytes": len(raw),
            "stored_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        exporter.read_moonbub = lambda _path, _limit: raw
        self.assertEqual(exporter._blob(descriptor, prep.KIT, expected_encoding="raw"), raw)
        with self.assertRaises(prep.FixtureError):
            exporter._blob({**descriptor, "raw_bytes": len(raw) + 1}, prep.KIT, expected_encoding="raw")

    def test_inverse_index_schema_and_descriptor_errors(self):
        """@brief Reject invalid golden schemas, datasets, and descriptor geometry."""

        def run_index(index):
            exporter, _, _, _ = self.fixture_exporter()
            exporter.read_moonbub = lambda _path, _limit=prep.MAX_JSON_BYTES: json.dumps(index).encode()
            with tempfile.TemporaryDirectory() as temporary, self.assertRaises(prep.FixtureError):
                exporter._export_inverse(Path(temporary))

        good_descriptor = {
            **packed(bytes(256)),
            "dtype": "<i4",
            "shape": [1, 8, 8],
        }
        valid_dataset = {
            "name": "case",
            "blocks": 1,
            "arrays": {"dequantized": good_descriptor, "residual": good_descriptor},
        }
        malformed = [
            {"schema": "wrong", "datasets": [valid_dataset]},
            {"schema": "gamebub-v20-inverse-golden-v1", "datasets": [{**valid_dataset, "name": "bad/name"}]},
            {"schema": "gamebub-v20-inverse-golden-v1", "datasets": [{"name": "case", "blocks": 1}]},
            {"schema": "gamebub-v20-inverse-golden-v1", "datasets": [{**valid_dataset, "arrays": {
                "dequantized": {**good_descriptor, "dtype": "i32"}, "residual": good_descriptor}}]},
            {"schema": "gamebub-v20-inverse-golden-v1", "datasets": [{**valid_dataset, "arrays": {
                "dequantized": {**good_descriptor, "shape": [1, 8]}, "residual": good_descriptor}}]},
            {"schema": "gamebub-v20-inverse-golden-v1", "datasets": [{**valid_dataset, "arrays": {
                "dequantized": good_descriptor, "residual": {**good_descriptor, "shape": [2, 8, 8]}}}]},
            {"schema": "gamebub-v20-inverse-golden-v1", "datasets": [{**valid_dataset, "blocks": 2}]},
        ]
        for index in malformed:
            with self.subTest(index=index):
                run_index(index)
        run_index({"schema": "gamebub-v20-inverse-golden-v1", "datasets": []})

        exporter, _, _, _ = self.fixture_exporter()
        exporter.read_moonbub = lambda _path, _limit=prep.MAX_JSON_BYTES: json.dumps({
            "schema": "gamebub-v20-inverse-golden-v1",
            "datasets": [{
                **valid_dataset,
                "arrays": {
                    "dequantized": {**good_descriptor, "raw_bytes": 4},
                    "residual": {**good_descriptor, "raw_bytes": 4},
                },
            }],
        }).encode()
        exporter._blob = lambda _descriptor, _prefix: bytes(4)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(prep.FixtureError):
            exporter._export_inverse(Path(temporary))

    def test_inverse_rejects_unsafe_descriptor_path(self):
        """@brief Refuse traversal paths in arrays before asking Git for their object."""
        exporter, _, _, _ = self.fixture_exporter()
        descriptor = {**packed(bytes(256)), "dtype": "<i4", "shape": [1, 8, 8], "path": "../escape"}
        index = {
            "schema": "gamebub-v20-inverse-golden-v1",
            "datasets": [{"name": "case", "blocks": 1, "arrays": {
                "dequantized": descriptor, "residual": descriptor,
            }}],
        }
        exporter.read_moonbub = lambda _path, _limit=prep.MAX_JSON_BYTES: json.dumps(index).encode()
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(prep.FixtureError):
            exporter._export_inverse(Path(temporary))

    def test_packet_index_rejects_bad_ids_count_sizes_and_duplicate_labels(self):
        """@brief Enforce all 20 unique packet labels and envelope size constraints."""

        def fixture_results(ids):
            return {"cases": [{
                "scene": "scene",
                "policy": "policy",
                "vectors": [{"id": fixture_id, "packet": {"kind": "packet"}, "ack": {"kind": "ack"}} for fixture_id in ids],
            }]}

        def run_results(results, packet=b"p" * 65, ack=b"a" * 43):
            exporter, _, _, _ = self.fixture_exporter()
            exporter.read_moonbub = lambda _path, _limit=prep.MAX_JSON_BYTES: json.dumps(results).encode()
            exporter._blob = lambda descriptor, _prefix, **_kwargs: ack if descriptor["kind"] == "ack" else packet
            with tempfile.TemporaryDirectory() as temporary, self.assertRaises(prep.FixtureError):
                exporter._export_packets(Path(temporary))

        run_results(fixture_results(list(range(19))))
        run_results(fixture_results([-1] + list(range(19))))
        run_results(fixture_results(list(range(20))), ack=b"a" * 42)
        run_results(fixture_results(list(range(20))), packet=b"p" * (prep.MAX_AR03_BYTES + 1))
        duplicate = list(range(20))
        duplicate[-1] = duplicate[0]
        run_results(fixture_results(duplicate))

    def test_invalid_json_and_missing_contract_repo_are_reported(self):
        """@brief Reject malformed metadata and require the pinned Sunshine contract source."""
        with self.assertRaises(prep.FixtureError):
            prep._json(b"\xff", "broken")
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(prep.FixtureError):
            prep.Exporter(Path(temporary))._export_contracts(Path(temporary))

    def test_cli_reports_export_counts(self):
        """@brief CLI accepts explicit repositories/output and prints a concise summary."""
        manifest = {"inverse": {"datasets": [1, 2]}, "ar03_fixtures": [1, 2, 3]}

        class StubExporter:
            """@brief Replace Git access while exercising argument parsing/output formatting."""

            def __init__(self, moon, sunshine):
                self.repositories = moon, sunshine

            def export(self, output):
                self.output = output
                return manifest

        output = io.StringIO()
        with patch.object(prep, "Exporter", StubExporter), redirect_stdout(output):
            result = prep.main(["--reference-repo", "moon", "--sunshine-repo", "sun",
                                "--output", "fixtures"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["inverse_datasets"], 2)

    def test_script_entrypoint_parses_required_arguments(self):
        """@brief Executing the script directly enters argparse and rejects missing arguments."""
        with patch("sys.argv", [str(Path(prep.__file__))]), self.assertRaises(SystemExit) as raised:
            runpy.run_path(str(Path(prep.__file__)), run_name="__main__")
        self.assertEqual(raised.exception.code, 2)

    def test_blob_rejects_declared_raw_size_bombs(self):
        """@brief Enforce per-object expansion bounds before writing fixture files."""
        exporter, _, _, _ = self.fixture_exporter()
        descriptor = packed(b"x")
        descriptor["raw_bytes"] = prep.MAX_RAW_BYTES + 1
        with self.assertRaises(prep.FixtureError):
            exporter._blob(descriptor, prep.KIT)


if __name__ == "__main__":
    unittest.main()
