"""@brief Check actual native HD22 conformance against retained word oracles."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("GAMEBUB_V20_EXE") and os.environ.get("GAMEBUB_HD22_FIXTURES"),
    "Requires native executable and exported HD22 fixtures",
)
class Hd22CliTests(unittest.TestCase):
    """@brief Verify real word reconstruction while keeping hardware claims disabled."""

    def invoke(self, directory):
        """@brief Run one finite hash-pinned native replay."""
        return subprocess.run(
            [os.environ["GAMEBUB_V20_EXE"], "--hud-delta-contract", str(directory)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_all_retained_word_oracles(self):
        """@brief Require all seven RAW/SPAN results and immutable exact references."""
        result = self.invoke(os.environ["GAMEBUB_HD22_FIXTURES"])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["vectors"], 7)
        self.assertEqual(report["raw_vectors"], 5)
        self.assertEqual(report["span_vectors"], 2)
        self.assertEqual(report["verified_words"], 26880)
        for key in (
            "copy_golden_available",
            "stateful_hc22_verified",
            "hardware_playback",
            "performance_measured",
        ):
            self.assertFalse(report[key], key)

    def test_missing_and_changed_source_artifact_reject(self):
        """@brief Fail closed before accepting a different corpus or absent directory."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(self.invoke(root).returncode, 1)
            original = Path(os.environ["GAMEBUB_HD22_FIXTURES"]) / "source_results.json"
            (root / "source_results.json").write_bytes(original.read_bytes() + b"\n")
            result = self.invoke(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("pinned HD22 results hash", result.stderr)


if __name__ == "__main__":
    unittest.main()
