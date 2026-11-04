"""@brief Real native encoder fixture regressions; never opens a socket or device."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from verify_v20_body import descendant, descriptors


@unittest.skipUnless(
    os.environ.get("GAMEBUB_V20_EXE") and os.environ.get("GAMEBUB_V20_ENCODER_FIXTURES"),
    "Set GAMEBUB_V20_EXE and GAMEBUB_V20_ENCODER_FIXTURES for native encoder replay",
)
class EncoderCliTests(unittest.TestCase):
    """@brief Require actual source encoding and reject stale duplicated oracle metadata."""

    def setUp(self):
        """@brief Copy only a case's declared raw files into private test storage."""
        self.directory = tempfile.TemporaryDirectory(prefix="gamebub-encoder-cli-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.exe = str(Path(os.environ["GAMEBUB_V20_EXE"]).resolve(strict=True))
        self.fixtures = Path(os.environ["GAMEBUB_V20_ENCODER_FIXTURES"]).resolve(strict=True)
        self.load("mass-effect-7200-mandatory-00")

    def load(self, label):
        """@brief Retain exact source pixels and predictor preconditions from the frozen export."""
        path = self.fixtures / "cases" / f"{label}.json"
        self.case = json.loads(path.read_text())
        for descriptor in descriptors(self.case):
            shutil.copyfile(
                descendant(path.parent, descriptor["path"]), self.root / descriptor["path"]
            )

    def run_case(self, expected=0, message=None):
        """@brief Execute the actual encoder, checking finite exit and scoped report."""
        path = self.root / "case.json"
        path.write_text(json.dumps(self.case), encoding="utf-8")
        result = subprocess.run(
            [self.exe, "--encoder-case", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        if message is not None:
            self.assertIn(message, result.stderr)
        return json.loads(result.stdout) if expected == 0 else result.stderr

    def test_actual_cap_retry_and_reference_ack(self):
        """@brief The real fine map loses at54894B and the next map wins at47238B."""
        report = self.run_case()
        self.assertEqual(report["scope"], "native_encoder_fixture")
        self.assertTrue(
            report["inner_byte_exact"]
            and report["patches_byte_exact"]
            and report["ar03_byte_exact"]
        )
        self.assertTrue(report["mandatory_policy_verified"])
        self.assertTrue(report["profiling_not_playback"])
        self.assertEqual(report["inner_bytes"], 24301)
        self.assertEqual(report["packet_bytes"], 47238)
        self.assertEqual(report["selected_patch_count"], 4)
        self.assertEqual([r["complete_bytes"] for r in report["policy_attempts"]], [54894, 47238])
        self.assertEqual([r["accepted"] for r in report["policy_attempts"]], [False, True])

    def test_baseline_partial_hud_is_only_a_grammar_control(self):
        """@brief An intentionally incomplete baseline cannot claim mandatory admission."""
        self.load("mass-effect-7200-baseline-00")
        report = self.run_case()
        self.assertEqual(report["selected_patch_count"], 3)
        self.assertFalse(report["mandatory_policy_verified"])
        self.assertEqual(report["policy_attempts"], [])
        self.assertEqual(report["frozen_decode"]["mandatory_hud_words_verified"], 0)

    def test_corrupt_encoder_oracles_reject(self):
        """@brief Hash-valid frozen pixels cannot excuse changed control/profile oracles."""
        original = json.dumps(self.case)
        changes = (
            (lambda o: o["reference"].update(bank=0), "reference oracle"),
            (lambda o: o["reference"].update(id=0), "reference oracle"),
            (lambda o: o["reference"].update(tag="1" * 32), "reference oracle"),
            (lambda o: o["reference"]["geometry"].update(width=718), "reference oracle"),
            (lambda o: o["destination"].update(bank=1), "destination oracle"),
            (lambda o: o["destination"].update(tag="f" * 32), "destination oracle"),
            (lambda o: o["roi_quantmap"].update(roi_scale=16), "map/hash oracle"),
            (lambda o: o.update(packet_sha256="0" * 64), "map/hash oracle"),
            (lambda o: o.update(key=False), "frame flags"),
            (lambda o: o.update(selected_profile=[8, 8]), "declared map"),
            (lambda o: o.update(selected_profile=[]), "map shape"),
            (lambda o: o.update(inner_bytes=24300), "inner oracle/tag"),
            (lambda o: o.update(patch_bytes=22873), "patch blob oracle"),
            (lambda o: o.update(packet_bytes=47239), "complete byte oracle"),
            (lambda o: o.update(attempts=[]), "attempt count"),
            (lambda o: o["attempts"][0].update(attempted_complete_bytes=54895), "attempt oracle"),
        )
        for mutate, message in changes:
            with self.subTest(message=message):
                self.case = json.loads(original)
                mutate(self.case["encoder_oracle"])
                self.run_case(1, message)
