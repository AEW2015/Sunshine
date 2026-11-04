"""@brief Check pinned RS24 bytes through the native offline executable."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("GAMEBUB_V20_EXE") and os.environ.get("GAMEBUB_V24_RESULTS"),
    "Set GAMEBUB_V20_EXE and GAMEBUB_V24_RESULTS for RS24 wire replay",
)
class RecoveryCliTests(unittest.TestCase):
    """@brief Exercise the actual command without sockets, resets or hardware."""

    def invoke(self, path, mode="--recovery-contract"):
        """@brief Run one bounded native replay."""
        return subprocess.run(
            [os.environ["GAMEBUB_V20_EXE"], mode, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_all_frozen_controls_match(self):
        """@brief Require exact bytes and reject every single-byte bit corruption."""
        result = self.invoke(os.environ["GAMEBUB_V24_RESULTS"])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "pinned_rs24_wire_only")
        self.assertEqual(report["messages"], 124)
        self.assertEqual(report["corruption_rejections"], 5704)
        for key in (
            "state_replayed",
            "physical_drain_proven",
            "live_profile_negotiated",
            "hardware_playback",
        ):
            self.assertFalse(report[key], key)

    def test_absent_and_changed_results_fail_closed(self):
        """@brief Reject missing artifacts and changed provenance."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            self.assertEqual(self.invoke(path).returncode, 1)
            path.write_bytes(Path(os.environ["GAMEBUB_V24_RESULTS"]).read_bytes() + b"\n")
            result = self.invoke(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("pinned RS24 results hash", result.stderr)

    def test_host_control_loss_and_reboot_campaigns(self):
        """@brief Check actual host transitions with explicitly injected clear-owner evidence."""
        result = self.invoke(os.environ["GAMEBUB_V24_RESULTS"], "--recovery-replay")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "pinned_rs24_host_control_replay")
        for key, expected in (
            ("campaigns", 13),
            ("controls", 124),
            ("accepted_replies", 51),
            ("retry_calls", 13),
            ("safe_stops", 1),
            ("last_reboot_epoch", 3),
        ):
            self.assertEqual(report[key], expected, key)
        self.assertTrue(report["host_control_replayed"])
        self.assertEqual(report["drain_input"], "explicitly modeled clear owners")
        for key in (
            "receiver_state_replayed",
            "media_reset_replayed",
            "physical_drain_proven",
            "hardware_playback",
        ):
            self.assertFalse(report[key], key)

    def test_replay_missing_or_changed_provenance_fails(self):
        """@brief Keep state replay bound to the exact published artifact."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            self.assertEqual(self.invoke(path, "--recovery-replay").returncode, 1)
            path.write_bytes(Path(os.environ["GAMEBUB_V24_RESULTS"]).read_bytes() + b"\n")
            result = self.invoke(path, "--recovery-replay")
            self.assertEqual(result.returncode, 1)
            self.assertIn("pinned RS24 results hash", result.stderr)


if __name__ == "__main__":
    unittest.main()
