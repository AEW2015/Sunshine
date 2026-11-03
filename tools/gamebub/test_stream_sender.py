"""@brief Localhost tests for continuous receiver-compatible video transmission."""

import io
import json
import socket
import tempfile
import threading
import unittest
import zlib
from collections import Counter, OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from msv1 import FEEDBACK, VIDEO, Pacer
from pipeline import Frame
from stream_sender import Session, main, run


class StreamSenderTests(unittest.TestCase):
    """@brief Exercise capture, JPEG, packetization and ingress feedback on loopback."""

    def test_loopback_frames_and_feedback(self):
        """@brief A receiver reassembles complete CRC-checked JPEGs and acknowledges ingress."""
        completed, errors = [], []
        stop = threading.Event()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(0.05)

            def peer():
                """@brief Minimal strict loopback receiver, not an FPGA simulation."""
                current = bytearray()
                while not stop.is_set():
                    try:
                        packet, address = receiver.recvfrom(2048)
                    except TimeoutError:
                        continue
                    fields = VIDEO.unpack(packet[: VIDEO.size])
                    _, _, _, flags, frame, width, height, total, offset, size, _, crc, stamp = (
                        fields
                    )
                    if flags & 1:
                        current = bytearray()
                    if offset != len(current) or size != len(packet) - VIDEO.size:
                        errors.append("invalid chunk")
                        continue
                    current.extend(packet[VIDEO.size :])
                    if flags & 2:
                        if (
                            (width, height) != (720, 480)
                            or len(current) != total
                            or zlib.crc32(current) != crc
                        ):
                            errors.append("invalid frame")
                        else:
                            completed.append(frame)
                            receiver.sendto(
                                FEEDBACK.pack(b"MSF1", 1, 0, 0, frame, 0, len(completed), 0, stamp),
                                address,
                            )

            thread = threading.Thread(target=peer)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as directory:
                    args = SimpleNamespace(
                        target="127.0.0.1",
                        port=receiver.getsockname()[1],
                        log=Path(directory) / "run.jsonl",
                        fps=10,
                        mbps=100,
                        max_age_ms=500,
                        quality=75,
                        min_quality=20,
                        frames=4,
                    )
                    source = iter([Image.new("RGB", (720, 480), (i * 40, 0, 0)) for i in range(4)])
                    result = run(args, source)
                    events = [json.loads(line) for line in args.log.read_text().splitlines()]
            finally:
                stop.set()
                thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(completed, [0, 1, 2, 3])
        self.assertEqual(result["counts"]["feedback_accepted"], 4)
        self.assertEqual(result["pipeline"]["counts"]["sent"], 4)
        self.assertFalse(result["end_to_end_verified"])
        self.assertEqual(sum(event["event"] == "send" for event in events), 4)
        self.assertEqual(events[-1]["event"], "summary")

    def test_adaptation_and_network_errors(self):
        """@brief Congestion and encoder/socket failures lower quality within bounds."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), io.StringIO(), Mock()
        s.quality, s.min_quality, s.max_quality = 75, 20, 75
        s.rate, s.fps, s.age_ns, s.pacer = 3000, 30, 100, Pacer()
        s.pending, s.counts = OrderedDict(), Counter()
        with patch("stream_sender.encode", return_value=(b"x" * 100, {})):
            s._encode(None)
        self.assertEqual(s.quality, 70)
        with patch("stream_sender.encode", return_value=(b"x", {})):
            s._encode(None)
        self.assertEqual(s.quality, 71)
        with patch("stream_sender.encode", return_value=(b"x" * 40, {})):
            s._encode(None)
        self.assertEqual(s.quality, 71)
        with (
            patch("stream_sender.encode", side_effect=OverflowError("too big")),
            self.assertRaises(OverflowError),
        ):
            s._encode(None)
        self.assertEqual(s.quality, 66)
        frame = Frame(2, 10, 20, Image.new("RGB", (720, 480)))
        with patch("stream_sender.send_frame", return_value=(False, 40)):
            self.assertFalse(s._send(frame, b"x"))
        self.assertEqual(s.quality, 61)
        with (
            patch("stream_sender.send_frame", side_effect=OSError("closed")),
            self.assertRaises(OSError),
        ):
            s._send(frame, b"x")
        self.assertEqual(s.counts["socket_failures"], 1)
        self.assertEqual(len(s.pending), 0)
        s.pending.update(((i, i), None) for i in range(512))
        with patch("stream_sender.send_frame", return_value=(True, 40)):
            self.assertTrue(s._send(frame, b"x"))
        self.assertEqual(len(s.pending), 512)
        self.assertEqual(s.counts["feedback_evicted"], 1)

    def test_feedback_filters_unmatched_and_reacts_to_busy(self):
        """@brief Bad or old feedback cannot acknowledge a frame; busy lowers quality."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), io.StringIO(), threading.Event()
        s.pending, s.counts = OrderedDict({(4, 10): None}), Counter()
        s.quality, s.min_quality = 75, 20
        s.sock = Mock()
        s.sock.recv.side_effect = [
            b"bad",
            FEEDBACK.pack(b"MSF1", 1, 0, 0, 3, 0, 0, 0, 10),
            FEEDBACK.pack(b"MSF1", 1, 2, 0, 4, 0, 0, 0, 10),
            OSError("closed"),
        ]
        s._feedback_loop()
        self.assertEqual(s.counts["invalid_feedback"], 1)
        self.assertEqual(s.counts["unmatched_feedback"], 1)
        self.assertEqual(s.counts["feedback_rejected"], 1)
        self.assertEqual(s.quality, 70)
        self.assertEqual(s.counts["feedback_socket_failures"], 1)

    def test_cli_validation_and_ack_exit_status(self):
        """@brief The CLI fails without ingress confirmation and rejects invalid limits."""
        for extra in (("--fps", "60"), ("--mbps", "nan"), ("--port", "0"), ("--max-age-ms", "0")):
            with self.subTest(extra=extra), self.assertRaises(SystemExit):
                main(["127.0.0.1", "--desktop", "--log", "unused", *extra])
        with patch("stream_sender.run", return_value={"counts": {}}), patch("builtins.print"):
            self.assertEqual(main(["127.0.0.1", "--desktop", "--log", "unused"]), 2)
        with (
            patch("stream_sender.run", return_value={"counts": {"feedback_accepted": 1}}),
            patch("builtins.print"),
        ):
            self.assertEqual(main(["127.0.0.1", "--desktop", "--log", "unused"]), 0)
        with (
            patch("stream_sender.run", side_effect=OSError("closed")),
            self.assertRaises(SystemExit),
        ):
            main(["127.0.0.1", "--desktop", "--log", "unused"])

    def test_invalid_session_and_empty_clip_and_desktop(self):
        """@brief Reject invalid sessions and close cleanly on EOF or desktop capture."""
        with self.assertRaises(ValueError):
            Session(None, None, 30, 20, 0, 75, 20)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            with tempfile.TemporaryDirectory() as directory:
                args = SimpleNamespace(
                    target="127.0.0.1",
                    port=receiver.getsockname()[1],
                    log=Path(directory) / "empty.jsonl",
                    clip=Path("unused"),
                    fps=30,
                    mbps=20,
                    max_age_ms=200,
                    quality=75,
                    min_quality=20,
                    frames=1,
                )
                with patch("stream_sender.clip_frames", return_value=(x for x in ())):
                    empty = run(args)
                self.assertEqual(empty["pipeline"]["counts"], {})
                args.log, args.clip = Path(directory) / "desktop.jsonl", None
                with patch(
                    "stream_sender.ImageGrab.grab", return_value=Image.new("RGB", (720, 480))
                ):
                    desktop = run(args)
                self.assertEqual(desktop["pipeline"]["counts"]["submitted"], 1)


if __name__ == "__main__":
    unittest.main()
