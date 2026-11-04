"""@brief Optional real Windows CLI regression tests; no network or hardware access."""

import json
import os
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path


@unittest.skipUnless(
    os.environ.get("GAMEBUB_V20_EXE"), "Set GAMEBUB_V20_EXE to the built offline tool"
)
class V20CliTests(unittest.TestCase):
    """@brief Exercise native file/argument errors and exact bounded reports."""

    def setUp(self):
        """@brief Use a fresh fixture directory for every native subprocess test."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.exe = Path(os.environ["GAMEBUB_V20_EXE"]).resolve(strict=True)

    def file(self, name, data):
        """@brief Write one private test input without touching retained vectors."""
        path = self.root / name
        path.write_bytes(data)
        return str(path)

    def run_cli(self, *args, code=0):
        """@brief Require a finite exit with the declared success/rejection category."""
        result = subprocess.run(
            [str(self.exe), *args], capture_output=True, text=True, timeout=10, check=False
        )
        self.assertEqual(result.returncode, code, result.stderr)
        return json.loads(result.stdout) if code == 0 else result.stderr

    def test_inverse_success_and_file_boundaries(self):
        """@brief Match multiple blocks; reject truncation, unequal arrays and missing files."""
        source = self.file("input", bytes(512))
        expected = self.file("expected", bytes(512))
        self.assertEqual(
            self.run_cli("--inverse", source, expected),
            {"scope": "inverse_only", "blocks": 2, "samples": 128},
        )
        missing = str(self.root / "absent")
        self.run_cli("--inverse", missing, expected, code=2)
        self.run_cli("--inverse", source, missing, code=2)
        self.run_cli("--inverse", self.file("short", b"x"), expected, code=2)
        self.run_cli("--inverse", source, self.file("short-gold", bytes(257)), code=2)
        self.run_cli("--inverse", source, self.file("long-gold", bytes(513)), code=2)
        self.run_cli("--inverse", self.file("empty", b""), expected, code=2)
        self.run_cli("--inverse", source, self.file("bad-gold", bytes(511) + b"x"), code=1)
        self.run_cli(
            "--inverse",
            self.file("illegal", struct.pack("<i", 522241) + bytes(252)),
            self.file("one-block-gold", bytes(256)),
            code=1,
        )

    def test_packet_acceptance_and_read_failures(self):
        """@brief Success identifies only envelope checks, including the maximum AR03 size."""
        for ack, size in ((True, 43), (False, 65), (False, 49152)):
            raw = bytearray(size)
            raw[:6] = b"AF03\x03\x01" if ack else b"AR03\x03\x01"
            if not ack:
                struct.pack_into("<I", raw, 52, size - 65)
            struct.pack_into("<I", raw, size - 4, zlib.crc32(raw[:-4]))
            switch = "--af03" if ack else "--ar03"
            packet = self.file(f"packet-{size}", raw)
            self.assertEqual(
                self.run_cli(switch, packet), {"scope": "envelope_only", "bytes": size}
            )
            raw[-1] ^= 1
            self.run_cli(switch, self.file(f"bad-{size}", raw), code=1)
        self.run_cli("--ar03", self.file("oversize", bytes(49154)), code=1)
        self.run_cli("--af03", str(self.root / "missing"), code=2)
        self.run_cli("--ar03", self.file("empty-packet", b""), code=2)

    def test_usage(self):
        """@brief Wrong mode and argument counts fail without opening sockets or devices."""
        for args in ((), ("--help",), ("--inverse", "one"), ("--unknown", "a", "b")):
            self.assertIn("Usage:", self.run_cli(*args, code=2))
