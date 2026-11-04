"""@brief Optional real native full-body fixture and metadata boundary regressions."""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from verify_v20_body import descendant, descriptors


@unittest.skipUnless(
    os.environ.get("GAMEBUB_V20_EXE") and os.environ.get("GAMEBUB_V20_BODY_FIXTURES"),
    "Set GAMEBUB_V20_EXE and GAMEBUB_V20_BODY_FIXTURES for offline native replay",
)
class BodyCliTests(unittest.TestCase):
    """@brief Reject malformed real fixture metadata and oracles without hardware use."""

    def setUp(self):
        """@brief Copy a frozen mandatory key privately; never mutate retained vectors."""
        self.temp = tempfile.TemporaryDirectory(prefix="gamebub-body-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = str(Path(os.environ["GAMEBUB_V20_EXE"]).resolve(strict=True))
        self.fixtures = Path(os.environ["GAMEBUB_V20_BODY_FIXTURES"]).resolve(strict=True)
        self.load("mass-effect-2600-mandatory-00")

    def load(self, label):
        """@brief Load one exact case with its declared predecessor banks."""
        case_path = self.fixtures / "cases" / f"{label}.json"
        self.case = json.loads(case_path.read_text())
        for descriptor in descriptors(self.case):
            shutil.copyfile(
                descendant(case_path.parent, descriptor["path"]), self.root / descriptor["path"]
            )

    def run_case(self, case=None, expected=1, message=None):
        """@brief Execute the native reader/decoder and inspect its actual exit/report."""
        path = self.root / "case.json"
        path.write_text(json.dumps(self.case if case is None else case), encoding="utf-8")
        result = subprocess.run(
            [self.exe, "--body-case", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        if message:
            self.assertIn(message, result.stderr)
        return json.loads(result.stdout) if expected == 0 else result.stderr

    def mutate_blob(self, descriptor, index=0, mask=1):
        """@brief Change a private raw oracle and update its fixture hash explicitly."""
        path = self.root / descriptor["path"]
        raw = bytearray(path.read_bytes())
        raw[index] ^= mask
        path.write_bytes(raw)
        descriptor["sha256"] = hashlib.sha256(raw).hexdigest()

    def test_real_key_exact_oracles(self):
        """@brief Native full-body success distinguishes original HUD and base samples."""
        report = self.run_case(expected=0)
        self.assertEqual(report["mandatory_hud_words_verified"], 21120)
        self.assertEqual(report["yuv_samples"], 518400)
        self.assertTrue(report["post_banks_exact"])

    def test_metadata_path_type_hash_and_geometry_boundaries(self):
        """@brief Reject traversals, bad array descriptions and malformed signed metadata."""
        original = json.dumps(self.case)
        changes = (
            (lambda c: c.update(schema="unknown"), "schema"),
            (lambda c: c["geometry"].update(width=-1), "negative fixture integer"),
            (lambda c: c["geometry"].update(width=721), "integer bound"),
            (lambda c: c["geometry"].update(height=479), "geometry"),
            (lambda c: c.update(id=True), "integer type"),
            (lambda c: c.update(last_frame=-2), "last frame bound"),
            (lambda c: c.update(last_frame=2**64 - 1), "integer bound"),
            (lambda c: c.update(last_frame="0"), "last frame type"),
            (lambda c: c["packet"].update(path="../escape"), "path traversal"),
            (lambda c: c["packet"].update(path="C:/escape"), "path encoding"),
            (lambda c: c["packet"].update(path=""), "path encoding"),
            (lambda c: c["packet"].update(path="folder//packet"), "relative path"),
            (lambda c: c["packet"].update(sha256="0" * 64), "size/hash"),
            (lambda c: c["packet"].update(bytes=49153), "integer bound"),
            (lambda c: c["packet"].update(bytes=1), "fixture allocation bound"),
            (lambda c: c["decoded_yuv"][0].update(dtype="<u2"), "dtype/shape"),
            (lambda c: c["decoded_yuv"][0].update(shape=[480, 719]), "dtype/shape"),
            (lambda c: c.update(decoded_yuv=[]), "plane count"),
        )
        for mutation, message in changes:
            with self.subTest(message=message):
                self.case = json.loads(original)
                mutation(self.case)
                self.run_case(message=message)

    def test_frozen_oracle_mismatches_and_decoder_rejection(self):
        """@brief Hash-valid changed oracles must still fail exact native comparisons."""
        for field, index, mask, message in (
            ("display_rgb565", 0, 1, "display RGB565 mismatch"),
            ("ack", 0, 1, "AF03 bytes mismatch"),
            ("source_rgb", 3 * (54 * 720 + 22), 8, "mandatory source HUD mismatch"),
        ):
            with self.subTest(field=field):
                self.load("mass-effect-2600-mandatory-00")
                self.mutate_blob(self.case[field], index, mask)
                self.run_case(message=message)
        self.load("mass-effect-2600-mandatory-00")
        self.mutate_blob(self.case["decoded_yuv"][0])
        self.run_case(message="decoded YUV/identity mismatch")
        self.load("mass-effect-2600-mandatory-00")
        self.mutate_blob(self.case["packet"])
        self.run_case(message="body decode:")
        self.load("mass-effect-2600-mandatory-00")
        self.case["last_frame"] = 0
        self.run_case(message="body decode:")
        self.load("mass-effect-2600-mandatory-00")
        self.case["post_banks"]["0"]["tag"] = "0" * 32
        self.run_case(message="bank identity mismatch")

    def test_prebank_domains_and_tag_identity(self):
        """@brief A P fixture cannot decode from malformed or different predictor storage."""
        for tag, message in (
            ("0", "tag size"),
            ("g" * 32, "tag digit"),
            ("0" * 32, "prebank tag mismatch"),
        ):
            self.load("mass-effect-2600-mandatory-01")
            self.case["pre_banks"]["0"]["tag"] = tag
            self.run_case(message=message)
        self.load("mass-effect-2600-mandatory-01")
        self.mutate_blob(self.case["pre_banks"]["0"]["planes"][0], index=1, mask=1)
        self.run_case(message="sample domain")

    def test_independent_tiny_raw_coefficients_and_patch_palette_modes(self):
        """@brief Exercise raw CP02 and every HP01 palette width through the actual CLI."""
        for mode, width, colors in ((0, 2, 0), (1, 2, 2), (2, 4, 3), (4, 8, 16), (8, 18, 17)):
            with self.subTest(mode=mode):
                self.case = self.tiny_case(width, 2, mode, colors)
                report = self.run_case(expected=0)
                self.assertEqual(report["scope"], "full_body_fixture")
                self.assertEqual(report["display_words"], width * 2)

    def tiny_case(self, width, height, mode, colors):
        """@brief Build an independent small grayscale key and exact HP01 overlay oracle."""

        def seal(raw):
            """@brief Append an independently computed little-endian IEEE trailer."""
            return bytes(raw) + struct.pack("<I", zlib.crc32(raw))

        def descriptor(name, raw, dtype=None, shape=None):
            """@brief Write one synthetic oracle and its explicit byte/array description."""
            self.file_blob(name, raw)
            value = {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            if dtype is not None:
                value.update(dtype=dtype, shape=shape)
            return value

        sizes = [(width, height), (width // 2, height // 2), (width // 2, height // 2)]
        expected = [struct.pack("<h", 128) * (w * h) for w, h in sizes]
        tag = hashlib.sha256(struct.pack("<HH", width, height) + b"".join(expected)).digest()[:16]
        inner = bytearray(46)
        inner[:6] = b"GM01\x01\x01"
        struct.pack_into("<IIIHH", inner, 6, 1, 0, 0xFFFFFFFF, width, height)
        mw, mh = (width + 15) // 16, (height + 15) // 16
        struct.pack_into("<HHI", inner, 26, mw, mh, (mw * mh + 3) // 4)
        inner += bytes((mw * mh + 3) // 4)
        for index, (w, h) in enumerate(sizes):
            bw, bh = (w + 7) // 8, (h + 7) // 8
            cp = bytearray(22)
            cp[:5] = b"CP02\x01"
            struct.pack_into("<IH", cp, 6, bw * bh, bw)
            struct.pack_into("<I", cp, 14, bw * bh * 128)
            cp = seal(cp + bytes(bw * bh * 128))
            struct.pack_into("<I", inner, 34 + index * 4, len(cp))
            inner += cp
        inner = seal(inner)
        pixels = width * height
        words = [i % colors for i in range(pixels)] if mode else [0, 65535] * (pixels // 2)
        patch = bytearray(24)
        patch[:6] = b"HP01\x01" + bytes([mode])
        struct.pack_into("<HHH", patch, 10, width, height, colors)
        palette = b"".join(struct.pack("<H", i) for i in range(colors))
        if mode:
            bits = "".join(f"{i:0{mode}b}" for i in words)
            bits += "0" * (-len(bits) % 8)
            payload = int(bits, 2).to_bytes(len(bits) // 8, "big")
        else:
            payload = b"".join(struct.pack("<H", word) for word in words)
        struct.pack_into("<II", patch, 16, pixels, len(payload))
        patch = seal(patch + palette + payload)
        blob = struct.pack("<I", len(patch)) + patch
        packet = bytearray(61)
        packet[:6] = b"AR03\x03\x01"
        struct.pack_into("<II", packet, 6, 1, 0)
        packet[14] = 255
        struct.pack_into("<I", packet, 16, 0xFFFFFFFF)
        packet[36:52] = tag
        struct.pack_into("<IBI", packet, 52, len(inner), 1, len(blob))
        packet = seal(packet + inner + blob)
        ack = bytearray(39)
        ack[:6] = b"AF03\x03\x01"
        struct.pack_into("<III", ack, 6, 1, 0, struct.unpack_from("<I", packet, len(packet) - 4)[0])
        ack[23:39] = tag
        return {
            "schema": "gamebub-v20-body-case-v1",
            "label": f"independent-palette-{mode}",
            "policy": "baseline",
            "id": 0,
            "epoch": 1,
            "last_frame": -1,
            "geometry": {"width": width, "height": height},
            "packet": descriptor("tiny.ar03", packet),
            "ack": descriptor("tiny.af03", seal(ack)),
            "source_rgb": descriptor(
                "tiny.rgb", bytes([128]) * pixels * 3, "|u1", [height, width, 3]
            ),
            "decoded_yuv": [
                descriptor(f"tiny.yuv{i}", raw, "<i2", [h, w])
                for i, (raw, (w, h)) in enumerate(zip(expected, sizes, strict=True))
            ],
            "display_rgb565": descriptor(
                "tiny.display",
                b"".join(struct.pack("<H", word) for word in words),
                "<u2",
                [height, width],
            ),
            "pre_banks": {"0": None, "1": None},
            "post_banks": {"0": {"id": 0, "tag": tag.hex()}, "1": None},
        }

    def file_blob(self, name, raw):
        """@brief Store only a private synthetic file beside its case JSON."""
        (self.root / name).write_bytes(raw)
