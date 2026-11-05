"""@brief Run actual finite native saved-frame CLI checks without sockets or hardware."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from prepare_encoder_sequence import SCHEMA


@unittest.skipUnless(os.environ.get("GAMEBUB_V20_EXE"), "Set GAMEBUB_V20_EXE for native CLI checks")
class EncoderSequenceCliTests(unittest.TestCase):
    """@brief Verify actual command-line behavior, cap accounting and malformed sources."""

    def setUp(self):
        """@brief Own two tiny-detail full-size RGB8 sources and their declared identities."""
        self.directory = tempfile.TemporaryDirectory(prefix="gamebub-sequence-cli-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.exe = str(Path(os.environ["GAMEBUB_V20_EXE"]).resolve(strict=True))
        self.manifest = {
            "schema": SCHEMA,
            "label": "synthetic-two-frame-cli-input",
            "geometry": {"width": 720, "height": 480, "channels": 3},
            "source": {
                "kind": "saved_clip",
                "file_name": "synthetic-metadata-not-real-video.webm",
                "bytes": 123,
                "sha256": "a" * 64,
                "requested_offset_us": 0,
                "sample_fps": 30,
                "selection_mode": "resampled",
                "native_rate": None,
                "first_decoded_id": None,
                "first_sample_index": 0,
                "pts_origin_us": 0,
                "resampling_policy": "existing clip_frames: source at or before sample; ceil offset to sampling grid",
                "canvas_policy": "existing canvas: aspect-preserving fit into centered720x405 within720x480",
                "loop": False,
                "repeated_source_timestamps": False,
            },
            "frames": [],
        }
        for index in range(2):
            raw = bytearray([128]) * (720 * 480 * 3)
            raw[index * 3] = 255
            name = f"frame{index}.rgb"
            (self.root / name).write_bytes(raw)
            self.manifest["frames"].append(
                {
                    "id": index,
                    "pts_us": index * 33333,
                    "sample_time_us": index * 1_000_000 // 30,
                    "rgb": {
                        "path": name,
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "dtype": "|u1",
                        "shape": [480, 720, 3],
                    },
                }
            )

    def execute(self, flag="--encoder-sequence", frames="2", expected=0):
        """@brief Execute the real isolated CLI with bounded duration and output."""
        path = self.root / "manifest.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        result = subprocess.run(
            [self.exe, flag, str(path), frames],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return json.loads(result.stdout) if expected == 0 else result.stderr

    def test_native_both_modes_keep_hashes_costs_and_reference_counts(self):
        """@brief Compare actual baseline/cache commands without treating them as performance tests."""
        baseline = self.execute()
        cached = self.execute("--encoder-sequence-cached")
        self.assertEqual(baseline["accepted_frames"], 2)
        self.assertEqual(baseline["complete_bytes"], cached["complete_bytes"])
        self.assertEqual(cached["source_frames_loaded"], 2)
        self.assertEqual(cached["analysis_builds"], 2)
        self.assertFalse(baseline["hardware_measured"])
        self.assertFalse(baseline["original_clip_reverified"])
        for index in range(2):
            row = cached["frames"][index]
            self.assertEqual(
                row["source_rgb_sha256"], self.manifest["frames"][index]["rgb"]["sha256"]
            )
            self.assertEqual(row["packet_sha256"], baseline["frames"][index]["packet_sha256"])
            self.assertGreaterEqual(
                row["source_prepare_ns"], row["source_file_read_ns"] + row["source_hash_ns"]
            )

    def test_cli_count_bounds_and_source_exhaustion(self):
        """@brief Invalid command counts fail rather than silently looping or shortening input."""
        for count in ("0", "1801", "-1", "1.5", "no"):
            self.assertIn("frame count", self.execute(frames=count, expected=1))
        self.assertIn("exceeds source", self.execute(frames="3", expected=1))

    def test_native_mode_retains_pts_without_fabricated_sampling_grid(self):
        """@brief The actual CLI preserves native provenance rather than inventing30fps capture."""
        source = self.manifest["source"]
        source["selection_mode"] = "native-decoded"
        source["resampling_policy"] = (
            "no resampling: unique decoded native frames; skip before requested relative PTS offset"
        )
        source["sample_fps"] = None
        source["first_sample_index"] = None
        source["first_decoded_id"] = 0
        source["native_rate"] = {"numerator": 30, "denominator": 1}
        source["pts_origin_us"] = 7000
        for row in self.manifest["frames"]:
            row["relative_pts_us"] = row["pts_us"]
            row["pts_us"] += 7000
            del row["sample_time_us"]
        report = self.execute()
        self.assertEqual(report["frames"][0]["source_pts_us"], 7000)
        self.assertNotIn("source_sample_time_us", report["frames"][0])
        self.assertEqual(
            report["source_provenance"]["native_rate"], {"numerator": 30, "denominator": 1}
        )
        source["sample_fps"] = 30
        self.assertIn("no sample grid", self.execute(expected=1))

    def test_actual_hash_traversal_and_duplicate_pts_reject(self):
        """@brief Real loader must enforce integrity, confinement and source temporal identity."""
        self.manifest["frames"][0]["rgb"]["sha256"] = "0" * 64
        self.assertIn("RGB8 hash", self.execute(expected=1))
        self.manifest["frames"][0]["rgb"]["path"] = "../escape.rgb"
        self.assertIn("traversal", self.execute(expected=1))
        self.manifest["frames"][0]["rgb"]["path"] = "frame0.rgb"
        self.manifest["frames"][1]["pts_us"] = 0
        self.assertIn("ordered source identities", self.execute(expected=1))

    def test_wrong_mode_remains_usage_error(self):
        """@brief New flags do not reinterpret unknown modes as encoded media input."""
        self.assertIn("Usage:", self.execute(flag="--encoder-sequence-unknown", expected=2))


if __name__ == "__main__":
    unittest.main()
