"""@brief Verify deterministic audio assets and independent block reference hashes."""

import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import make_audio_assets as assets
from audio_codec import decode_block


class AudioAssetsTests(unittest.TestCase):
    """@brief Fixtures are reproducible and refuse to overwrite prior receiver evidence."""

    def test_assets_and_entrypoint(self):
        """@brief Regeneration matches bytes; a surviving late block has a standalone hash."""
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            manifest = assets.generate(first)
            self.assertEqual(manifest["version"], 2)
            self.assertEqual(manifest["encoder"], "gamebub-ima-product-v1")
            self.assertEqual((len(manifest["blocks"]), manifest["discarded_tail_frames"]), (20, 0))
            with self.assertRaises(FileExistsError):
                assets.generate(first)
            with patch("sys.argv", ["make_audio_assets.py", str(second)]), patch("builtins.print"):
                runpy.run_path(assets.__file__, run_name="__main__")
            self.assertEqual(manifest, json.loads((second / "manifest.json").read_text()))
            self.assertEqual(
                (first / "blocks.ima").read_bytes(), (second / "blocks.ima").read_bytes()
            )
            block = (first / "blocks.ima").read_bytes()[-512:]
            self.assertEqual(
                hashlib.sha256(decode_block(block)).hexdigest(),
                manifest["blocks"][-1]["decoded_pcm_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
