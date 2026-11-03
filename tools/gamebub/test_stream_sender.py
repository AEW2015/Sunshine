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
from unittest.mock import MagicMock, Mock, patch

import av
from PIL import Image

from controller import ControllerTracker
from host import canvas as reference_canvas
from msv1 import FEEDBACK, VIDEO, Pacer, PartialSendError, encode_receiver_jpeg
from msv1 import send_frame as paced_send_frame
from pipeline import Frame
from quality import QualityController
from stream_sender import (
    FeedbackGate,
    ReceiverCounterTracker,
    Session,
    desktop_duplication_frames,
    main,
    recovering_desktop_frames,
    run,
)


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

    def test_desktop_duplication_opens_and_closes_filter_graph(self):
        """@brief The optional graph yields decoded frames and releases its device on close."""
        capture = MagicMock()
        capture.__enter__ = Mock(return_value=capture)
        capture.__exit__ = Mock(return_value=False)
        capture.decode.return_value = iter(["frame"])
        with patch("stream_sender.av.open", return_value=capture) as open_graph:
            frames = desktop_duplication_frames(30)
            self.assertEqual(next(frames), "frame")
            frames.close()
        open_graph.assert_called_once_with(
            "ddagrab=framerate=30:dup_frames=1:draw_mouse=0,hwdownload,format=bgra",
            format="lavfi",
        )
        capture.decode.assert_called_once_with(video=0)
        capture.__exit__.assert_called_once()

    def test_desktop_duplication_open_error_propagates(self):
        """@brief Initialization errors reach the caller instead of silently changing backends."""
        with (
            patch("stream_sender.av.open", side_effect=OSError("device unavailable")),
            self.assertRaisesRegex(OSError, "device unavailable"),
        ):
            next(desktop_duplication_frames(30))

    def test_desktop_recovery_reopens_and_resets_after_stable_frames(self):
        """@brief Retry budget resets after ten seconds of successful frame delivery."""

        def broken():
            """@brief Simulate a failed graph after it was opened."""
            raise av.FFmpegError(5, "device lost")
            yield  # pragma: no cover

        def then_fail(*values):
            """@brief Yield frames then simulate a subsequent device loss."""
            yield from values
            raise OSError("device lost again")

        events, sleep, elapsed = Mock(), Mock(), [0]
        with patch(
            "stream_sender.desktop_duplication_frames",
            side_effect=[
                broken(),
                broken(),
                then_fail("first", "stable"),
                broken(),
                broken(),
                then_fail("second"),
            ],
        ):
            frames = recovering_desktop_frames(30, events, sleep, lambda: elapsed[0])
            self.assertEqual(next(frames), "first")
            elapsed[0] = 10
            self.assertEqual(next(frames), "stable")
            self.assertEqual(next(frames), "second")
            frames.close()
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.1, 0.2, 0.1, 0.2, 0.4])
        self.assertEqual(events.call_args_list[2].args[0], "capture_restored")
        self.assertEqual(events.call_args_list[-1].args[0], "capture_restored")

    def test_desktop_recovery_limits_repeated_single_frame_flapping(self):
        """@brief An unstable graph cannot evade the retry budget by yielding one frame."""

        def unstable(value):
            """@brief Yield once before a runtime device error."""
            yield value
            raise OSError("flapping")

        sleep, events = Mock(), Mock()
        with patch(
            "stream_sender.desktop_duplication_frames",
            side_effect=[unstable(i) for i in range(4)],
        ):
            frames = recovering_desktop_frames(30, events, sleep, lambda: 0)
            self.assertEqual([next(frames) for _ in range(4)], [0, 1, 2, 3])
            with self.assertRaisesRegex(OSError, "flapping"):
                next(frames)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.1, 0.2, 0.4])
        self.assertFalse(events.call_args.kwargs["retry"])

    def test_desktop_recovery_exhausts_budget_and_closes_graphs(self):
        """@brief Permanent failure closes every graph and reports the final error."""
        graphs = [MagicMock() for _ in range(4)]
        for graph in graphs:
            graph.__next__.side_effect = OSError("unavailable")
        events, sleep = Mock(), Mock()
        with (
            patch("stream_sender.desktop_duplication_frames", side_effect=graphs),
            self.assertRaisesRegex(OSError, "unavailable"),
        ):
            next(recovering_desktop_frames(30, events, sleep))
        for graph in graphs:
            graph.close.assert_called_once()
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.1, 0.2, 0.4])
        self.assertFalse(events.call_args.kwargs["retry"])

    def test_desktop_empty_graph_is_not_silent_eof(self):
        """@brief Unexpected capture EOF is retried and ultimately surfaced."""
        with (
            patch(
                "stream_sender.desktop_duplication_frames", side_effect=lambda _: (x for x in ())
            ),
            self.assertRaisesRegex(OSError, "ended unexpectedly"),
        ):
            next(recovering_desktop_frames(30, Mock(), Mock()))

    def test_desktop_recovery_events_reach_sender_log(self):
        """@brief A reopening capture emits failure and restoration through the session."""
        broken = MagicMock()
        broken.__next__.side_effect = OSError("lost")
        image = Image.new("RGB", (720, 480))
        session = Mock()
        session.lock = threading.Lock()
        session.counts = Counter()
        session.close.return_value = {}
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                target="127.0.0.1",
                port=5533,
                log=Path(directory) / "run.jsonl",
                clip=None,
                desktop_backend="ddagrab",
                fps=10,
                mbps=20,
                max_age_ms=200,
                quality=75,
                min_quality=20,
                frames=1,
            )
            with (
                patch("stream_sender.Session", return_value=session),
                patch(
                    "stream_sender.desktop_duplication_frames",
                    side_effect=[broken, (x for x in [image])],
                ),
            ):
                run(args)
        self.assertEqual(
            [c.args[0] for c in session._event.call_args_list],
            ["capture_config", "capture_error", "capture_restored"],
        )
        broken.close.assert_called_once()
        session.pipeline.submit.assert_called_once()

    def test_desktop_capture_stall_skips_expired_slots(self):
        """@brief Rebase slow startup and skip, rather than submit, expired capture slots."""
        image = Image.new("RGB", (720, 480))
        for stall_ns, expected_ids, skipped in [(250_000_000, [0, 3], 2), (500_000_000, [0], 3)]:
            with self.subTest(stall_ns=stall_ns), tempfile.TemporaryDirectory() as directory:
                clock = [0]

                def acquire(clock=clock, stall_ns=stall_ns):
                    """@brief Model a slow initial open followed by a stalled capture."""
                    clock[0] += 2_000_000_000
                    yield image
                    clock[0] += stall_ns
                    yield image

                def sleep(seconds, clock=clock):
                    """@brief Advance a fake monotonic clock without real waits."""
                    clock[0] += int(seconds * 1_000_000_000)

                session = Mock()
                session.lock = threading.Lock()
                session.counts = Counter()
                session.close.return_value = {}
                args = SimpleNamespace(
                    target="127.0.0.1",
                    port=5533,
                    log=Path(directory) / "run.jsonl",
                    clip=None,
                    desktop_backend="ddagrab",
                    fps=10,
                    mbps=20,
                    max_age_ms=200,
                    quality=75,
                    min_quality=20,
                    frames=4,
                )
                with (
                    patch("stream_sender.Session", return_value=session),
                    patch("stream_sender.desktop_duplication_frames", return_value=acquire()),
                    patch(
                        "stream_sender.time.perf_counter_ns",
                        side_effect=lambda clock=clock: clock[0],
                    ),
                    patch("stream_sender.time.sleep", side_effect=sleep),
                ):
                    run(args)
                ids = [call.args[0].frame_id for call in session.pipeline.submit.call_args_list]
                self.assertEqual(ids, expected_ids)
                self.assertEqual(session.counts["skipped_slots"], skipped)

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

    def test_inflight_extension_is_latched_and_has_absolute_silence_bound(self):
        """@brief Continuing frame sends cannot extend a silent epoch indefinitely."""
        gate = FeedbackGate(0, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        gate.packet_sent((1, 1), 100, 1)
        self.assertFalse(gate.expire(10))
        self.assertFalse(gate.expire(11))
        self.assertEqual(gate.extension_deadline, 40)
        gate.packet_sent((2, 2), 1000, 12)
        self.assertEqual(gate.extension_deadline, 40)
        self.assertFalse(gate.expire(40))
        self.assertTrue(gate.expire(41))
        self.assertTrue(gate.probing)
        self.assertFalse(gate.feedback((1, 1), True, 42))
        self.assertEqual(gate.offer((3, 3), 42), (True, True))
        self.assertTrue(gate.feedback((3, 3), True, 43))
        self.assertFalse(gate.probing)

    def test_inflight_completion_shortens_grace_and_feedback_starts_new_epoch(self):
        """@brief Completion bounds ACK grace and valid feedback resets extension credit."""
        gate = FeedbackGate(0, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        gate.packet_sent((1, 1), 100, 1)
        self.assertFalse(gate.expire(11))
        gate.send_finished((1, 1), 12)
        self.assertEqual(gate.extension_deadline, 22)
        self.assertTrue(gate.feedback((1, 1), True, 13))
        self.assertIsNone(gate.candidate)
        self.assertIsNone(gate.extension_deadline)
        gate.packet_sent((2, 2), 100, 14)
        self.assertFalse(gate.expire(24))
        self.assertEqual(gate.extension_deadline, 53)
        self.assertTrue(gate.expire(54))

    def test_initial_first_packet_arms_bounded_grace_but_no_traffic_does_not(self):
        """@brief Initial silence remains unarmed until actual transmission."""
        gate = FeedbackGate(None, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        self.assertEqual(gate.offer((1, 1), 100), (True, False))
        self.assertFalse(gate.expire(10_000))
        gate.packet_sent((1, 1), 20_000, 10_000)
        self.assertFalse(gate.expire(10_040))
        self.assertTrue(gate.expire(10_041))
        with self.assertRaises(ValueError):
            FeedbackGate(0, timeout_ns=10, max_silence_ns=9)

    def test_recovery_probe_itself_cannot_run_beyond_silence_cap(self):
        """@brief An overlong probe is abandoned and its later ACK cannot restore video."""
        gate = FeedbackGate(0, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        self.assertTrue(gate.expire(11))
        self.assertEqual(gate.offer((1, 1), 11), (True, True))
        self.assertFalse(gate.permit_packet((2, 2), 12))
        self.assertTrue(gate.permit_packet((1, 1), 12))
        gate.packet_sent((1, 1), 1000, 12)
        self.assertTrue(gate.permit_packet((1, 1), 52))
        self.assertFalse(gate.permit_packet((1, 1), 53))
        self.assertFalse(gate.feedback((1, 1), True, 54))
        self.assertEqual(gate.offer((2, 2), 54), (True, True))
        self.assertTrue(gate.feedback((2, 2), True, 55))

    def test_probe_ack_is_bounded_even_without_an_intervening_packet_check(self):
        """@brief An overdue matching ACK cannot revive a still-active long probe."""
        on_time = FeedbackGate(0, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        self.assertTrue(on_time.expire(11))
        self.assertEqual(on_time.offer((1, 1), 11), (True, True))
        on_time.packet_sent((1, 1), 1000, 12)
        self.assertTrue(on_time.feedback((1, 1), True, 52))
        self.assertFalse(on_time.probing)

        late = FeedbackGate(0, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        self.assertTrue(late.expire(11))
        self.assertEqual(late.offer((1, 1), 11), (True, True))
        late.packet_sent((1, 1), 1000, 12)
        self.assertFalse(late.feedback((1, 1), True, 53))
        self.assertTrue(late.probing)
        self.assertIsNone(late.probe_key)
        self.assertEqual(late.offer((2, 2), 54), (True, True))
        self.assertTrue(late.feedback((2, 2), True, 55))

    def test_inflight_frame_stops_after_absolute_silence_limit(self):
        """@brief Continuous datagrams cannot continue after the fixed silence bound."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = (
            QualityController(75, 20),
            1_000_000_000,
            1_000_000_000,
            Pacer(),
        )
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(
            None, timeout_ns=750_000, probe_ns=1_000_000, max_silence_ns=3_000_000
        )
        elapsed = [0]

        def send(packet):
            """@brief Advance time on each successful socket send."""
            elapsed[0] += 1_000_000
            return len(packet)

        def fake_sleep(seconds):
            """@brief Advance fake monotonic time rather than blocking on a frozen clock."""
            elapsed[0] += max(1, int(seconds * 1_000_000_000))

        def paced(*args, **kwargs):
            """@brief Run actual packetization and pacing with deterministic waiting."""
            kwargs["sleeper"] = fake_sleep
            return paced_send_frame(*args, **kwargs)

        s.sock.send.side_effect = send
        jpeg = (Path(__file__).parent / "fixtures/frame-00000000-420-r0.jpg").read_bytes()
        frame = Frame(2, 0, 20, Image.new("RGB", (720, 480)), 0)
        with (
            patch("stream_sender.time.perf_counter_ns", side_effect=lambda: elapsed[0]),
            patch("stream_sender.send_frame", side_effect=paced),
        ):
            self.assertFalse(s._send(frame, jpeg))
        self.assertTrue(s.gate.probing)
        self.assertGreater(s.counts["wire_bytes"], 0)
        self.assertLess(s.counts["wire_bytes"], len(jpeg))
        self.assertEqual(s.counts["feedback_suppressed"], 1)
        events = [json.loads(line) for line in s.log.getvalue().splitlines()]
        self.assertTrue(any(event["event"] == "feedback_timeout" for event in events))
        sent = next(event for event in events if event["event"] == "send")
        self.assertFalse(sent["complete"])
        self.assertEqual(sent["wire_bytes"], s.counts["wire_bytes"])

    def test_silence_between_offer_and_first_datagram_cannot_send_untracked_frame(self):
        """@brief A timeout racing preflight suppresses output before the socket call."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = QualityController(75, 20), 100, 3000, Pacer()
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(0, timeout_ns=10, probe_ns=20, max_silence_ns=40)
        elapsed = [0]

        def racing_send(sock, *args, **kwargs):
            """@brief Advance time to after expiry before attempting the first datagram."""
            elapsed[0] = 11
            return sock.send(b"one packet")

        frame = Frame(2, 0, 20, Image.new("RGB", (720, 480)), 0)
        with (
            patch("stream_sender.time.perf_counter_ns", side_effect=lambda: elapsed[0]),
            patch("stream_sender.send_frame", side_effect=racing_send),
        ):
            self.assertFalse(s._send(frame, b"jpeg"))
        s.sock.send.assert_not_called()
        self.assertEqual(s.counts["wire_bytes"], 0)
        self.assertEqual(len(s.pending), 0)
        self.assertTrue(s.gate.probing)

    def test_long_pacing_wait_is_interrupted_by_feedback_silence(self):
        """@brief Silence stops an in-flight sender without waiting for the next packet due."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = (
            QualityController(75, 20),
            100_000_000_000,
            1000,
            Pacer(),
        )
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(
            None, timeout_ns=10_000_000, probe_ns=20_000_000, max_silence_ns=100_000_000
        )
        s.sock.send.side_effect = lambda packet: len(packet)
        elapsed = [0]

        def sleep(seconds):
            """@brief Advance the monotonic test clock by the requested delay."""
            elapsed[0] += int(seconds * 1_000_000_000)

        jpeg = (Path(__file__).parent / "fixtures/frame-00000000-420-r0.jpg").read_bytes()
        frame = Frame(2, 0, 20, Image.new("RGB", (720, 480)), 0)
        with (
            patch("stream_sender.time.perf_counter_ns", side_effect=lambda: elapsed[0]),
            patch("stream_sender.time.sleep", side_effect=sleep),
        ):
            self.assertFalse(s._send(frame, jpeg))
        self.assertEqual(s.sock.send.call_count, 1)
        self.assertEqual(s.counts["wire_bytes"], VIDEO.size + 1024)
        self.assertGreater(elapsed[0], 100_000_000)
        self.assertLessEqual(elapsed[0], 150_000_000)
        self.assertTrue(s.gate.probing)

    def test_partial_first_datagram_does_not_arm_feedback_grace(self):
        """@brief An invalid short socket send is not recorded as a successful packet."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = (
            QualityController(75, 20),
            1_000_000_000,
            1_000_000_000,
            Pacer(),
        )
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(None)
        s.sock.send.return_value = 0
        jpeg = (Path(__file__).parent / "fixtures/frame-00000000-420-r0.jpg").read_bytes()
        now = time.perf_counter_ns()
        frame = Frame(2, now, 20, Image.new("RGB", (720, 480)), now)
        with self.assertRaisesRegex(OSError, "Partial UDP datagram send"):
            s._send(frame, jpeg)
        self.assertIsNone(s.gate.last_feedback)
        self.assertEqual(s.counts["socket_failures"], 1)
        self.assertEqual(s.counts["wire_bytes"], 0)

    def test_loopback_long_subsequent_frame_receives_ack_before_grace(self):
        """@brief A paced frame longer than 750 ms can complete and receive feedback."""
        stop = threading.Event()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(0.05)

            def peer():
                """@brief Acknowledge a complete, sequential, CRC-checked JPEG."""
                current = bytearray()
                while not stop.is_set():
                    try:
                        packet, address = receiver.recvfrom(2048)
                    except TimeoutError:
                        continue
                    fields = VIDEO.unpack(packet[: VIDEO.size])
                    if fields[8] != len(current):
                        return
                    current.extend(packet[VIDEO.size :])
                    if fields[3] & 2:
                        if zlib.crc32(current) != fields[11]:
                            return
                        receiver.sendto(
                            FEEDBACK.pack(b"MSF1", 1, 0, 0, fields[4], 0, 1, 0, fields[12]),
                            address,
                        )
                        return

            thread = threading.Thread(target=peer)
            thread.start()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect(receiver.getsockname())
                    sock.setblocking(False)
                    session = Session(sock, io.StringIO(), 1, 0.5, 3000, 75, 20)
                    try:
                        with session.lock:
                            session.gate.feedback((1, 1), True, time.perf_counter_ns())
                        jpeg = (
                            Path(__file__).parent / "fixtures/frame-00000000-420-r0.jpg"
                        ).read_bytes()
                        started = time.perf_counter_ns()
                        frame = Frame(2, started, 20, Image.new("RGB", (720, 480)), started)
                        self.assertTrue(session._send(frame, jpeg))
                        self.assertGreater(time.perf_counter_ns() - started, 750_000_000)
                    finally:
                        summary = session.close()
            finally:
                stop.set()
                thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(summary["counts"]["feedback_accepted"], 1)
        self.assertEqual(summary["counts"].get("feedback_suppressed", 0), 0)

    def test_late_matched_ack_does_not_regress_current_heartbeat(self):
        """@brief Older ACKs confirm liveness without displacing the newest heartbeat key."""
        gate = FeedbackGate(0, timeout_ns=10, probe_ns=20)
        self.assertTrue(gate.feedback((0xFFFFFFFF, 100), True, 1))
        self.assertTrue(gate.feedback((0, 90), True, 2))
        self.assertTrue(gate.feedback((0xFFFFFFFF, 100), True, 3))
        self.assertEqual(gate.heartbeat_key, (0, 90))
        self.assertTrue(gate.feedback((0, 91), True, 4))
        self.assertEqual(gate.heartbeat_key, (0, 90))
        self.assertFalse(gate.feedback((0, 91), False, 5))
        self.assertTrue(gate.feedback((0, 90), False, 6))
        self.assertFalse(gate.expire(16))
        self.assertTrue(gate.expire(17))
        self.assertFalse(gate.feedback((0, 90), True, 18))
        self.assertEqual(gate.offer((1, 80), 18), (True, True))
        self.assertTrue(gate.feedback((1, 80), True, 19))
        self.assertEqual(gate.heartbeat_key, (1, 80))

    def test_current_heartbeat_survives_reordered_pending_ack(self):
        """@brief Feedback loop keeps newer heartbeats after a late, still-pending ACK."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(0xFFFFFFFF, 100): None, (0, 90): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        newer = FEEDBACK.pack(b"MSF1", 1, 0, 0, 0, 0, 11, 0, 90)
        older = FEEDBACK.pack(b"MSF1", 1, 0, 0, 0xFFFFFFFF, 0, 10, 0, 100)
        s.sock.recv.side_effect = [newer, older, newer, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", return_value=1):
            s._feedback_loop()
        self.assertEqual(s.counts["feedback_accepted"], 2)
        self.assertEqual(s.counts["feedback_heartbeats"], 1)
        self.assertEqual(s.counts["unmatched_feedback"], 0)
        self.assertEqual(s.gate.heartbeat_key, (0, 90))

    def test_receiver_counter_tracker_handles_wrap_reset_and_reordering(self):
        """@brief Track aggregate counts without assigning them to a frame."""
        tracker = ReceiverCounterTracker()
        self.assertEqual(
            tracker.observe(0xFFFFFFFF, 100, 0xFFFFFFFE, 0xFFFFFFFF),
            {"received_delta": 0, "dropped_delta": 0, "reset": False, "baseline": True},
        )
        wrapped = tracker.observe(0, 200, 0xFFFFFFFF, 0)
        self.assertEqual(
            wrapped,
            {"received_delta": 1, "dropped_delta": 1, "reset": False, "baseline": False},
        )
        self.assertIsNone(tracker.observe(0xFFFFFFFF, 100, 0xFFFFFFFE, 0xFFFFFFFF))
        reset_tracker = ReceiverCounterTracker()
        self.assertEqual(
            reset_tracker.observe(1, 300, 100, 200),
            {"received_delta": 0, "dropped_delta": 0, "reset": False, "baseline": True},
        )
        reset = reset_tracker.observe(2, 400, 0, 0)
        self.assertEqual(
            reset,
            {"received_delta": 0, "dropped_delta": 0, "reset": True, "baseline": True},
        )
        after_reset = reset_tracker.observe(3, 500, 1, 2)
        self.assertEqual(
            after_reset,
            {"received_delta": 1, "dropped_delta": 2, "reset": False, "baseline": False},
        )
        reordered = ReceiverCounterTracker()
        reordered.observe(4, 600, 10, 1)
        self.assertEqual(
            reordered.observe(4, 600, 10, 2),
            {"received_delta": 0, "dropped_delta": 1, "reset": False, "baseline": False},
        )
        self.assertIsNone(reordered.observe(4, 600, 10, 1))
        self.assertEqual(
            reordered.observe(5, 700, 11, 2),
            {"received_delta": 1, "dropped_delta": 0, "reset": False, "baseline": False},
        )

    def test_receiver_counter_frame_order_survives_wall_clock_rollback(self):
        """@brief A late older ACK after clock rollback cannot reset or double count."""
        tracker = ReceiverCounterTracker()
        tracker.observe(0xFFFFFFFE, 110, 10, 0)
        self.assertEqual(tracker.observe(0xFFFFFFFF, 90, 11, 1)["dropped_delta"], 1)
        self.assertIsNone(tracker.observe(0xFFFFFFFE, 110, 10, 0))
        self.assertIsNone(tracker.observe(0xFFFFFFFF, 91, 11, 2))
        self.assertEqual(
            tracker.observe(0, 80, 12, 1),
            {"received_delta": 1, "dropped_delta": 0, "reset": False, "baseline": False},
        )
        self.assertEqual(
            tracker.observe(1, 80, 13, 1),
            {"received_delta": 1, "dropped_delta": 0, "reset": False, "baseline": False},
        )
        self.assertIsNone(tracker.observe(0x80000001, 200, 14, 2))

    def test_late_ack_after_clock_rollback_cannot_double_apply_drop_pressure(self):
        """@brief Real feedback processing ignores stale counters from an older pending ACK."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(0, 110): None, (1, 100): None, (2, 90): None, (3, 80): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        s.sock.recv.side_effect = [
            FEEDBACK.pack(b"MSF1", 1, 0, 0, 0, 0, 10, 0, 110),
            FEEDBACK.pack(b"MSF1", 1, 1, 0, 2, 0, 11, 1, 90),
            FEEDBACK.pack(b"MSF1", 1, 0, 0, 1, 0, 10, 0, 100),
            FEEDBACK.pack(b"MSF1", 1, 0, 0, 3, 0, 12, 1, 80),
            OSError("closed"),
        ]
        with patch("stream_sender.time.perf_counter_ns", return_value=1):
            s._feedback_loop()
        self.assertEqual(s.counts["receiver_counter_resets"], 0)
        self.assertEqual(s.counts["receiver_completed_frames_since_baseline"], 2)
        self.assertEqual(s.counts["receiver_dropped_frames_since_baseline"], 1)
        self.assertEqual(s.quality.value, 70)

    def test_feedback_counter_reset_is_rebaselined_after_gate_accepts(self):
        """@brief Count a receiver reset without treating its lower totals as drops."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(1, 100): None, (2, 200): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        before = FEEDBACK.pack(b"MSF1", 1, 0, 0, 1, 0, 100, 200, 100)
        after = FEEDBACK.pack(b"MSF1", 1, 0, 0, 2, 0, 0, 0, 200)
        s.sock.recv.side_effect = [before, after, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[1, 1, 2, 2, 3]):
            s._feedback_loop()
        self.assertEqual(s.counts["receiver_counter_resets"], 1)
        self.assertEqual(s.counts["receiver_completed_frames_since_baseline"], 0)
        self.assertEqual(s.counts["receiver_dropped_frames_since_baseline"], 0)
        self.assertEqual(s.quality.value, 75)

    def test_accepted_but_stale_counter_snapshot_is_ignored(self):
        """@brief A still-pending old frame may pass liveness but cannot regress counters."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(4, 400): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.receiver_counters = ReceiverCounterTracker()
        s.receiver_counters.observe(5, 500, 10, 10)
        s.sock = Mock()
        delayed = FEEDBACK.pack(b"MSF1", 1, 0, 0, 4, 0, 12, 15, 400)
        s.sock.recv.side_effect = [delayed, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[1, 1, 2]):
            s._feedback_loop()
        self.assertEqual(s.counts["feedback_accepted"], 1)
        self.assertEqual((s.receiver_counters.received, s.receiver_counters.dropped), (10, 10))
        self.assertEqual(s.counts["receiver_completed_frames_since_baseline"], 0)
        self.assertEqual(s.counts["receiver_dropped_frames_since_baseline"], 0)
        self.assertEqual(s.quality.value, 75)

    def test_status_pressure_baseline_deduplication_and_bound(self):
        """@brief Apply status-only pressure conservatively and bound remembered keys."""
        s = Session.__new__(Session)
        s.quality = QualityController(75, 20)
        s.recovery_eligible = True
        first_key = (1, 100)
        s._apply_status_pressure(first_key, 1, {"baseline": True, "dropped_delta": 0})
        self.assertEqual(s.quality.value, 70)
        self.assertFalse(s.recovery_eligible)
        s._apply_status_pressure(first_key, 1, {"baseline": False, "dropped_delta": 0})
        self.assertEqual(s.quality.value, 70)

        no_baseline_key = (2, 200)
        s._apply_status_pressure(no_baseline_key, 1, {"baseline": False, "dropped_delta": 0})
        self.assertEqual(s.quality.value, 70)
        error_key = (3, 300)
        s._apply_status_pressure(error_key, 3, None)
        self.assertEqual(s.quality.value, 65)
        busy_key = (4, 400)
        s._apply_status_pressure(busy_key, 2, {"baseline": False, "dropped_delta": 1})
        self.assertEqual(s.quality.value, 65)

        s.status_pressure_keys = OrderedDict(((i, i), None) for i in range(512))
        new_key = (1000, 1000)
        s._apply_status_pressure(new_key, 2, None)
        self.assertEqual(len(s.status_pressure_keys), 512)
        self.assertNotIn((0, 0), s.status_pressure_keys)
        self.assertIn(new_key, s.status_pressure_keys)

    def test_same_key_heartbeat_then_drop_counter_reduces_quality_once(self):
        """@brief A later counter update on an echoed key signals a drop, not completion."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        key = (7, 700)
        s.pending = OrderedDict({key: None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        early = FEEDBACK.pack(b"MSF1", 1, 0, 0, 7, 0, 0, 0, 700)
        drop_count = FEEDBACK.pack(b"MSF1", 1, 0, 0, 7, 0, 0, 1, 700)
        dropped = FEEDBACK.pack(b"MSF1", 1, 1, 0, 7, 0, 0, 1, 700)
        s.sock.recv.side_effect = [early, drop_count, dropped, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[1, 1, 2, 2, 3, 3, 4]):
            s._feedback_loop()
        self.assertEqual(s.counts["feedback_accepted"], 1)
        self.assertEqual(s.counts["feedback_rejected"], 0)
        self.assertEqual(s.counts["receiver_completed_frames_since_baseline"], 0)
        self.assertEqual(s.counts["receiver_dropped_frames_since_baseline"], 1)
        self.assertEqual(s.quality.value, 70)
        self.assertFalse(s.recovery_eligible)

    def test_unmatched_feedback_cannot_mutate_receiver_counters_or_quality(self):
        """@brief A delayed key rejected by the gate cannot apply its counter snapshot."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(4, 400): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.receiver_counters = ReceiverCounterTracker()
        s.receiver_counters.observe(4, 400, 10, 10)
        s.sock = Mock()
        delayed = FEEDBACK.pack(b"MSF1", 1, 0, 0, 5, 0, 12, 15, 500)
        s.sock.recv.side_effect = [delayed, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[1, 1, 2]):
            s._feedback_loop()
        self.assertEqual((s.receiver_counters.received, s.receiver_counters.dropped), (10, 10))
        self.assertEqual(s.counts["receiver_completed_frames_since_baseline"], 0)
        self.assertEqual(s.counts["receiver_dropped_frames_since_baseline"], 0)
        self.assertEqual(s.quality.value, 75)
        self.assertEqual(s.counts["unmatched_feedback"], 1)

    def test_same_key_completion_counter_counts_aggregate_only(self):
        """@brief A later complete counter increase is not assigned to heartbeat frame ID."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        key = (7, 700)
        s.pending = OrderedDict({key: None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        early = FEEDBACK.pack(b"MSF1", 1, 0, 0, 7, 0, 0, 0, 700)
        complete = FEEDBACK.pack(b"MSF1", 1, 0, 0, 7, 0, 1, 0, 700)
        s.sock.recv.side_effect = [early, complete, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[1, 1, 2, 2, 3]):
            s._feedback_loop()
        self.assertEqual(s.counts["feedback_accepted"], 1)
        self.assertEqual(s.counts["receiver_completed_frames_since_baseline"], 1)
        self.assertEqual(s.counts["feedback_heartbeats"], 1)

    def test_matching_drop_status_and_counter_apply_one_backoff(self):
        """@brief A matched status-1 reply and its counter delta are one congestion event."""
        s = Session.__new__(Session)
        s.lock, s.log, s.stop = threading.Lock(), MemoryEvents(), threading.Event()
        s.pending = OrderedDict({(8, 800): None, (9, 900): None})
        s.counts, s.gate = Counter(), FeedbackGate(0, timeout_ns=1000, probe_ns=100)
        s.controller = ControllerTracker()
        s.quality = QualityController(75, 20)
        s.recovery_eligible = False
        s.sock = Mock()
        baseline = FEEDBACK.pack(b"MSF1", 1, 0, 0, 8, 0, 0, 0, 800)
        dropped = FEEDBACK.pack(b"MSF1", 1, 1, 0, 9, 0, 0, 1, 900)
        s.sock.recv.side_effect = [baseline, dropped, OSError("closed")]
        with patch("stream_sender.time.perf_counter_ns", side_effect=[1, 1, 2, 2, 3]):
            s._feedback_loop()
        self.assertEqual(s.quality.value, 70)
        self.assertEqual(s.counts["receiver_dropped_frames_since_baseline"], 1)
        self.assertEqual(s.counts["feedback_rejected"], 1)

    def test_partial_send_error_accounts_wire_bytes_and_arms_grace(self):
        """@brief A second-datagram failure records first-datagram bytes and grace."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality = QualityController(75, 20)
        s.age_ns, s.rate, s.pacer = 1_000_000_000, 100_000_000, Pacer()
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(None)
        image = Image.effect_noise((720, 480), 100).convert("RGB")
        jpeg = encode_receiver_jpeg(image, 75)
        captured_ns = time.perf_counter_ns()
        frame = Frame(2, captured_ns, 20, image, captured_ns)
        calls = 0

        def fail_on_second_datagram(packet):
            """@brief Accept one full UDP datagram, then fail the next send."""
            nonlocal calls
            calls += 1
            if calls == 1:
                return len(packet)
            raise OSError("socket closed")

        s.sock.send.side_effect = fail_on_second_datagram
        with self.assertRaises(PartialSendError):
            s._send(frame, jpeg)
        self.assertEqual(calls, 2)
        self.assertEqual(s.counts["wire_bytes"], VIDEO.size + 1024)
        self.assertEqual(s.counts["socket_failures"], 1)
        self.assertIsNotNone(s.gate.last_feedback)
        self.assertEqual(len(s.pending), 0)
        event = next(json.loads(line) for line in s.log.getvalue().splitlines())
        self.assertEqual(event["wire_bytes"], VIDEO.size + 1024)

        zero = Session.__new__(Session)
        zero.lock, zero.log, zero.sock = threading.Lock(), MemoryEvents(), Mock()
        zero.quality, zero.age_ns, zero.rate, zero.pacer = (
            QualityController(75, 20),
            100,
            3000,
            Pacer(),
        )
        zero.recovery_eligible = False
        zero.pending, zero.counts = OrderedDict(), Counter()
        zero.gate = FeedbackGate(None)
        zero_frame = Frame(3, 10, 30, Image.new("RGB", (720, 480)))
        with (
            patch(
                "stream_sender.send_frame",
                side_effect=PartialSendError(OSError("closed before packet"), 0),
            ),
            self.assertRaises(PartialSendError),
        ):
            zero._send(zero_frame, b"jpeg")
        self.assertEqual(zero.counts["wire_bytes"], 0)
        self.assertIsNone(zero.gate.last_feedback)

    def test_feedback_grace_starts_after_initial_traffic(self):
        """@brief Capture startup, preflight, and initial frame sending do not consume grace."""
        gate = FeedbackGate(None, timeout_ns=10, probe_ns=20)
        self.assertFalse(gate.expire(100))
        self.assertFalse(gate.feedback((1, 1), False, 100))
        self.assertEqual(gate.offer((1, 1), 100), (True, False))
        self.assertFalse(gate.expire(1_000))
        gate.sent(1_000)
        self.assertFalse(gate.expire(1_010))
        self.assertTrue(gate.expire(1_011))
        self.assertTrue(gate.probing)
        self.assertEqual(gate.offer((2, 2), 1_011), (True, True))
        self.assertFalse(gate.feedback((1, 1), True, 1_012))
        self.assertTrue(gate.feedback((2, 2), True, 1_012))

    def test_initial_feedback_during_send_is_not_overwritten(self):
        """@brief Matching feedback received before send returns retains its timestamp."""
        gate = FeedbackGate(None, timeout_ns=10, probe_ns=20)
        gate.offer((1, 1), 100)
        self.assertTrue(gate.feedback((1, 1), True, 105))
        gate.sent(108)
        self.assertEqual(gate.last_feedback, 105)

    def test_no_traffic_does_not_arm_initial_feedback_timeout(self):
        """@brief A preflight refusal cannot start silence detection without datagrams."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = QualityController(75, 20), 100, 3000, Pacer()
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(None, timeout_ns=10, probe_ns=20)
        frame = Frame(2, 1, 2, Image.new("RGB", (720, 480)))
        with patch("stream_sender.send_frame", return_value=(False, 0)):
            self.assertFalse(s._send(frame, b"x"))
        self.assertIsNone(s.gate.last_feedback)
        self.assertEqual(len(s.pending), 0)
        self.assertFalse(s.gate.expire(100_000))

    def test_initial_send_longer_than_timeout_arms_after_it_finishes(self):
        """@brief A paced first frame receives its full feedback grace after transmission."""
        s = Session.__new__(Session)
        s.lock, s.log, s.sock = threading.Lock(), MemoryEvents(), Mock()
        s.quality, s.age_ns, s.rate, s.pacer = QualityController(75, 20), 100, 3000, Pacer()
        s.recovery_eligible = False
        s.pending, s.counts = OrderedDict(), Counter()
        s.gate = FeedbackGate(None, timeout_ns=10, probe_ns=20)
        frame = Frame(2, 1, 2, Image.new("RGB", (720, 480)))

        def long_send(*args, **kwargs):
            """@brief Simulate sending for much longer than the silence deadline."""
            self.assertFalse(s.gate.expire(1_000))
            return True, 40

        with (
            patch("stream_sender.time.perf_counter_ns", return_value=1_001),
            patch("stream_sender.send_frame", side_effect=long_send),
        ):
            self.assertTrue(s._send(frame, b"x"))
        self.assertEqual(s.gate.last_feedback, 1_001)
        self.assertIn((2, 2), s.pending)
        self.assertFalse(s.gate.expire(1_011))
        self.assertTrue(s.gate.expire(1_012))

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

    def test_slow_capture_start_gets_full_feedback_grace(self):
        """@brief Slow initialization does not falsely put a responsive peer into probing."""
        stop = threading.Event()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(0.05)

            def peer():
                """@brief Acknowledge the first complete frame."""
                while not stop.is_set():
                    try:
                        packet, address = receiver.recvfrom(2048)
                    except TimeoutError:
                        continue
                    fields = VIDEO.unpack(packet[: VIDEO.size])
                    if fields[3] & 2:
                        receiver.sendto(
                            FEEDBACK.pack(b"MSF1", 1, 0, 0, fields[4], 0, 1, 0, fields[12]),
                            address,
                        )
                        return

            def slow_capture():
                """@brief Delay capture longer than the 750 ms liveness timeout."""
                time.sleep(0.85)
                yield Image.new("RGB", (720, 480), "red")

            thread = threading.Thread(target=peer)
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as directory:
                    args = SimpleNamespace(
                        target="127.0.0.1",
                        port=receiver.getsockname()[1],
                        log=Path(directory) / "slow-start.jsonl",
                        clip=None,
                        fps=5,
                        mbps=100,
                        max_age_ms=500,
                        quality=75,
                        min_quality=20,
                        frames=1,
                    )
                    result = run(args, slow_capture())
                    events = [
                        json.loads(line)["event"] for line in args.log.read_text().splitlines()
                    ]
            finally:
                stop.set()
                thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["counts"]["feedback_accepted"], 1)
        self.assertNotIn("feedback_timeout", events)

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
                    if fields[3] & 2 and time.monotonic() - started > 2.2:
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
                        frames=70,
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
                        packet_timing=True,
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
        feedback = [event for event in events if event["event"] == "feedback"]
        self.assertEqual(feedback[-1]["received_frames"], 4)
        self.assertEqual(feedback[-1]["dropped_frames"], 0)
        self.assertEqual(result["logging"]["dropped"], 0)
        self.assertIsNone(result["logging"]["error"])
        self.assertEqual(sum(event["event"] == "send" for event in events), 4)
        timing = [event for event in events if event["event"] == "packet_timing"]
        self.assertEqual([event["frame_id"] for event in timing], completed)
        for event in timing:
            self.assertGreater(event["capture_us"], 0)
            self.assertEqual(event["packets"][0][0], 0)
            self.assertTrue(all(len(packet) == 3 and packet[1] > 0 for packet in event["packets"]))
            self.assertEqual(
                [packet[0] for packet in event["packets"]],
                sorted(packet[0] for packet in event["packets"]),
            )
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

    def test_packet_timing_is_opt_in_and_retains_partial_send(self):
        """@brief Packet events include only callbacks for successfully sent datagrams."""
        for enabled, result, enqueue in [
            (False, "complete", True),
            (True, "complete", True),
            (True, "partial", True),
            (True, "error", True),
            (True, "partial", False),
        ]:
            with self.subTest(enabled=enabled, result=result, enqueue=enqueue):
                s = Session.__new__(Session)
                s.lock, s.log, s.sock = threading.Lock(), Mock(), Mock()
                s.log.submit.side_effect = lambda event, enqueue=enqueue: (
                    enqueue if event["event"] == "packet_timing" else True
                )
                s.packet_timing = enabled
                s.quality, s.age_ns, s.rate, s.pacer = QualityController(75, 20), 100, 3000, Pacer()
                s.recovery_eligible = True
                s.pending, s.counts = OrderedDict(), Counter()
                s.gate = FeedbackGate(None)
                frame = Frame(2, 10, 20, Image.new("RGB", (720, 480)))

                def send(*args, result=result, **kwargs):
                    """@brief Report actual sends, then simulate completion or an error."""
                    callback = kwargs["on_packet"]
                    if callback:
                        packet = VIDEO.pack(b"MSV1", 1, 1, 1, 2, 720, 480, 2048, 0, 1024, 0, 0, 20)
                        callback(packet, 1.25)
                    if result == "error":
                        raise OSError("socket failed after one packet")
                    return result == "complete", 1064

                with patch("stream_sender.send_frame", side_effect=send):
                    if result == "error":
                        with self.assertRaises(OSError):
                            s._send(frame, b"jpeg")
                    else:
                        self.assertEqual(s._send(frame, b"jpeg"), result == "complete")
                events = [c.args[0] for c in s.log.submit.call_args_list]
                timing = [e for e in events if e["event"] == "packet_timing"]
                if enabled:
                    self.assertEqual(timing[0]["packets"], [[0, 1024, 1.25]])
                    self.assertEqual((timing[0]["frame_id"], timing[0]["capture_us"]), (2, 20))
                    self.assertEqual(s.counts["packet_timing_enqueue_dropped"], int(not enqueue))
                else:
                    self.assertEqual(timing, [])

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

    def test_quality_does_not_recover_before_first_send(self):
        """@brief An unstarted feedback gate cannot establish congestion recovery."""
        s = Session.__new__(Session)
        s.lock, s.log = threading.Lock(), MemoryEvents()
        s.quality, s.gate = QualityController(75, 20, recovery_frames=1), FeedbackGate(None)
        s.quality.congested()
        s.recovery_eligible, s.rate, s.fps, s.counts = True, 3000, 30, Counter()
        with patch("stream_sender.encode_receiver_jpeg", return_value=b"x"):
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
        events = [json.loads(line) for line in s.log.getvalue().splitlines()]
        heartbeat = next(event for event in events if event["event"] == "heartbeat")
        self.assertEqual((heartbeat["received_frames"], heartbeat["dropped_frames"]), (0, 0))
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
        with self.assertRaises(SystemExit):
            main(
                [
                    "127.0.0.1",
                    "--clip",
                    "clip.mp4",
                    "--desktop-backend",
                    "ddagrab",
                    "--log",
                    "unused",
                ]
            )
        with patch("stream_sender.run", return_value={"counts": {}}), patch("builtins.print"):
            self.assertEqual(main(["127.0.0.1", "--desktop", "--log", "unused"]), 2)
        with (
            patch("stream_sender.run", return_value={"counts": {"feedback_accepted": 1}}) as sender,
            patch("builtins.print"),
        ):
            self.assertEqual(
                main(["127.0.0.1", "--desktop", "--log", "unused", "--packet-timing"]), 0
            )
            self.assertTrue(sender.call_args.args[0].packet_timing)
        with (
            patch("stream_sender.run", side_effect=OSError("closed")),
            self.assertRaises(SystemExit),
        ):
            main(["127.0.0.1", "--desktop", "--log", "unused"])
        with (
            patch("stream_sender.run", side_effect=av.FFmpegError(5, "capture failed")),
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
                args.desktop_filter = "box"
                with (
                    patch(
                        "stream_sender.ImageGrab.grab", return_value=Image.new("RGB", (720, 480))
                    ),
                    patch("stream_sender.canvas", wraps=reference_canvas) as resize,
                ):
                    desktop = run(args)
                self.assertEqual(desktop["pipeline"]["counts"]["submitted"], 1)
                self.assertEqual(desktop["pipeline"]["counts"]["encoded"], 1)
                self.assertEqual(resize.call_args.args[1], Image.Resampling.BOX)
                config = json.loads(args.log.read_text().splitlines()[0])
                self.assertEqual((config["source"], config["desktop_filter"]), ("desktop", "box"))
                args.log = Path(directory) / "ddagrab.jsonl"
                args.desktop_backend = "ddagrab"
                source = MagicMock()
                source.__next__ = Mock(return_value=Image.new("RGB", (720, 480)))
                source.close = Mock()
                with patch(
                    "stream_sender.desktop_duplication_frames", return_value=source
                ) as capture:
                    result = run(args)
                self.assertEqual(result["pipeline"]["counts"]["submitted"], 1)
                capture.assert_called_once_with(30)
                source.close.assert_called_once()
                config = json.loads(args.log.read_text().splitlines()[0])
                self.assertEqual(
                    (config["source"], config["desktop_filter"]), ("desktop_ddagrab", None)
                )
                args.log = Path(directory) / "failed-capture.jsonl"
                source = MagicMock()
                source.__next__.side_effect = av.FFmpegError(5, "capture failed")
                with (
                    patch("stream_sender.recovering_desktop_frames", return_value=source),
                    self.assertRaises(av.FFmpegError),
                ):
                    run(args)
                source.close.assert_called_once()
                events = [json.loads(line)["event"] for line in args.log.read_text().splitlines()]
                self.assertIn("summary", events)


if __name__ == "__main__":
    unittest.main()
