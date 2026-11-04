"""@brief Independent Windows serialization checks against pinned MoonBub AV v1 vectors."""

import hashlib
import json
import runpy
import struct
import unittest
import zlib
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from audio_codec import decode_block
from av_protocol import HEADER, INPUT, NONCE, Packet, decode, input_status
from verify_av_vectors import verify

FIXTURES = Path(__file__).parent / "fixtures" / "av-v1"
VECTORS = json.loads((FIXTURES / "vectors.json").read_text())
COOKIE = int(VECTORS["cookie_hex"], 16)
HOST_NONCE = int(VECTORS["nonce_hex"], 16)


def repair_crc(raw):
    """@brief Recalculate CRC after deliberate schema corruption, isolating validation."""
    raw = bytes(raw[:40]) + bytes(4) + bytes(raw[44:])
    return raw[:40] + struct.pack("!I", zlib.crc32(raw) & 0xFFFFFFFF) + raw[44:]


class AvProtocolTests(unittest.TestCase):
    """@brief Verify all frozen byte vectors, field offsets and negative schemas."""

    def test_all_golden_datagrams_byte_exact(self):
        """@brief Seven independently constructed packets match the published bytes and hashes."""
        packets = {
            "hello": Packet(b"MSC1", 1, HOST_NONCE, flags=1),
            "offer": Packet(b"MSR1", 1, COOKIE, flags=1, payload=NONCE.pack(HOST_NONCE)),
            "start": Packet(
                b"MSC1", 2, COOKIE, sequence=1, flags=1, payload=NONCE.pack(HOST_NONCE)
            ),
            "keep": Packet(b"MSC1", 3, COOKIE, sequence=2),
            "audio": Packet(b"MSA1", 1, COOKIE, payload=(FIXTURES / "stereo-505.ima").read_bytes()),
            "input": Packet(
                b"MSI1",
                1,
                COOKIE,
                sequence=42,
                payload=INPUT.pack(0x881, 1, 0, 1010, 505, 0, 7, 0x4D424F50),
            ),
            "stop": Packet(b"MSC1", 4, COOKIE, sequence=3),
        }
        self.assertEqual(HEADER.size, 48)
        for name, packet in packets.items():
            with self.subTest(name=name):
                raw = packet.encode()
                self.assertEqual(raw, bytes.fromhex(VECTORS["vectors"][name]["hex"]))
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(), VECTORS["vectors"][name]["sha256"]
                )
                self.assertEqual(decode(raw), packet)
        self.assertEqual(len(packets["audio"].encode()), 560)

    def test_fixture_provenance_and_required_pcm_oracle(self):
        """@brief The product-rounded decoder must exactly reconstruct the frozen PCM oracle."""
        provenance = json.loads((FIXTURES / "provenance.json").read_text())
        self.assertEqual(provenance["revision"], "dff5452871e911a60c8a278134e1f6fabdaa95e2")
        for name, digest in provenance["sha256"].items():
            self.assertEqual(hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), digest)
        decoded = decode_block((FIXTURES / "stereo-505.ima").read_bytes())
        expected = (FIXTURES / "stereo-505-decoded.s16le").read_bytes()
        self.assertEqual(len(decoded), 2020)
        self.assertEqual(decoded, expected)
        self.assertEqual(hashlib.sha256(expected).hexdigest(), VECTORS["decoded_pcm_sha256"])
        result = verify()
        self.assertTrue(result["wire_match"])
        self.assertTrue(result["pcm_match"])
        self.assertTrue(result["complete_conformance"])

    def test_verifier_returns_failure_on_pcm_mismatch(self):
        """@brief Passing unit tests must not turn a failed conformance check into success."""
        import verify_av_vectors as verifier

        with (
            patch.object(verifier, "decode_block", return_value=bytes(2020)),
            patch("builtins.print"),
        ):
            mismatch = verifier.verify()
            self.assertTrue(mismatch["wire_match"])
            self.assertFalse(mismatch["pcm_match"])
            self.assertFalse(mismatch["complete_conformance"])
            self.assertEqual(verifier.main([]), 2)
        for conforms in (False, True):
            with (
                patch.object(verifier, "verify", return_value={"complete_conformance": conforms}),
                patch("builtins.print"),
            ):
                self.assertEqual(verifier.main([]), 0 if conforms else 2)
        with (
            patch("sys.argv", ["verify_av_vectors.py"]),
            patch("builtins.print"),
            self.assertRaises(SystemExit) as stopped,
        ):
            runpy.run_path(verifier.__file__, run_name="__main__")
        self.assertEqual(stopped.exception.code, 0 if verify()["complete_conformance"] else 2)

    def test_crc_covers_every_header_and_payload_byte(self):
        """@brief A bit flip anywhere in the 560-byte packet is rejected without repair."""
        wire = bytes.fromhex(VECTORS["vectors"]["audio"]["hex"])
        for offset in range(len(wire)):
            raw = bytearray(wire)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                decode(bytes(raw))

    def test_header_schema_even_with_repaired_crc(self):
        """@brief Wrong version/size/rate/samples/length/reserved are not hidden by valid CRC."""
        wire = bytes.fromhex(VECTORS["vectors"]["hello"]["hex"])
        for offset in (4, 7, 20, 24, 26, 44):
            raw = bytearray(wire)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                decode(repair_crc(raw))
        for raw in (None, bytearray(wire), b"", wire[:-1], wire + b"x", bytes(561)):
            with self.assertRaises(ValueError):
                decode(raw)

    def test_packet_schema_rejection(self):
        """@brief Validate integer bounds and all class-specific flags/payload constraints."""
        hello = Packet(b"MSC1", 1, 1)
        changes = (
            [{"session": value} for value in (0, -1, 2**64, True)]
            + [{"sequence": value} for value in (-1, 2**32, True)]
            + [{"timestamp_us": value} for value in (-1, 2**64, True)]
            + [
                {"magic": "MSC1"},
                {"magic": b"MSF1"},
                {"kind": True},
                {"kind": 5},
                {"payload": bytearray()},
                {"payload": b"x"},
                {"flags": -1},
                {"flags": True},
                {"flags": 2},
                {"sequence": 1},
            ]
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(hello, **change).encode()
        for packet in (
            Packet(b"MSC1", 2, 1, payload=NONCE.pack(1)),
            Packet(b"MSR1", 1, 1, sequence=1, payload=NONCE.pack(1)),
            Packet(b"MSR1", 1, 1, payload=bytes(8)),
            Packet(b"MSC1", 3, 1, flags=1),
            Packet(b"MSA1", 1, 1, payload=bytes(511)),
            Packet(b"MSI1", 1, 1, payload=INPUT.pack(4096, 0, 0, 0, 0, 0, 1, 0)),
            Packet(b"MSI1", 1, 1, payload=INPUT.pack(0, 0, 0, 0, 0, 0, 8, 0)),
        ):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                packet.encode()

    def test_control_wrap_not_rejected_statelessly_and_status_validity(self):
        """@brief Wrapped control0/1 are schema-valid; invalid FPGA snapshots hide counters."""
        for sequence in (0, 1, 0xFFFFFFFF):
            packet = Packet(b"MSC1", 3, 1, sequence=sequence, timestamp_us=123456789)
            self.assertEqual(decode(packet.encode()), packet)
        packet = Packet(b"MSI1", 1, 1, payload=INPUT.pack(1, 2, 3, 4, 5, 6, 1, 7))
        status = input_status(packet)
        self.assertEqual(status["rejected_or_unconfirmed_audio_blocks"], 3)
        self.assertIsNone(status["queued_pcm_frames"])
        self.assertIsNone(status["played_pcm_frames"])
        self.assertIsNone(status["underruns"])
        valid = replace(packet, payload=INPUT.pack(1, 2, 3, 4, 5, 6, 7, 7))
        self.assertEqual(input_status(valid)["played_pcm_frames"], 5)
        with self.assertRaises(ValueError):
            input_status(Packet(b"MSC1", 1, 1))


if __name__ == "__main__":
    unittest.main()
