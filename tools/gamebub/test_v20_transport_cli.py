"""@brief Exercise the real offline wire replay and generated-motion profiling CLI."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("GAMEBUB_V20_EXE") and os.environ.get("GAMEBUB_V20_CONTRACT"),
    "Set GAMEBUB_V20_EXE and GAMEBUB_V20_CONTRACT for native wire replay",
)
class TransportCliTests(unittest.TestCase):
    """@brief Check actual native outputs without starting a socket or hardware session."""

    def invoke(self, *arguments):
        """@brief Execute a bounded offline native command with a finite child timeout."""
        return subprocess.run(
            [os.environ["GAMEBUB_V20_EXE"], *map(str, arguments)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_pinned_wire_history_and_examples(self):
        """@brief Require all golden controls and corruption probes, excluding state proof."""
        result = self.invoke("--transport-contract", os.environ["GAMEBUB_V20_CONTRACT"])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "pinned_transport_wire_only")
        self.assertEqual(report["history_count"], 9)
        self.assertEqual(report["fg19_messages"], 1725)
        self.assertEqual(report["corruption_truncation_rejections"], 3450)
        self.assertEqual(report["pc18_examples"], 1)
        self.assertEqual(report["qc18_examples"], 1)
        self.assertGreater(report["gf03_fragments"], 1)
        self.assertFalse(report["ownership_proven"])
        self.assertFalse(report["hardware_playback"])

    def test_contract_mutation_and_missing_input_fail(self):
        """@brief Reject changed provenance and absent files instead of claiming replay."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "contract.json"
            missing = self.invoke("--transport-contract", path)
            self.assertEqual(missing.returncode, 1)
            original = Path(os.environ["GAMEBUB_V20_CONTRACT"]).read_bytes()
            path.write_bytes(original + b"\n")
            changed = self.invoke("--transport-contract", path)
            self.assertEqual(changed.returncode, 1)
            self.assertIn("pinned transport contract hash", changed.stderr)

    def test_benchmark_frame_argument_bounds_precede_source_loading(self):
        """@brief Strict finite counts prevent accidental unlimited profiling runs."""
        for mode in ("--encoder-benchmark", "--encoder-benchmark-cached"):
            for value in ("0", "1801", "-1", "1x", "+1", "", "999999999999999999"):
                with self.subTest(mode=mode, value=value):
                    result = self.invoke(mode, "absent.json", value)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("benchmark frame count", result.stderr)

    @unittest.skipUnless(os.environ.get("GAMEBUB_V20_ENCODER_FIXTURES"), "Requires RGB seed")
    def test_generated_motion_has_real_software_reference_evolution(self):
        """@brief Run a continuous small workload, keeping playback claims explicitly false."""
        path = (
            Path(os.environ["GAMEBUB_V20_ENCODER_FIXTURES"])
            / "cases"
            / "mass-effect-2600-mandatory-00.json"
        )
        result = self.invoke("--encoder-benchmark", path, 3)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "offline_generated_motion_encode_and_software_decode")
        self.assertEqual(report["requested_frames"], 3)
        self.assertEqual(report["accepted_frames"] + report["rejected_frames"], 3)
        self.assertEqual(report["software_decoded_frames"], report["accepted_frames"])
        self.assertGreater(report["accepted_frames"], 0)
        self.assertEqual([row["id"] for row in report["frames"]], [0, 1, 2])
        for key in ("hardware_measured", "network_measured", "capture_measured"):
            self.assertFalse(report[key])
        self.assertTrue(report["profiling_not_playback"])

    @unittest.skipUnless(os.environ.get("GAMEBUB_V20_ENCODER_FIXTURES"), "Requires RGB seed")
    def test_frame_analysis_reuse_preserves_admitted_bytes_and_reference_counts(self):
        """@brief Compare baseline and cached continuous workloads through real software ACKs."""
        path = (
            Path(os.environ["GAMEBUB_V20_ENCODER_FIXTURES"])
            / "cases"
            / "mass-effect-7200-mandatory-00.json"
        )
        reports = []
        for mode in ("--encoder-benchmark", "--encoder-benchmark-cached"):
            result = self.invoke(mode, path, 3)
            self.assertEqual(result.returncode, 0, result.stderr)
            reports.append(json.loads(result.stdout))
        baseline, cached = reports
        self.assertFalse(baseline["analysis_reuse"])
        self.assertTrue(cached["analysis_reuse"])
        for key in (
            "source_rgb_sha256",
            "accepted_frames",
            "rejected_frames",
            "attempts",
            "losing_attempts",
            "complete_bytes",
            "final_confirmed_frame",
        ):
            self.assertEqual(baseline[key], cached[key], key)
        for left, right in zip(baseline["frames"], cached["frames"], strict=True):
            for key in ("id", "accepted", "packet_bytes", "frame_kind"):
                self.assertEqual(left[key], right[key], key)
            self.assertEqual(len(left["attempts"]), len(right["attempts"]))
            for first, second in zip(left["attempts"], right["attempts"], strict=True):
                for key in ("roi", "background", "complete_bytes", "accepted"):
                    self.assertEqual(first[key], second[key], key)


if __name__ == "__main__":
    unittest.main()
