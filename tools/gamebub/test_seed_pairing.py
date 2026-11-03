"""@brief Tests for isolated Sunshine client-certificate state preparation."""

import contextlib
import io
import json
import re
import runpy
import ssl
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from seed_pairing import main, seed_state


class SeedPairingTests(unittest.TestCase):
    """@brief Verify state shape, parsing, and preservation of existing files."""

    @classmethod
    def setUpClass(cls):
        """@brief Reuse Sunshine's public test certificate, never its test private key."""
        source = (
            Path(__file__).resolve().parents[2] / "tests/unit/test_confighttp.cpp"
        ).read_text()
        cls.certificate = re.search(
            r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", source, re.DOTALL
        ).group()

    def test_seed_state_and_sunshine_fields(self):
        """@brief A new state contains exactly one enabled public client identity."""
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "state.json"
            fingerprint = seed_state(self.certificate, target)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(fingerprint), 64)
            root = data["root"]
            uuid.UUID(root["uniqueid"])
            self.assertEqual(len(root["named_devices"]), 1)
            device = root["named_devices"][0]
            uuid.UUID(device["uuid"])
            self.assertEqual(device["name"], "Game Bub")
            self.assertTrue(device["enabled"])
            self.assertEqual(
                ssl.PEM_cert_to_DER_cert(device["cert"]), ssl.PEM_cert_to_DER_cert(self.certificate)
            )
            self.assertNotIn("PRIVATE KEY", target.read_text(encoding="utf-8"))
            self.assertNotIn("password", data)

    def test_reject_non_certificate_and_private_material(self):
        """@brief Do not publish malformed data, a certificate chain, or private keys."""
        cases = (
            "",
            "text",
            self.certificate * 2,
            self.certificate + "\nPRIVATE KEY",
            "-----BEGIN CERTIFICATE-----\nQUJD\n-----END CERTIFICATE-----",
        )
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "state.json"
            for value in cases:
                with self.subTest(value=value[:20]), self.assertRaises(ValueError):
                    seed_state(value, target)
                self.assertFalse(target.exists())

    def test_existing_state_never_overwritten(self):
        """@brief Exclusive creation preserves an existing installation's state byte for byte."""
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "state.json"
            target.write_bytes(b"existing user state")
            with self.assertRaises(FileExistsError):
                seed_state(self.certificate, target)
            self.assertEqual(target.read_bytes(), b"existing user state")

    def test_cli_success_and_invalid_input(self):
        """@brief The CLI reports only the public fingerprint and fails on missing input."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cert = folder / "client.pem"
            cert.write_text(self.certificate, encoding="utf-8")
            output = folder / "state.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--client-cert", str(cert), "--output", str(output)]), 0)
            self.assertIn("certificate SHA-256", stdout.getvalue())
            self.assertNotIn("BEGIN CERTIFICATE", stdout.getvalue())
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--client-cert", str(folder / "missing"), "--output", str(output)])

    def test_script_entrypoint(self):
        """@brief Run the standalone script with a temporary public certificate."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            cert = folder / "client.pem"
            cert.write_text(self.certificate, encoding="utf-8")
            script = Path(__file__).with_name("seed_pairing.py")
            with (
                patch.object(
                    sys,
                    "argv",
                    [str(script), "--client-cert", str(cert), "--output", str(folder / "new.json")],
                ),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as exit_status,
            ):
                runpy.run_path(str(script), run_name="__main__")
            self.assertEqual(exit_status.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
