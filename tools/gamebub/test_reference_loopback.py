"""@brief Tests for the reproducible pinned receiver loopback harness."""

import io
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

import reference_loopback as reference


class ReferenceLoopbackTests(unittest.TestCase):
    """@brief Verify pinned source handling, error counters and real loopback use."""

    def test_hash_mismatch_does_not_execute_source(self):
        """@brief Reject unexpected receiver bytes before importing them."""
        with (
            patch("reference_loopback.subprocess.check_output", return_value=b"unexpected"),
            self.assertRaisesRegex(ValueError, "hash mismatch"),
        ):
            reference.load_reference(Path("unused"))

    def test_receiver_counts_bad_packets_and_reply_errors(self):
        """@brief Invalid data and failed ACK sends are bounded and counted."""
        peer = reference.ReferencePeer.__new__(reference.ReferencePeer)
        peer.stop = threading.Event()
        peer.stats = {"complete": 0, "invalid_datagrams": 0, "reply_errors": 0}
        packet = SimpleNamespace(frame_id=1, capture_us=2)
        decoder = Mock()
        decoder.accept.side_effect = [ValueError("bad"), None, (packet, b"jpeg")]
        peer.reference = SimpleNamespace(Reassembler=lambda: decoder, FEEDBACK=Mock())
        peer.reference.FEEDBACK.pack.return_value = b"ack"
        peer.socket = Mock()
        peer.socket.recvfrom.side_effect = [
            TimeoutError(),
            (b"bad", "peer"),
            (b"part", "peer"),
            (b"end", "peer"),
        ]

        def failed_send(*args):
            """@brief End the test after a simulated failed response."""
            peer.stop.set()
            raise OSError("unreachable")

        peer.socket.sendto.side_effect = failed_send
        peer._serve()
        self.assertEqual(peer.stats, {"complete": 1, "invalid_datagrams": 1, "reply_errors": 1})

    def test_command_validation_and_status(self):
        """@brief Command errors and exit status do not require a network peer."""
        args = ["--reference-repo", "unused", "--clip", "unused", "--log", "unused"]
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            reference.main([*args, "--frames", "0"])
        with (
            patch("reference_loopback.run_reference", side_effect=ValueError("bad")),
            patch("sys.stderr", new_callable=io.StringIO),
            self.assertRaises(SystemExit),
        ):
            reference.main(args)
        with (
            patch("reference_loopback.run_reference", return_value={"receiver": {"complete": 0}}),
            patch("builtins.print"),
        ):
            self.assertEqual(reference.main(args), 2)
        with (
            patch("reference_loopback.run_reference", return_value={"receiver": {"complete": 1}}),
            patch("builtins.print"),
        ):
            self.assertEqual(reference.main(args), 0)

    @unittest.skipUnless(os.environ.get("MOONBUB_REFERENCE"), "requires pinned MoonBub Git clone")
    def test_actual_pinned_reference_reassembles_sender_frames(self):
        """@brief Two actual sender frames reach the hash-checked receiver implementation."""
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                reference_repo=Path(os.environ["MOONBUB_REFERENCE"]),
                log=Path(directory) / "run.jsonl",
                clip=None,
                fps=10,
                mbps=100,
                max_age_ms=500,
                quality=75,
                min_quality=20,
                frames=2,
            )
            image = Image.new("RGB", (720, 480), "red")
            result = reference.run_reference(args, iter([image, image]))
        self.assertEqual(result["receiver"]["complete"], 2)
        self.assertEqual(result["receiver"]["invalid_datagrams"], 0)
        self.assertEqual(result["sender"]["counts"]["feedback_accepted"], 2)
        self.assertFalse(result["hardware_playback_verified"])

    def test_git_error_propagates(self):
        """@brief A missing source revision is reported rather than replaced silently."""
        with (
            patch(
                "reference_loopback.subprocess.check_output",
                side_effect=subprocess.CalledProcessError(1, "git"),
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            reference.load_reference(Path("missing"))

    def test_sender_error_still_closes_peer(self):
        """@brief A failed source or sender cannot leave a reference socket running."""
        peer = Mock(port=1234)
        args = SimpleNamespace(
            reference_repo=Path("unused"),
            log=Path("unused"),
            clip=None,
            fps=30,
            mbps=20,
            max_age_ms=200,
            quality=75,
            min_quality=20,
            frames=1,
        )
        with (
            patch("reference_loopback.load_reference"),
            patch("reference_loopback.ReferencePeer", return_value=peer),
            patch("reference_loopback.run", side_effect=OSError("capture failed")),
            self.assertRaises(OSError),
        ):
            reference.run_reference(args)
        peer.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
