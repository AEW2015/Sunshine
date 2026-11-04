"""@brief Exercise bounded hash-pinned HD22 export without executing reference Python."""

import hashlib
import io
import json
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import prepare_hd22_fixtures as h


class Hd22ExporterTests(unittest.TestCase):
    """@brief Verify preflight, hash/stream limits and non-overwriting exports."""

    def setUp(self):
        """@brief Build explicit tiny mock Git blobs; real artifacts are replayed separately."""
        raw = b"\x01\x02"
        stored = zlib.compress(raw)
        self.descriptor = {
            "path": "objects/a.zlib",
            "raw_bytes": 2,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "stored_sha256": hashlib.sha256(stored).hexdigest(),
        }
        self.stored = stored
        golden = {
            "shape": [1, 1],
            "packet": self.descriptor,
            "current": self.descriptor,
            "reference": None,
        }
        self.results = json.dumps({"goldens": [golden] * 7}).encode()

    def fake_git(self, repo, commit, path, limit):
        """@brief Return a deterministic mock object under the real pinned-commit argument."""
        self.assertEqual(commit, h.COMMIT)
        return self.results if path.endswith("results.json") else self.stored

    def test_export_and_existing_destination_preserved(self):
        """@brief Emit exact raw bytes, then refuse to replace the same output directory."""
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(h, "_git_show", self.fake_git),
            patch.object(h, "RESULTS_HASH", hashlib.sha256(self.results).hexdigest()),
        ):
            root = Path(folder) / "out"
            report = h.export(Path(folder), root)
            self.assertEqual(report["vectors"], 7)
            self.assertEqual(report["objects"], 1)
            self.assertEqual((root / "source_results.json").read_bytes(), self.results)
            self.assertEqual(next((root / "objects").iterdir()).read_bytes(), b"\x01\x02")
            with self.assertRaises(FileExistsError):
                h.export(Path(folder), root)

    def test_main_reports_success_for_exclusive_export(self):
        """@brief Exercise the documented CLI arguments against a controlled Git reader."""
        output = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(h, "_git_show", self.fake_git),
            patch.object(h, "RESULTS_HASH", hashlib.sha256(self.results).hexdigest()),
            redirect_stdout(output),
        ):
            self.assertEqual(
                h.main(["--reference-repo", folder, "--output-dir", str(Path(folder) / "out")]), 0
            )
        self.assertEqual(json.loads(output.getvalue())["vectors"], 7)

    def test_wrong_results_hash_does_not_create_output(self):
        """@brief Fail provenance before any filesystem publication."""
        with tempfile.TemporaryDirectory() as folder, patch.object(h, "_git_show", self.fake_git):
            root = Path(folder) / "out"
            with self.assertRaisesRegex(h.FixtureError, "pinned"):
                h.export(Path(folder), root)
            self.assertFalse(root.exists())

    def test_object_bounds_hashes_and_path_reject(self):
        """@brief Reject malformed descriptors without trusting repository paths."""
        for key, value in (
            ("path", "../escape"),
            ("path", "other/a.zlib"),
            ("raw_bytes", 0),
            ("raw_bytes", 42291),
            ("raw_sha256", "bad"),
            ("stored_sha256", "0" * 64),
            ("raw_sha256", "0" * 64),
        ):
            with self.subTest(key=key, value=value), patch.object(h, "_git_show", self.fake_git):
                descriptor = dict(self.descriptor, **{key: value})
                with self.assertRaises(h.FixtureError):
                    h.unpack(Path("."), descriptor)

    def test_trailing_stream_and_wrong_size_reject(self):
        """@brief Do not accept concatenated streams or oversized decompressed output."""
        for stored, size in ((self.stored + b"tail", 2), (self.stored[:-1], 2), (self.stored, 1)):
            descriptor = dict(
                self.descriptor, raw_bytes=size, stored_sha256=hashlib.sha256(stored).hexdigest()
            )
            with (
                self.subTest(size=size),
                patch.object(h, "_git_show", return_value=stored),
                self.assertRaises(h.FixtureError),
            ):
                h.unpack(Path("."), descriptor)

    def test_geometry_count_and_word_mismatch_preflight(self):
        """@brief Reject malformed case geometry before creating an output directory."""
        base = json.loads(self.results)
        for change in ("count", "shape", "words"):
            data = json.loads(self.results)
            if change == "count":
                data["goldens"].pop()
            elif change == "shape":
                data["goldens"][0]["shape"] = [481, 1]
            else:
                data["goldens"][0]["shape"] = [1, 2]
            self.results = json.dumps(data).encode()
            with (
                tempfile.TemporaryDirectory() as folder,
                patch.object(h, "_git_show", self.fake_git),
                patch.object(h, "RESULTS_HASH", hashlib.sha256(self.results).hexdigest()),
            ):
                root = Path(folder) / "out"
                with self.assertRaises(h.FixtureError):
                    h.export(Path(folder), root)
                self.assertFalse(root.exists())
            self.results = json.dumps(base).encode()


if __name__ == "__main__":
    unittest.main()
