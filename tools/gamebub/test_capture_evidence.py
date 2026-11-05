"""@brief Verify STOP capture inspection without executing Wireshark or sending packets."""

import subprocess
import unittest
from unittest.mock import Mock

from av_protocol import Packet
from capture_evidence import verify_stop


class CaptureEvidenceTests(unittest.TestCase):
    """@brief Bind STOP identity and source, preserving failed/absent evidence."""

    def test_exact_stop_filter_and_numeric_records(self):
        """@brief Match the complete CRC-protected datagram, not any other session STOP."""
        packet = Packet(b"MSC1", 4, 123, sequence=7).encode()
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "8\t1793860000.123456\n", ""))
        result = verify_stop(
            "capture.pcapng", packet, "127.0.0.1", tshark="tshark.exe", runner=runner
        )
        self.assertTrue(result["stop_packet_verified"])
        command = runner.call_args.args[0]
        self.assertIn(packet.hex(":"), command[command.index("-Y") + 1])
        self.assertIn("ip.src == 127.0.0.1", command[command.index("-Y") + 1])
        self.assertEqual(result["stop_packets"][0]["epoch_seconds"], "1793860000.123456")
        self.assertTrue(runner.call_args.kwargs["check"])

    def test_absent_stop_is_not_verified(self):
        """@brief An empty matching set does not establish captured STOP coverage."""
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        result = verify_stop(
            "capture.pcapng",
            Packet(b"MSC1", 4, 1).encode(),
            "127.0.0.1",
            tshark="tshark",
            runner=runner,
        )
        self.assertFalse(result["stop_packet_verified"])

    def test_wrong_packet_or_source_rejected_before_execution(self):
        """@brief Reject a different control class or an unusable wildcard source."""
        runner = Mock()
        for packet, source in (
            (Packet(b"MSC1", 1, 1).encode(), "127.0.0.1"),
            (Packet(b"MSC1", 4, 1).encode(), "0.0.0.0"),
        ):
            with self.assertRaises(ValueError):
                verify_stop("capture", packet, source, tshark="tshark", runner=runner)
        runner.assert_not_called()

    def test_invalid_capture_fields_and_tool_failures_propagate(self):
        """@brief Corrupt inspection output or a failed tool never becomes verified evidence."""
        packet = Packet(b"MSC1", 4, 1).encode()
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "0\t-1", ""))
        with self.assertRaises(ValueError):
            verify_stop("capture", packet, "127.0.0.1", tshark="tshark", runner=runner)
        runner.side_effect = subprocess.TimeoutExpired("tshark", 30)
        with self.assertRaises(subprocess.TimeoutExpired):
            verify_stop("capture", packet, "127.0.0.1", tshark="tshark", runner=runner)


if __name__ == "__main__":
    unittest.main()
