"""@brief Localhost tests for continuous receiver-compatible video transmission."""

import io
import json
import socket
import tempfile
import threading
import time
import unittest
import zlib
from collections import Counter, OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from controller import ControllerTracker
from msv1 import FEEDBACK, VIDEO, Pacer
from pipeline import Frame
from quality import QualityController
from stream_sender import FeedbackGate, Session, main, run


class MemoryEvents:
    """@brief Synchronous event collector for isolated Session method tests."""

    def __init__(self):
        """@brief Start an in-memory JSONL stream."""
        self.output = io.StringIO()

    def submit(self, event):
        """@brief Record one structured event without starting a writer thread."""
        self.output.write(json.dumps(event) + "\n")

    def getvalue(self):
        """@brief Return the recorded JSONL events."""
        return self.output.getvalue()


class StreamSenderTests(unittest.TestCase):
    """@brief Exercise capture, JPEG, packetization and ingress feedback on loopback."""

    def test_feedback_gate_timeout_heartbeat_and_probe_recovery(self):
        """@brief Silence limits traffic; only a fresh probe can restore regular sending."""
        with self.assertRaises(ValueError):
            FeedbackGate(0, timeout_ns=0)
        gate = FeedbackGate(0, timeout_ns=10, probe_ns=20)
        self.assertEqual(gate.offer((1, 1), 0), (True, False))
        self.assertTrue(gate.feedback((1, 1), True, 1))
        self.assertTrue(gate.feedback((1, 1), False, 10))
        self.assertFalse(gate.feedback((9, 9), False, 10))
        self.assertEqual(gate.offer((2, 2), 20), (True, False))
        self.assertEqual(gate.offer((3, 3), 21), (True, True))
        self.assertTrue(gate.probing)
        self.assertEqual(gate.offer((4, 4), 22), (False, False))
        self.assertFalse(gate.feedback((1, 1), False, 22))
        self.assertFalse(gate.feedback((2, 2), True, 22))
        self.assertEqual(gate.offer((5, 5), 41), (True, True))
        self.assertFalse(gate.feedback((3, 3), True, 42))
        self.assertTrue(gate.feedback((5, 5), True, 42))
        self.assertFalse(gate.probing)
        self.assertEqual(gate.offer((6, 6), 43), (True, False))

    def test_silent_peer_suppresses_frames_and_clears_stale_pending(self):
        """@brief Timeout limits datagrams to probes and rejects delayed old feedback."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = QualityController(75, 20), 100, 3000, Pacer()
        s.recovery_eligible = True
        s.pending, s.counts = OrderedDict({(0, 0): None}), Counter()
        s.gate = FeedbackGate(0, timeout_ns=10, probe_ns=20)
        frame = Frame(2, 1, 2, Image.new("RGB", (720, 480)))
        with (
            patch("stream_sender.time.perf_counter_ns", return_value=11),
            patch("stream_sender.send_frame", return_value=(True, 40)) as send,
        ):
            self.assertTrue(s._send(frame, b"x"))
            self.assertEqual(list(s.pending), [(2, 2)])
            self.assertFalse(s._send(Frame(3, 1, 3, frame.image), b"x"))
            self.assertEqual(send.call_count, 1)
        self.assertEqual(s.counts["feedback_suppressed"], 1)
        self.assertEqual(s.counts["feedback_abandoned"], 1)

    def test_loopback_silence_then_fresh_probe_restores_video(self):
        """@brief A silent localhost peer causes suppression and later probe recovery."""
        stop = threading.Event()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(0.05)
            starts = []
            started = time.monotonic()

            def peer():
                """@brief Delay feedback, then acknowledge each complete test frame."""
                while not stop.is_set():
                    try:
                        packet, address = receiver.recvfrom(2048)
                    except TimeoutError:
                        continue
                    fields = VIDEO.unpack(packet[: VIDEO.size])
                    if fields[3] & 1:
                        starts.append(fields[4])
                    if fields[3] & 2 and time.monotonic() - started > 1.2:
                        receiver.sendto(
                            FEEDBACK.pack(b"MSF1", 1, 0, 0, fields[4], 0, 0, 0, fields[12]),
                            address,
                        )

            thread = threading.Thread(target=peer)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as directory:
                    args = SimpleNamespace(
                        target="127.0.0.1",
                        port=receiver.getsockname()[1],
                        log=Path(directory) / "recovery.jsonl",
                        fps=20,
                        mbps=100,
                        max_age_ms=500,
                        quality=75,
                        min_quality=20,
                        frames=50,
                    )
                    image = Image.new("RGB", (720, 480), "red")
                    result = run(args, iter([image] * args.frames))
                    events = [
                        json.loads(line)["event"] for line in args.log.read_text().splitlines()
                    ]
            finally:
                stop.set()
                thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertGreater(result["counts"]["feedback_suppressed"], 0)
        self.assertGreater(result["counts"].get("feedback_accepted", 0), 1)
        self.assertFalse(result["feedback_probing"])
        self.assertLess(len(starts), args.frames)
        self.assertIn("feedback_timeout", events)
        self.assertIn("feedback_restored", events)

    def test_loopback_frames_and_feedback(self):
        """@brief A receiver reassembles complete CRC-checked JPEGs and acknowledges ingress."""
        completed, errors, source_ports = [], [], set()
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
                    source_ports.add(address[1])
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
                                FEEDBACK.pack(
                                    b"MSF1", 1, 0, 1 << 11, frame, 0, len(completed), 0, stamp
                                ),
                                address,
                            )

            thread = threading.Thread(target=peer)
            thread.start()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reserve:
                    reserve.bind(("127.0.0.1", 0))
                    source_port = reserve.getsockname()[1]
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
                        source_port=source_port,
                        start_frame_id=0xFFFFFFFE,
                    )
                    source = iter([Image.new("RGB", (720, 480), (i * 40, 0, 0)) for i in range(4)])
                    result = run(args, source)
                    events = [json.loads(line) for line in args.log.read_text().splitlines()]
            finally:
                stop.set()
                thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(completed, [0xFFFFFFFE, 0xFFFFFFFF, 0, 1])
        self.assertEqual(source_ports, {source_port})
        self.assertEqual(result["counts"]["feedback_accepted"], 4)
        self.assertEqual(result["pipeline"]["counts"]["sent"], 4)
        self.assertFalse(result["end_to_end_verified"])
        self.assertEqual(result["logging"]["dropped"], 0)
        self.assertIsNone(result["logging"]["error"])
        self.assertEqual(sum(event["event"] == "send" for event in events), 4)
        self.assertEqual(
            [
                (event["gamepad_flags"], event["reason"])
                for event in events
                if event["event"] == "controller"
            ],
            [(0x1000, "feedback"), (0, "shutdown")],
        )
        self.assertEqual(events[-1]["event"], "summary")

    def test_restart_keeps_source_port_and_advances_frame_id(self):
        """@brief Two sender runs can match a peer pinned to the first source port."""
        stopped, complete, peers = threading.Event(), [], []
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(0.05)

            def peer():
                """@brief Enforce the peer port and monotonically newer completed IDs."""
                while not stopped.is_set():
                    try:
                        packet, address = receiver.recvfrom(2048)
                    except TimeoutError:
                        continue
                    if peers and address != peers[0]:
                        continue
                    if not peers:
                        peers.append(address)
                    header = VIDEO.unpack(packet[: VIDEO.size])
                    if header[3] & 2 and (not complete or header[4] > complete[-1]):
                        complete.append(header[4])
                        receiver.sendto(
                            FEEDBACK.pack(b"MSF1", 1, 0, 0, header[4], 0, 0, 0, header[12]),
                            address,
                        )

            thread = threading.Thread(target=peer)
            thread.start()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reserve:
                    reserve.bind(("127.0.0.1", 0))
                    source_port = reserve.getsockname()[1]
                with tempfile.TemporaryDirectory() as directory:
                    args = SimpleNamespace(
                        target="127.0.0.1",
                        port=receiver.getsockname()[1],
                        source_port=source_port,
                        log=Path(directory) / "first.jsonl",
                        fps=30,
                        mbps=100,
                        max_age_ms=500,
                        quality=75,
                        min_quality=20,
                        frames=1,
                        start_frame_id=100,
                    )
                    image = Image.new("RGB", (720, 480))
                    first = run(args, iter([image]))
                    args.start_frame_id, args.log = 101, Path(directory) / "second.jsonl"
                    second = run(args, iter([image]))
            finally:
                stopped.set()
                thread.join(2)
        self.assertEqual(complete, [100, 101])
        self.assertEqual(peers[0][1], source_port)
        self.assertEqual(first["counts"]["feedback_accepted"], 1)
        self.assertEqual(second["counts"]["feedback_accepted"], 1)

    def test_log_io_failure_is_reported_at_close(self):
        """@brief Log storage failure does not crash the sender and is visible in its summary."""

        class BrokenFile(io.StringIO):
            """@brief Deterministically fail all logging writes."""

            def write(self, value):
                """@brief Simulate a full disk."""
                raise OSError("disk full")

        sock = Mock()
        sock.recv.side_effect = BlockingIOError()
        session = Session(sock, BrokenFile(), 30, 20, 200, 75, 20)
        session._event("test")
        result = session.close()
        self.assertIn("disk full", result["logging"]["error"])
        self.assertGreaterEqual(result["logging"]["dropped"], 1)

    def test_adaptation_and_network_errors(self):
        """@brief Congestion and encoder/socket failures lower quality within bounds."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality = QualityController(75, 20, recovery_frames=1)
        s.recovery_eligible = True
        s.rate, s.fps, s.age_ns, s.pacer = 3000, 30, 100, Pacer()
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(time.perf_counter_ns())
        with patch("stream_sender.encode_receiver_jpeg", return_value=b"x" * 100):
            s._encode(None)
        self.assertEqual(s.quality.value, 70)
        with patch("stream_sender.encode_receiver_jpeg", return_value=b"x"):
            s._encode(None)
        self.assertEqual(s.quality.value, 71)
        with patch("stream_sender.encode_receiver_jpeg", return_value=b"x" * 40):
            s._encode(None)
        self.assertEqual(s.quality.value, 71)
        with (
            patch("stream_sender.encode_receiver_jpeg", side_effect=OverflowError("too big")),
            self.assertRaises(OverflowError),
        ):
            s._encode(None)
        self.assertEqual(s.quality.value, 66)
        frame = Frame(2, 10, 20, Image.new("RGB", (720, 480)))
        with patch("stream_sender.send_frame", return_value=(False, 40)):
            self.assertFalse(s._send(frame, b"x"))
        self.assertEqual(s.quality.value, 61)
        with (
            patch("stream_sender.send_frame", side_effect=OSError("closed")),
            self.assertRaises(OSError),
        ):
            s._send(frame, b"x")
        self.assertEqual(s.counts["socket_failures"], 1)
        self.assertEqual(len(s.pending), 0)
        with (
            patch("stream_sender.send_frame", side_effect=ValueError("invalid jpeg")),
            self.assertRaises(ValueError),
        ):
            s._send(frame, b"x")
        self.assertEqual(s.counts["packet_failures"], 1)
        self.assertEqual(len(s.pending), 0)
        s.pending.update(((i, i), None) for i in range(512))
        with patch("stream_sender.send_frame", return_value=(True, 40)):
            self.assertTrue(s._send(frame, b"x"))
        self.assertEqual(len(s.pending), 512)
        self.assertEqual(s.counts["feedback_evicted"], 1)

    def test_quality_does_not_recover_on_old_feedback(self):
        """@brief Old ACKs do not permit quality recovery while the send worker is blocked."""
        s = Session.__new__(Session)
        s.lock, s.log = threading.Lock(), MemoryEvents()
        s.quality, s.gate = QualityController(75, 20, recovery_frames=1), FeedbackGate(0, 10, 20)
        s.quality.congested()
        s.recovery_eligible, s.rate, s.fps, s.counts = True, 3000, 30, Counter()
        with (
            patch("stream_sender.time.perf_counter_ns", return_value=11),
            patch("stream_sender.encode_receiver_jpeg", return_value=b"x"),
        ):
            s._encode(None)
        self.assertEqual(s.quality.value, 70)

    def test_feedback_filters_unmatched_and_reacts_to_busy(self):
        """@brief Bad or old feedback cannot acknowledge a frame; busy lowers quality."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending, s.counts = OrderedDict({(4, 10): None}), Counter()
        s.gate = FeedbackGate(time.perf_counter_ns())
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
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
        self.assertEqual(s.quality.value, 70)
        self.assertEqual(s.counts["feedback_socket_failures"], 1)

    def test_feedback_heartbeat_and_ack_after_timeout(self):
        """@brief Repeated current heartbeats count, but delayed ACKs do not revive silence."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(4, 10): None, (5, 11): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=10, probe_ns=20)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        ack = FEEDBACK.pack(b"MSF1", 1, 0, 0, 4, 0, 0, 0, 10)
        late = FEEDBACK.pack(b"MSF1", 1, 0, 0, 5, 0, 0, 0, 11)
        s.sock.recv.side_effect = [ack, ack, late, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[0, 1, 1, 2, 2, 20, 20]):
            s._feedback_loop()
        self.assertEqual(s.counts["feedback_accepted"], 1)
        self.assertEqual(s.counts["feedback_heartbeats"], 1)
        self.assertEqual(s.counts["feedback_abandoned"], 1)
        self.assertEqual(s.counts["unmatched_feedback"], 1)
        self.assertTrue(s.gate.probing)

    def test_button_logging_timeout_and_late_heartbeat(self):
        """@brief Accepted snapshots are logged; silence emits a neutral state."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending, s.counts = OrderedDict({(4, 10): None}), Counter()
        s.gate, s.controller = FeedbackGate(0, 1000, 100), ControllerTracker(10)
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        pressed = FEEDBACK.pack(b"MSF1", 1, 0, 1 << 11, 4, 0, 0, 0, 10)
        s.sock.recv.side_effect = [pressed, BlockingIOError(), pressed, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[0, 1, 12, 13, 14, 15]):
            s._feedback_loop()
        events = [json.loads(line) for line in s.log.getvalue().splitlines()]
        controller_events = [event for event in events if event["event"] == "controller"]
        self.assertEqual([event["gamepad_flags"] for event in controller_events], [0x1000, 0])
        self.assertEqual(controller_events[-1]["reason"], "timeout")

    def test_bad_button_mask_and_socket_error_release(self):
        """@brief Reject reserved button bits and neutralize held state on socket error."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending, s.counts = OrderedDict({(4, 10): None, (5, 11): None}), Counter()
        s.gate, s.controller = FeedbackGate(0, 1000, 100), ControllerTracker(1000)
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        s.sock.recv.side_effect = [
            FEEDBACK.pack(b"MSF1", 1, 0, 1 << 11, 4, 0, 0, 0, 10),
            FEEDBACK.pack(b"MSF1", 1, 0, 1 << 12, 5, 0, 0, 0, 11),
            OSError("closed"),
        ]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[0, 1, 2, 3, 4]):
            s._feedback_loop()
        events = [json.loads(line) for line in s.log.getvalue().splitlines()]
        self.assertEqual(s.counts["invalid_buttons"], 1)
        self.assertEqual(events[-1]["reason"], "socket_error")
        self.assertEqual(events[-1]["gamepad_flags"], 0)

    def test_cli_validation_and_ack_exit_status(self):
        """@brief The CLI fails without ingress confirmation and rejects invalid limits."""
        for extra in (
            ("--fps", "60"),
            ("--mbps", "nan"),
            ("--port", "0"),
            ("--max-age-ms", "0"),
            ("--source-port", "-1"),
            ("--start-frame-id", "4294967296"),
        ):
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
