"""@brief Optional integration test against the pinned MoonBub Rust receiver parser."""

import hashlib
import os
import re
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from msv1 import frame_datagrams, parse_feedback

REVISION = "75f8497b6ffefadd8c0403728b93ccfbbfa02f52"
REFERENCE = os.environ.get("MOONBUB_REFERENCE")


@unittest.skipUnless(REFERENCE, "Set MOONBUB_REFERENCE to the pinned receiver repository")
class ReceiverFirmwareIntegration(unittest.TestCase):
    """@brief Compile and exercise the receiver parser with host-generated packets."""

    def test_rust_receiver_acceptance_and_recovery(self):
        """@brief Verify valid frame, CRC failure, newer-SOF recovery, and ID wrap."""

        def read_source(path):
            """@brief Read source directly from the user-supplied pinned Git revision."""
            return subprocess.check_output(["git", "-C", REFERENCE, "show", f"{REVISION}:{path}"])

        protocol = read_source("firmware/handheld/src/streaming/protocol.rs")
        self.assertEqual(
            hashlib.sha256(protocol).hexdigest(),
            "32a91ffaf0b39a82f11036be7e501765cd3f9fed6905c27b6efc01f358d79e64",
        )
        source = read_source("evidence/integration/firmware_protocol_harness.rs").decode("utf-8")
        source, count = re.subn(
            r'#\[path\s*=\s*"[^"]+"\]', '#[path = "protocol.rs"]', source, count=1
        )
        self.assertEqual(count, 1)
        jpeg = (Path(__file__).parent / "fixtures/frame-00000000-420-r0.jpg").read_bytes()
        self.assertEqual(
            hashlib.sha256(jpeg).hexdigest(),
            "b327b1c2e2af7988e66f2ae570534a91c4526bbb53739ee5809f51e123228fb6",
        )
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "protocol.rs").write_bytes(protocol)
            (directory / "harness.rs").write_text(source, encoding="utf-8")
            executable = directory / ("harness.exe" if os.name == "nt" else "harness")
            subprocess.run(
                [
                    "rustc",
                    "--edition=2021",
                    "-O",
                    str(directory / "harness.rs"),
                    "-o",
                    str(executable),
                ],
                check=True,
            )

            def execute(packets):
                """@brief Feed length-prefixed datagrams to the compiled reference parser."""
                wire = b"".join(struct.pack("!I", len(packet)) + packet for packet in packets)
                result = subprocess.run(
                    [str(executable)], input=wire, capture_output=True, check=True
                )
                lines = result.stdout.decode("ascii").splitlines()
                return [tuple(map(int, line.split())) for line in lines[:-1]], bytes.fromhex(
                    lines[-1]
                )

            frame = list(frame_datagrams(jpeg, 7, 1234567890123))
            rows, feedback = execute(frame)
            self.assertEqual(len(rows), len(frame))
            self.assertTrue(all(row[:2] == (1, 1) for row in rows))
            self.assertEqual(rows[-1][2:4], (1, 7))
            self.assertEqual(parse_feedback(feedback).buttons, 0x845)
            damaged = list(frame)
            last = bytearray(damaged[-1])
            last[-1] ^= 1
            damaged[-1] = bytes(last)
            rows, _ = execute(damaged)
            self.assertEqual(rows[-1][:2], (1, 0))
            newer = list(frame_datagrams(jpeg, 8, 1234567890124))
            rows, _ = execute(frame[:2] + newer)
            self.assertTrue(all(row[:2] == (1, 1) for row in rows))
            self.assertEqual(rows[-1][2:4], (1, 8))
            wrapped = list(frame_datagrams(jpeg, 0xFFFFFFFF, 1)) + list(frame_datagrams(jpeg, 0, 2))
            rows, _ = execute(wrapped)
            self.assertEqual(rows[-1][2:4], (1, 0))


if __name__ == "__main__":
    unittest.main()
