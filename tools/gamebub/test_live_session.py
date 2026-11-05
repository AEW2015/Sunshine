"""@brief Local AV runner tests use fake clocks/sockets and no physical injection."""

import queue
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import live_session
from av_protocol import INPUT, NONCE, Packet, decode
from gamepad_backend import GamepadDispatcher
from msv1 import gamebub_buttons
from realtime import gamepad_buttons
from windows_gamepad import OrderedInput


class Clock:
    """@brief Deterministically advance QPC-compatible nanoseconds on every call."""

    def __init__(self):
        """@brief Start before any lease or capture timestamp."""
        self.now = 0

    def __call__(self):
        """@brief Advance five milliseconds without wall-clock waits."""
        self.now += 5_000_000
        return self.now


class PeerSocket:
    """@brief Answer only HELLO/START/keepalive using real validated wire packets."""

    def __init__(self, audio=False, keep=True):
        """@brief Set peer mode and independently sequenced input responses."""
        self.audio, self.keep = audio, keep
        self.pending = []
        self.sent = []
        self.sequence = 0
        self.peer = ("127.0.0.1", 5534)

    def send(self, raw):
        """@brief Model the receiver with the exact local AV serializer/parser."""
        packet = decode(raw)
        self.sent.append(packet)
        if packet.magic == b"MSC1" and packet.kind == 1:
            self.pending.append(
                Packet(
                    b"MSR1", 1, 42, flags=int(self.audio), payload=NONCE.pack(packet.session)
                ).encode()
            )
        if packet.magic == b"MSC1" and (packet.kind == 2 or packet.kind == 3 and self.keep):
            self.pending.append(
                Packet(
                    b"MSI1",
                    1,
                    42,
                    sequence=self.sequence,
                    payload=INPUT.pack(0, 2, 0, 0, 3, 0, 5 | int(self.audio) * 2, 8),
                ).encode()
            )
            self.sequence += 1
        return len(raw)

    def recvfrom(self, count):
        """@brief Return pending replies or a nonblocking timeout."""
        if self.pending:
            return self.pending.pop(0), self.peer
        raise TimeoutError()

    def bind(self, endpoint):
        """@brief Retain the exact source endpoint for assertions."""
        self.local = endpoint

    def connect(self, peer):
        """@brief Pin one peer endpoint."""
        self.peer = peer

    def getsockname(self):
        """@brief Return this fake source endpoint."""
        return self.local

    def settimeout(self, value):
        """@brief Socket waits are represented by deterministic clock advances."""

    def close(self):
        """@brief Mark resource cleanup."""
        self.closed = True


class SessionTests(unittest.TestCase):
    """@brief Preserve cookie handshake, independent ordering, profiles and STOP."""

    def test_wow_repeated_valid_holds_accelerate_through_profile_sink(self):
        """@brief The combined-session adapter refreshes a held camera and releases on silence."""
        backend = MagicMock()
        backend.close.return_value = ()
        now = [0]
        dispatcher = GamepadDispatcher(backend, profile="wow", clock=lambda: now[0])
        sink = live_session.ProfileSink(dispatcher)
        self.assertTrue(sink.repeat_buttons)
        token = bytes(range(16))
        ordered = OrderedInput(token, sink, 500_000_000)
        speeds = []
        for tick in range(21):
            now[0] = tick * 100_000_000
            self.assertTrue(ordered.accept(token, tick, 0x800, now[0]))
            speeds.append(backend.set_state.call_args.args[4])
        self.assertEqual(speeds[0], 10000)
        self.assertEqual(speeds[-1], 32767)
        self.assertEqual(speeds, sorted(speeds))
        calls = backend.set_state.call_count
        self.assertFalse(ordered.accept(token, 20, 0x800, now[0] + 1))
        self.assertEqual(backend.set_state.call_count, calls)
        now[0] += 500_000_000
        self.assertTrue(ordered.expire(now[0]))
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0, 0, 0, 0))
        self.assertIsNone(dispatcher.camera.started_ns)
        dispatcher.close()

    def args(self, **changes):
        """@brief Return a short localhost-only session configuration."""
        return SimpleNamespace(
            **(
                {
                    "receiver": "127.0.0.1",
                    "bind": "127.0.0.1",
                    "av_port": 5534,
                    "av_source_port": 0,
                    "gamepad": False,
                    "profile": "wow",
                    "audio": False,
                    "gain": 0.75,
                    "seconds": 0.2,
                    "source_timeout": 0.01,
                }
                | changes
            )
        )

    def test_all_masks_roundtrip_through_profile_sink(self):
        """@brief Reverse standard flags exactly before applying a selected profile."""
        dispatcher = MagicMock()
        sink = live_session.ProfileSink(dispatcher)
        for mask in range(4096):
            sink.set_buttons(gamepad_buttons(gamebub_buttons(mask)))
            self.assertEqual(dispatcher.apply.call_args.args, (mask,))
        live_session.ProfileSink().set_buttons(0)

    def test_input_only_handshake_keepalive_stop(self):
        """@brief One socket owns handshake, ordered snapshots and next-sequence STOP."""
        sock = PeerSocket()
        events = []
        result = live_session.run_av(
            self.args(),
            lambda kind, **fields: events.append((kind, fields)),
            clock=Clock(),
            socket_factory=lambda *args: sock,
        )
        self.assertGreater(result["input_packets"], 0)
        self.assertEqual(result["input_timeouts"], 0)
        self.assertEqual(sock.sent[-1].kind, 4)
        self.assertTrue(sock.closed)
        self.assertEqual(events[-1][0], "av_summary")
        self.assertTrue(result["stop_sent"])
        stop_event = next(fields for kind, fields in events if kind == "stop_sent")
        self.assertEqual(decode(bytes.fromhex(stop_event["wire_hex"])).kind, 4)

    def test_partial_stop_send_is_reported_and_socket_is_closed(self):
        """@brief A short control send cannot claim successful STOP transmission."""
        sock = PeerSocket()
        original = sock.send

        def short_stop(raw):
            """@brief Preserve handshake while simulating a partial STOP send."""
            if decode(raw).kind == 4:
                return len(raw) - 1
            return original(raw)

        sock.send = short_stop
        result = live_session.run_av(
            self.args(), lambda *a, **kw: None, clock=Clock(), socket_factory=lambda *a: sock
        )
        self.assertFalse(result["stop_sent"])
        self.assertIn("Partial AV STOP", result["stop_error"])
        self.assertTrue(sock.closed)

    def test_owned_completion_sends_stop_before_nominal_duration(self):
        """@brief A completion predicate ends AV through its normal STOP/cleanup path."""
        sock = PeerSocket()
        checks = []

        def finished():
            """@brief Simulate video closing after several AV iterations."""
            checks.append(True)
            return len(checks) == 4

        result = live_session.run_av(
            self.args(seconds=60),
            lambda *args, **fields: None,
            clock=Clock(),
            socket_factory=lambda *args: sock,
            stop_when=finished,
        )
        self.assertEqual(len(checks), 4)
        self.assertEqual(result["input_timeouts"], 0)
        self.assertEqual(sock.sent[-1].kind, 4)
        self.assertTrue(sock.closed)

    def test_completion_predicate_failure_still_sends_stop(self):
        """@brief Owner errors cannot bypass session/socket cleanup."""
        sock = PeerSocket()

        def failed():
            """@brief Simulate an unexpected owner-state inspection failure."""
            raise RuntimeError("owner failure")

        with self.assertRaisesRegex(RuntimeError, "owner failure"):
            live_session.run_av(
                self.args(),
                lambda *args, **fields: None,
                clock=Clock(),
                socket_factory=lambda *args: sock,
                stop_when=failed,
            )
        self.assertEqual(sock.sent[-1].kind, 4)
        self.assertTrue(sock.closed)

    def test_timeout_neutralizes_even_when_no_buttons_held(self):
        """@brief Neutral input still has a finite liveness lease independent of audio/video."""
        sock = PeerSocket(keep=False)
        dispatcher = MagicMock()
        dispatcher.close.return_value = None
        with (
            patch.object(live_session.VigemXbox360Backend, "create"),
            patch.object(live_session, "GamepadDispatcher", return_value=dispatcher),
            self.assertRaises(TimeoutError),
        ):
            live_session.run_av(
                self.args(seconds=1, gamepad=True),
                lambda *a, **k: None,
                clock=Clock(),
                socket_factory=lambda *args: sock,
            )
        dispatcher.close.assert_called_once()
        self.assertEqual(dispatcher.apply.call_args.args, (0,))

    def test_audio_send_stale_and_inactive(self):
        """@brief Allocate transmitted sequence from encoded IDs and never fabricate silent PCM."""
        sock = PeerSocket(audio=True)
        worker = MagicMock()
        worker.error = None
        worker.last_capture_ns = None
        worker.blocks = queue.Queue()
        block = bytes(512)
        worker.blocks.put((0, -1_000_000_000, block))
        worker.blocks.put((4, 100_000_000, block))
        worker.close.return_value = {"shutdown_complete": True}
        events = []
        result = live_session.run_av(
            self.args(audio=True, seconds=0.3),
            lambda kind, **kw: events.append(kind),
            clock=Clock(),
            socket_factory=lambda *args: sock,
            audio_factory=lambda *a, **k: worker,
        )
        self.assertGreater(result["audio_stale"], 0)
        self.assertGreater(result["audio_sent"], 0)
        self.assertIn("audio_source_inactive", events)
        self.assertEqual([p.sequence for p in sock.sent if p.magic == b"MSA1"], [4])
        worker.close.assert_called_once()

    def test_noisy_wire_and_stop_failure_preserve_cleanup(self):
        """@brief Malformed/stale packets cannot refresh input; STOP failure still cleans up."""

        class NoisySocket(PeerSocket):
            def send(self, raw):
                """@brief Insert malformed and stale packets before a valid peer response."""
                packet = decode(raw)
                if packet.magic == b"MSC1" and packet.kind == 4:
                    raise OSError("stop failed")
                count = super().send(raw)
                if packet.magic == b"MSC1" and packet.kind == 1:
                    self.pending.insert(0, b"bad")
                    wrong = Packet(
                        b"MSR1", 1, 42, flags=0, payload=NONCE.pack(packet.session + 1)
                    ).encode()
                    self.pending.insert(0, wrong)
                if packet.magic == b"MSC1" and packet.kind == 2:
                    self.pending.insert(0, Packet(b"MSC1", 3, 42, sequence=2).encode())
                if packet.magic == b"MSC1" and packet.kind == 3:
                    self.pending.extend([self.pending[-1], b"bad"])
                return count

            def close(self):
                """@brief Record release before surfacing a close diagnostic."""
                super().close()
                raise OSError("close failed")

        sock = NoisySocket()
        result = live_session.run_av(
            self.args(seconds=0.4),
            lambda *a, **k: None,
            clock=Clock(),
            socket_factory=lambda *args: sock,
        )
        self.assertGreater(result["invalid_packets"], 0)
        self.assertGreater(result["stale_packets"], 0)
        self.assertIn("stop failed", result["stop_error"])
        self.assertTrue(result["cleanup_errors"])

    def test_handshake_timeout_and_audio_error(self):
        """@brief Establishment and producer errors stop finite sessions without leaking input."""
        from av_session import AvSession

        sock = PeerSocket()
        sock.recvfrom = MagicMock(side_effect=TimeoutError)
        session = AvSession(sock.peer, live_session.ProfileSink())
        with self.assertRaises(TimeoutError):
            live_session.handshake(session, sock, sock.peer, Clock(), timeout=0.03)
        with (
            patch.object(live_session.VigemXbox360Backend, "create", side_effect=OSError("driver")),
            self.assertRaises(OSError),
        ):
            live_session.run_av(self.args(gamepad=True), lambda *a, **k: None, clock=Clock())
        sock = PeerSocket(audio=True)
        worker = MagicMock()
        worker.error = "capture failed"
        with self.assertRaises(RuntimeError):
            live_session.run_av(
                self.args(audio=True),
                lambda *a, **k: None,
                clock=Clock(),
                socket_factory=lambda *args: sock,
                audio_factory=lambda *a, **k: worker,
            )
        worker.close.assert_called_once()

    def test_inactive_source_resumes(self):
        """@brief A renewed callback clears inactivity independently of receiver counters."""
        sock = PeerSocket(audio=True)
        worker = MagicMock()
        worker.error = None
        worker.last_capture_ns = None
        worker.blocks = queue.Queue()
        clock = Clock()

        def recovering_clock():
            value = clock()
            if value > 200_000_000:
                worker.last_capture_ns = value
            return value

        events = []
        live_session.run_av(
            self.args(audio=True, seconds=0.4),
            lambda kind, **kw: events.append(kind),
            clock=recovering_clock,
            socket_factory=lambda *args: sock,
            audio_factory=lambda *a, **k: worker,
        )
        self.assertIn("audio_source_resumed", events)

    def test_pacing_wait_and_failed_establishment_cleanup(self):
        """@brief Audio pacing waits between blocks; a failed handshake also closes safely."""
        worker = MagicMock()
        worker.error = None
        worker.last_capture_ns = None
        worker.blocks = queue.Queue()
        worker.blocks.put((0, 0, bytes(512)))
        clock = Clock()

        def slow_clock():
            clock.now += 10_000
            return clock.now

        result = live_session.run_av(
            self.args(audio=True, seconds=0.003),
            lambda *a, **kw: None,
            clock=slow_clock,
            socket_factory=lambda *a: PeerSocket(audio=True),
            audio_factory=lambda *a, **kw: worker,
        )
        self.assertEqual(result["audio_sent"], 1)
        sock = PeerSocket()
        sock.recvfrom = MagicMock(side_effect=TimeoutError)
        with self.assertRaises(TimeoutError):
            live_session.run_av(
                self.args(), lambda *a, **kw: None, clock=Clock(), socket_factory=lambda *a: sock
            )
        self.assertTrue(sock.closed)

    def test_session_close_diagnostic_does_not_skip_other_cleanup(self):
        """@brief Repeated close failures are recorded while the socket is still released."""
        from av_session import AvSession

        class FailingClose(AvSession):
            def close(self):
                """@brief Fail after performing the real neutral release."""
                super().close()
                raise OSError("release diagnostic")

        sock = PeerSocket()
        with patch.object(live_session, "AvSession", FailingClose):
            result = live_session.run_av(
                self.args(), lambda *a, **kw: None, clock=Clock(), socket_factory=lambda *a: sock
            )
        self.assertTrue(sock.closed)
        self.assertIn("release diagnostic", result["cleanup_errors"][0])


if __name__ == "__main__":
    unittest.main()
