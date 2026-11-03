"""@brief Tests for the reproducible pinned receiver loopback harness."""

import io
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

import reference_loopback as reference
from stream_sender import run


class ReferenceLoopbackTests(unittest.TestCase):
    """@brief Verify pinned source handling, error counters and real loopback use."""

    def test_hash_mismatch_does_not_execute_source(self):
        """@brief Reject unexpected receiver bytes before importing them."""
        with (
            patch("reference_loopback.subprocess.check_output", return_value=b"unexpected"),
            self.assertRaisesRegex(ValueError, "hash mismatch"),
        ):
            reference.load_reference(Path("unused"))

    def test_clip_loop_repeats_and_empty_clip_stops(self):
        """@brief Reopen nonempty clips without buffering and stop on empty input."""
        with patch("reference_loopback.clip_frames", side_effect=lambda *_: (x for x in [1, 2])):
            frames = reference.loop_clip(Path("unused"), 30)
            self.assertEqual([next(frames) for _ in range(5)], [1, 2, 1, 2, 1])
            frames.close()
        with patch("reference_loopback.clip_frames", return_value=(x for x in ())):
            self.assertEqual(list(reference.loop_clip(Path("unused"), 30)), [])

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

    @unittest.skipUnless(os.environ.get("MOONBUB_REFERENCE"), "requires pinned MoonBub Git clone")
    def test_sender_recovers_from_lost_duplicate_and_reordered_udp_chunks(self):
        """@brief Corrupt three frames in a live loopback path; later frames recover."""
        original = reference.load_reference(Path(os.environ["MOONBUB_REFERENCE"]))

        class FaultingReassembler:
            """@brief Inject deterministic faults before the real receiver parser."""

            def __init__(self):
                """@brief Start with the pinned parser and no delayed datagram."""
                self.receiver, self.held = original.Reassembler(), None

            def accept(self, data):
                """@brief Drop, duplicate, or swap chunks in frames zero, two, four."""
                packet = original.parse_packet(data)
                if packet.frame_id == 0 and packet.offset == 1024:
                    return None
                if packet.frame_id == 2 and packet.offset == 1024:
                    self.receiver.accept(data)
                    return self.receiver.accept(data)
                if packet.frame_id == 4 and packet.offset == 1024:
                    self.held = data
                    return None
                if packet.frame_id == 4 and packet.offset == 2048:
                    try:
                        return self.receiver.accept(data)
                    finally:
                        if self.held is not None:
                            delayed, self.held = self.held, None
                            try:
                                self.receiver.accept(delayed)
                            except ValueError:
                                pass
                return self.receiver.accept(data)

        faulting = SimpleNamespace(Reassembler=FaultingReassembler, FEEDBACK=original.FEEDBACK)
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                reference_repo=Path("unused"),
                log=Path(directory) / "faults.jsonl",
                clip=None,
                fps=10,
                mbps=100,
                max_age_ms=500,
                quality=75,
                min_quality=20,
                frames=6,
            )
            image = Image.new("RGB", (720, 480), "red")
            with patch("reference_loopback.load_reference", return_value=faulting):
                result = reference.run_reference(args, iter([image] * 6))
            events = [json.loads(line) for line in args.log.read_text().splitlines()]
        accepted = [event["frame_id"] for event in events if event["event"] == "feedback"]
        self.assertEqual(accepted, [1, 3, 5])
        self.assertEqual(result["receiver"]["complete"], 3)
        self.assertGreater(result["receiver"]["invalid_datagrams"], 0)

    @unittest.skipUnless(os.environ.get("MOONBUB_REFERENCE"), "requires pinned MoonBub Git clone")
    def test_delayed_feedback_requires_a_fresh_probe(self):
        """@brief A late old ACK cannot resume video; a new probe ACK can."""
        original = reference.load_reference(Path(os.environ["MOONBUB_REFERENCE"]))

        class DelayedFeedback:
            """@brief Delay only the first ACK long enough to trigger sender probing."""

            delayed = False

            def pack(self, *args):
                """@brief Return the receiver's original feedback bytes after the delay."""
                if not self.delayed:
                    self.delayed = True
                    time.sleep(1.05)
                return original.FEEDBACK.pack(*args)

        delayed = SimpleNamespace(Reassembler=original.Reassembler, FEEDBACK=DelayedFeedback())
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                reference_repo=Path("unused"),
                log=Path(directory) / "delay.jsonl",
                clip=None,
                fps=10,
                mbps=100,
                max_age_ms=500,
                quality=75,
                min_quality=20,
                frames=25,
            )
            image = Image.new("RGB", (720, 480), "red")
            with patch("reference_loopback.load_reference", return_value=delayed):
                result = reference.run_reference(args, iter([image] * 25))
            events = [json.loads(line) for line in args.log.read_text().splitlines()]
        kinds = [event["event"] for event in events]
        self.assertIn("feedback_timeout", kinds)
        self.assertIn("feedback_restored", kinds)
        self.assertGreater(result["sender"]["counts"].get("unmatched_feedback", 0), 0)
        self.assertGreater(result["sender"]["counts"]["feedback_accepted"], 0)
        self.assertFalse(result["sender"]["feedback_probing"])

    @unittest.skipUnless(os.environ.get("MOONBUB_REFERENCE"), "requires pinned MoonBub Git clone")
    def test_restart_and_frame_wrap_against_same_reference_receiver(self):
        """@brief Two sender sessions recover with the same UDP source and wrapping IDs."""
        peer = reference.ReferencePeer(
            reference.load_reference(Path(os.environ["MOONBUB_REFERENCE"]))
        )
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reserved:
                reserved.bind(("127.0.0.1", 0))
                source_port = reserved.getsockname()[1]
            with tempfile.TemporaryDirectory() as directory:
                args = SimpleNamespace(
                    target="127.0.0.1",
                    port=peer.port,
                    source_port=source_port,
                    start_frame_id=0xFFFFFFFE,
                    log=Path(directory) / "first.jsonl",
                    fps=10,
                    mbps=100,
                    max_age_ms=500,
                    quality=75,
                    min_quality=20,
                    frames=2,
                )
                image = Image.new("RGB", (720, 480), "red")
                first = run(args, iter([image] * 2))
                args.start_frame_id, args.log = 0, Path(directory) / "second.jsonl"
                second = run(args, iter([image] * 2))
        finally:
            counts = peer.close()
        self.assertEqual(first["counts"]["feedback_accepted"], 2)
        self.assertEqual(second["counts"]["feedback_accepted"], 2)
        self.assertEqual(counts["complete"], 4)
        self.assertEqual(counts["invalid_datagrams"], 0)

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

    def test_loop_option_supplies_repeat_source_to_sender(self):
        """@brief The optional soak mode passes a looped clip iterator to the sender."""
        peer = Mock(port=1234)
        source = iter(["sample"])
        args = SimpleNamespace(
            reference_repo=Path("unused"),
            log=Path("unused"),
            clip=Path("clip"),
            fps=30,
            mbps=20,
            max_age_ms=200,
            quality=75,
            min_quality=20,
            frames=1,
            loop=True,
        )
        with (
            patch("reference_loopback.load_reference"),
            patch("reference_loopback.ReferencePeer", return_value=peer),
            patch("reference_loopback.loop_clip", return_value=source) as loop,
            patch("reference_loopback.run", return_value={}) as send,
        ):
            reference.run_reference(args)
        loop.assert_called_once_with(args.clip, args.fps)
        self.assertIs(send.call_args.args[1], source)
        peer.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
