"""@brief Regression tests against the pinned MoonBub receiver packet fixture."""

import contextlib
import hashlib
import io
import json
import socket
import struct
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from host import Profile, canvas, encode, pattern
from msv1 import (
    FEEDBACK,
    Pacer,
    PartialSendError,
    ValidatedJpeg,
    encode_receiver_jpeg,
    frame_datagrams,
    gamebub_buttons,
    main,
    parse_feedback,
    send_frame,
    validate_receiver_jpeg,
)
from realtime import gamepad_buttons


class ReceiverProtocolTests(unittest.TestCase):
    """@brief Exercise the actual JPEG restrictions, wire bytes and feedback."""

    @classmethod
    def setUpClass(cls):
        """@brief Read receiver-owned deterministic fixtures pinned in the handoff."""
        directory = Path(__file__).parent / "fixtures"
        cls.jpeg = (directory / "receiver-pattern-720x480-420-q65.jpg").read_bytes()
        cls.golden = (directory / "receiver-pattern-msv1-packets.bin").read_bytes()

    def test_exact_receiver_golden_datagrams(self):
        """@brief Match every header, payload and CRC against the receiver's fixture."""
        self.assertEqual(
            hashlib.sha256(self.jpeg).hexdigest(),
            "8cc99ea7d50d1d20255e41ff7247b0770b3349e705c27152a41817418ce5c9de",
        )
        self.assertEqual(
            hashlib.sha256(self.golden).hexdigest(),
            "78c58cfcc4860761c33bcc7021e3db14e9fa66ef5e9a385ae1e4c00c82a6447f",
        )
        frames = frame_datagrams(self.jpeg, 0x12345678, 1234567890123)
        actual = b"".join(struct.pack("!H", len(packet)) + packet for packet in frames)
        self.assertEqual(actual, self.golden)

    def test_restricted_jpeg_validation(self):
        """@brief Accept baseline 420 and reject unsupported receiver options."""
        self.assertEqual(validate_receiver_jpeg(self.jpeg)["subsampling"], "4:2:0")
        image = canvas(pattern(0))
        unsupported = [
            encode(image, 65, Profile("4:4:4"))[0],
            encode(image, 65, Profile("4:2:2"))[0],
            encode(image, 65, Profile(restart_mcus=10))[0],
            b"x",
            self.jpeg + bytes(262144),
        ]
        for jpeg in unsupported:
            with self.subTest(length=len(jpeg)), self.assertRaises(ValueError):
                validate_receiver_jpeg(jpeg)

    def test_receiver_encoder_validates_once_and_preserves_packet_bytes(self):
        """@brief Strictly inspect each encoded JPEG once and packetize immutable bytes."""
        image = canvas(pattern(0))
        reference, _ = encode(image, 75, Profile())
        with patch("msv1.validate_receiver_jpeg", wraps=validate_receiver_jpeg) as validate:
            jpeg = encode_receiver_jpeg(image, 75)
            self.assertIsInstance(jpeg, ValidatedJpeg)
            self.assertEqual(jpeg, reference)
            packets = list(frame_datagrams(jpeg, 1, 2))
            self.assertEqual(validate.call_count, 1)
            self.assertEqual(packets, list(frame_datagrams(reference, 1, 2)))
            self.assertEqual(validate.call_count, 2)

    def test_validated_jpeg_and_encoder_reject_invalid_inputs(self):
        """@brief Reject mutable or invalid bytes, wrong canvas modes and invalid quality."""
        for data in (bytearray(self.jpeg), b"invalid"):
            with self.subTest(data=type(data)), self.assertRaises(ValueError):
                ValidatedJpeg(data)
        image = canvas(pattern(0))
        for bad_image, quality in (
            (None, 75),
            (Image.new("L", (720, 480)), 75),
            (Image.new("RGB", (10, 10)), 75),
            (image, True),
            (image, 0),
            (image, 96),
        ):
            with self.subTest(quality=quality), self.assertRaises(ValueError):
                encode_receiver_jpeg(bad_image, quality)

    def test_receiver_rtl_verified_host_fixture_is_transmittable(self):
        """@brief The exact 420 frame exercised by the receiver RTL meets the host profile."""
        jpeg = (Path(__file__).parent / "fixtures/frame-00000000-420-r0.jpg").read_bytes()
        self.assertEqual(
            hashlib.sha256(jpeg).hexdigest(),
            "b327b1c2e2af7988e66f2ae570534a91c4526bbb53739ee5809f51e123228fb6",
        )
        self.assertEqual(validate_receiver_jpeg(jpeg)["subsampling"], "4:2:0")
        self.assertGreater(len(list(frame_datagrams(jpeg, 7, 1))), 1)

    def test_reject_header_profile_changes(self):
        """@brief Reject unsupported marker layouts, altered dimensions and tables."""
        jpeg = self.jpeg
        app = jpeg.index(b"JFIF\x00")
        sof = jpeg.index(b"\xff\xc0")
        dht = jpeg.index(b"\xff\xc4")
        altered = [
            jpeg[:app] + b"NOPE\x00" + jpeg[app + 5 :],
            jpeg[: sof + 7] + b"\x01\x00" + jpeg[sof + 9 :],
            jpeg[: dht + 21] + bytes([jpeg[dht + 21] ^ 1]) + jpeg[dht + 22 :],
            jpeg[:2] + b"\xff\xfe\x00\x03x" + jpeg[2:],
        ]
        for value in altered:
            with self.assertRaises(ValueError):
                validate_receiver_jpeg(value)

    def test_packet_limits(self):
        """@brief Check identifier, timestamp and payload bounds without network I/O."""
        for args in (
            (-1, 0, 1024),
            (2**32, 0, 1024),
            (1, -1, 1024),
            (1, 2**64, 1024),
            (1, 0, 0),
            (1, 0, 1025),
            (True, 0, 1),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                list(frame_datagrams(self.jpeg, *args))
        packets = list(frame_datagrams(self.jpeg, 0, 0, 1000))
        self.assertGreater(len(packets), 1)
        self.assertTrue(all(len(packet) <= 1040 for packet in packets))

    def test_feedback_and_button_mapping(self):
        """@brief Parse peer feedback and translate all twelve receiver button bits."""
        data = FEEDBACK.pack(b"MSF1", 1, 0, 0xFFF, 99, 42, 7, 3, 123)
        feedback = parse_feedback(data)
        self.assertEqual((feedback.status, feedback.frame_id, feedback.capture_us), (0, 99, 123))
        self.assertEqual(
            gamebub_buttons(feedback.buttons),
            frozenset(
                ("a", "b", "x", "y", "up", "down", "left", "right", "l", "r", "start", "select")
            ),
        )
        for invalid in (
            b"",
            FEEDBACK.pack(b"FAIL", 1, 0, 0, 0, 0, 0, 0, 0),
            FEEDBACK.pack(b"MSF1", 2, 0, 0, 0, 0, 0, 0, 0),
            FEEDBACK.pack(b"MSF1", 1, 4, 0, 0, 0, 0, 0, 0),
        ):
            with self.assertRaises(ValueError):
                parse_feedback(invalid)
        for mask in (-1, 4096, True):
            with self.assertRaises(ValueError):
                gamebub_buttons(mask)

    def test_each_receiver_button_maps_to_expected_sunshine_flag(self):
        """@brief Exercise each hardware bit through to the intended gamepad flag."""
        expected = (
            0x0020,
            0x0010,
            0x0200,
            0x0100,
            0x0008,
            0x0004,
            0x0002,
            0x0001,
            0x8000,
            0x4000,
            0x2000,
            0x1000,
        )
        for bit, flag in enumerate(expected):
            with self.subTest(bit=bit):
                self.assertEqual(gamepad_buttons(gamebub_buttons(1 << bit)), flag)

    def test_all_button_combinations_preserve_independent_presses(self):
        """@brief Every 12-bit snapshot maps its chords and releases independently."""
        flags = (
            0x0020,
            0x0010,
            0x0200,
            0x0100,
            0x0008,
            0x0004,
            0x0002,
            0x0001,
            0x8000,
            0x4000,
            0x2000,
            0x1000,
        )
        for mask in range(4096):
            expected = sum(flag for bit, flag in enumerate(flags) if mask & (1 << bit))
            packet = FEEDBACK.pack(b"MSF1", 1, 0, mask, 1, 0, 0, 0, 0)
            self.assertEqual(
                gamepad_buttons(gamebub_buttons(parse_feedback(packet).buttons)), expected
            )

    def test_paced_send_and_expiry(self):
        """@brief Pace actual datagrams and stop a stale partial frame before its deadline."""
        now = [0.0]
        sock = Mock()
        sock.send.side_effect = lambda packet: len(packet)
        sleeper = lambda delay: now.__setitem__(0, now[0] + delay)
        done, sent = send_frame(sock, self.jpeg, 1, 4, 100000, 1, lambda: now[0], sleeper)
        self.assertTrue(done)
        self.assertEqual(sent, sum(len(c.args[0]) for c in sock.send.call_args_list))
        now[0] = 0
        sock.reset_mock()
        done, sent = send_frame(sock, self.jpeg, 2, 5, 100000, 0.015, lambda: now[0], sleeper)
        self.assertFalse(done)
        self.assertEqual(sent, 0)
        sock.send.assert_not_called()
        with self.assertRaises(ValueError):
            send_frame(sock, self.jpeg, 1, 2, 0, 1)
        sock.send.return_value = 1
        sock.send.side_effect = None
        with self.assertRaises(OSError):
            send_frame(sock, self.jpeg, 1, 2, 100000, 1, lambda: 0, sleeper)

        now[0] = 0
        sock.send.side_effect = lambda packet: len(packet)

        def late_sleep(delay):
            """@brief Simulate Windows waking after the sender's deadline."""
            now[0] += delay + 1

        done, sent = send_frame(sock, self.jpeg, 1, 2, 100000, 0.3, lambda: now[0], late_sleep)
        self.assertFalse(done)
        self.assertGreater(sent, 0)

    def test_socket_error_after_datagram_preserves_partial_byte_count(self):
        """@brief Wrap a partial socket failure while preserving its errno, text and cause."""
        packets = list(frame_datagrams(self.jpeg, 1, 2))
        error = OSError(10054, "receiver unavailable")
        sock = Mock()
        sock.send.side_effect = [len(packets[0]), error]
        now, recorded = [0.0], []
        sleeper = lambda delay: now.__setitem__(0, now[0] + delay)
        pacer = Pacer()
        with self.assertRaises(PartialSendError) as raised:
            send_frame(
                sock,
                self.jpeg,
                1,
                2,
                100000,
                10,
                lambda: now[0],
                sleeper,
                pacer,
                lambda packet, stamp: recorded.append((packet, stamp)),
            )
        failure = raised.exception
        self.assertIsInstance(failure, OSError)
        self.assertEqual(failure.sent_bytes, len(packets[0]))
        self.assertIs(failure.original_error, error)
        self.assertIs(failure.__cause__, error)
        self.assertEqual(failure.errno, error.errno)
        self.assertEqual(failure.args, error.args)
        self.assertEqual(str(failure), str(error))
        self.assertEqual([item[0] for item in recorded], packets[:1])
        self.assertIsNotNone(pacer.next_due)

    def test_zero_byte_socket_error_is_unmodified(self):
        """@brief Failure before the first packet retains the original exception object."""
        error = OSError(10054, "receiver unavailable")
        sock = Mock()
        sock.send.side_effect = error
        recorded = []
        with self.assertRaises(OSError) as raised:
            send_frame(
                sock,
                self.jpeg,
                1,
                2,
                100000,
                10,
                lambda: 0,
                on_packet=lambda packet, stamp: recorded.append((packet, stamp)),
            )
        self.assertIs(raised.exception, error)
        self.assertEqual(recorded, [])

    def test_short_datagram_after_success_reports_only_complete_packets(self):
        """@brief A short UDP send is not counted as a completely sent datagram."""
        packets = list(frame_datagrams(self.jpeg, 1, 2))
        sock = Mock()
        sock.send.side_effect = [len(packets[0]), 1]
        now, recorded = [0.0], []
        sleeper = lambda delay: now.__setitem__(0, now[0] + delay)
        with self.assertRaisesRegex(PartialSendError, "Partial UDP datagram send") as raised:
            send_frame(
                sock,
                self.jpeg,
                1,
                2,
                100000,
                10,
                lambda: now[0],
                sleeper,
                on_packet=lambda packet, stamp: recorded.append((packet, stamp)),
            )
        self.assertEqual(raised.exception.sent_bytes, len(packets[0]))
        self.assertEqual([item[0] for item in recorded], packets[:1])

    def test_preflight_accounts_for_pending_pacer_and_validates_input(self):
        """@brief A pending pacer can make a frame infeasible without emitting a partial frame."""
        sock = Mock()
        pacer = Pacer(next_due=0.9)
        done, sent = send_frame(sock, self.jpeg, 1, 2, 100000, 1, lambda: 0, lambda _: None, pacer)
        self.assertFalse(done)
        self.assertEqual(sent, 0)
        self.assertEqual(pacer.next_due, 0.9)
        sock.send.assert_not_called()
        with self.assertRaises(ValueError):
            send_frame(sock, b"bad", 1, 2, 100000, 0.00001, lambda: 0)

    def test_elapsed_time_after_send_can_expire_remaining_frame(self):
        """@brief An unexpected socket delay can expire a previously feasible frame."""
        now = [0.0]
        sock = Mock()

        def delayed_send(packet):
            """@brief Delay after accepting the first datagram."""
            now[0] += 1
            return len(packet)

        sock.send.side_effect = delayed_send
        done, sent = send_frame(sock, self.jpeg, 1, 2, 100000, 0.5, lambda: now[0])
        self.assertFalse(done)
        self.assertGreater(sent, 0)
        self.assertEqual(sock.send.call_count, 1)

    def test_validation_delay_does_not_cause_packet_burst(self):
        """@brief Validation or scheduler delays do not grant a burst of link credit."""
        now = [0.0]
        sends = []
        sock = Mock()
        sock.send.side_effect = lambda packet: sends.append((now[0], len(packet))) or len(packet)

        def validate(_data):
            """@brief Spend time validating before the first packet becomes available."""
            now[0] += 0.1

        def sleep(delay):
            """@brief Advance the deterministic monotonic clock."""
            now[0] += delay

        with patch("msv1.validate_receiver_jpeg", side_effect=validate):
            done, _ = send_frame(sock, self.jpeg, 1, 2, 100000, 1, lambda: now[0], sleep)
        self.assertTrue(done)
        for (started, length), (following, _) in pairwise(sends):
            self.assertGreaterEqual(following - started + 1e-12, length / 100000)

    def test_pacing_is_preserved_across_frame_boundaries(self):
        """@brief The next frame cannot burst immediately after the prior final packet."""
        now, sends = [0.0], []
        sock = Mock()
        sock.send.side_effect = lambda packet: sends.append((now[0], len(packet))) or len(packet)
        pacer = Pacer()
        sleeper = lambda delay: now.__setitem__(0, now[0] + delay)
        for frame_id in (1, 2):
            self.assertTrue(
                send_frame(
                    sock, self.jpeg, frame_id, 2, 100000, 10, lambda: now[0], sleeper, pacer
                )[0]
            )
        for (started, size), (following, _) in pairwise(sends):
            self.assertGreaterEqual(following - started + 1e-12, size / 100000)

    def test_pacer_waits_again_after_early_wakeup(self):
        """@brief Early timer wakeups never release a chunk ahead of its paced time."""
        now, sends, waits = [0.0], [], []
        sock = Mock()
        sock.send.side_effect = lambda packet: sends.append((now[0], len(packet))) or len(packet)

        def early_once(delay):
            """@brief Wake halfway through alternating waits, then advance to the target."""
            waits.append(delay)
            now[0] += delay / 2 if len(waits) % 2 else delay

        self.assertTrue(send_frame(sock, self.jpeg, 1, 2, 100000, 2, lambda: now[0], early_once)[0])
        self.assertGreater(len(waits), len(sends) - 1)
        for (started, size), (following, _) in pairwise(sends):
            self.assertGreaterEqual(following - started + 1e-12, size / 100000)

    def test_pacer_anchors_next_send_after_delayed_socket_call(self):
        """@brief Preemption during a socket call cannot shorten the next send interval."""
        now, sends = [0.0], []
        sock = Mock()

        def delayed_send(packet):
            """@brief Simulate a delayed send and record when the call completes."""
            now[0] += 0.004
            sends.append((now[0], len(packet)))
            return len(packet)

        sock.send.side_effect = delayed_send
        sleeper = lambda delay: now.__setitem__(0, now[0] + delay)
        self.assertTrue(send_frame(sock, self.jpeg, 1, 2, 100000, 2, lambda: now[0], sleeper)[0])
        for (sent, size), (following, _) in pairwise(sends):
            self.assertGreaterEqual(following - sent + 1e-12, size / 100000)

    def test_optional_packet_callback_reports_offsets_and_times(self):
        """@brief Report only successfully sent datagrams in order, using the send clock."""
        now, recorded = [0.0], []
        sock = Mock()
        sock.send.side_effect = lambda packet: len(packet)
        sleeper = lambda delay: now.__setitem__(0, now[0] + delay)
        done, _ = send_frame(
            sock,
            self.jpeg,
            1,
            2,
            100000,
            2,
            lambda: now[0],
            sleeper,
            on_packet=lambda packet, stamp: recorded.append((packet, stamp)),
        )
        self.assertTrue(done)
        self.assertEqual([p for p, _ in recorded], list(frame_datagrams(self.jpeg, 1, 2)))
        self.assertTrue(all(b[1] >= a[1] for a, b in pairwise(recorded)))

    def test_localhost_udp_datagrams_match_receiver_fixture(self):
        """@brief Send real loopback UDP packets and compare receiver-side bytes."""
        expected = list(frame_datagrams(self.jpeg, 0x12345678, 1234567890123))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.connect(receiver.getsockname())
                done, _ = send_frame(
                    sender, self.jpeg, 0x12345678, 1234567890123, 1000000000, float("1e20")
                )
            self.assertTrue(done)
            received = [receiver.recv(2048) for _ in expected]
        self.assertEqual(received, expected)

    def test_single_frame_command_and_matching_feedback(self):
        """@brief Ignore stale feedback and report a matching ingress acknowledgement."""
        fixture = Path(__file__).parent / "fixtures/receiver-pattern-720x480-420-q65.jpg"
        peer = MagicMock()
        peer.__enter__.return_value = peer
        stale = FEEDBACK.pack(b"MSF1", 1, 0, 0, 0, 0, 0, 0, 123)
        good = FEEDBACK.pack(b"MSF1", 1, 0, 0, 1, 0, 1, 0, 123)
        peer.recv.side_effect = [stale, good]
        stdout = io.StringIO()
        with (
            patch("msv1.socket.socket", return_value=peer),
            patch("msv1.time.time_ns", return_value=123000),
            patch("msv1.send_frame", return_value=(True, 50)),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(
                main(["127.0.0.1", "--jpeg", str(fixture), "--source-port", "55534"]), 0
            )
        peer.bind.assert_called_once_with(("0.0.0.0", 55534))
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["sent_complete"])
        self.assertFalse(result["end_to_end_verified"])
        self.assertEqual(result["feedback"]["received_frames"], 1)

    def test_single_frame_packet_log_records_actual_offsets(self):
        """@brief Persist optional timing after transmission without overwriting old logs."""
        fixture = Path(__file__).parent / "fixtures/receiver-pattern-720x480-420-q65.jpg"
        peer = MagicMock()
        peer.__enter__.return_value = peer
        peer.recv.return_value = FEEDBACK.pack(b"MSF1", 1, 0, 0, 1, 0, 1, 0, 123)
        packets = list(frame_datagrams(self.jpeg, 1, 123))

        def fake_send(*args, on_packet=None):
            """@brief Simulate two successful sends with deterministic timestamps."""
            on_packet(packets[0], 10.0)
            on_packet(packets[1], 10.02)
            return True, len(packets[0]) + len(packets[1])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packets.json"
            with (
                patch("msv1.socket.socket", return_value=peer),
                patch("msv1.time.time_ns", return_value=123000),
                patch("msv1.send_frame", side_effect=fake_send),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    main(["127.0.0.1", "--jpeg", str(fixture), "--packet-log", str(path)]), 0
                )
            log = json.loads(path.read_text())
            self.assertEqual([row["offset"] for row in log["packets"]], [0, 1024])
            self.assertEqual([row["sent_monotonic_s"] for row in log["packets"]], [10.0, 10.02])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["127.0.0.1", "--jpeg", str(fixture), "--packet-log", str(path)])

    def test_single_frame_command_failures(self):
        """@brief Reject invalid arguments and do not confuse missing feedback with playback."""
        fixture = Path(__file__).parent / "fixtures/receiver-pattern-720x480-420-q65.jpg"
        for option, value in (
            ("--port", "0"),
            ("--source-port", "-1"),
            ("--source-port", "65536"),
            ("--frame-id", "-1"),
            ("--mbps", "nan"),
            ("--deadline-ms", "0"),
            ("--feedback-timeout", "0"),
        ):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["127.0.0.1", "--jpeg", str(fixture), option, value])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["127.0.0.1", "--jpeg", "missing-file.jpg"])
        for complete, reply in (
            (False, None),
            (True, TimeoutError()),
            (True, FEEDBACK.pack(b"MSF1", 1, 2, 0, 1, 0, 0, 1, 123)),
        ):
            peer = MagicMock()
            peer.__enter__.return_value = peer
            peer.recv.side_effect = reply if isinstance(reply, Exception) else None
            if isinstance(reply, bytes):
                peer.recv.return_value = reply
            with (
                patch("msv1.socket.socket", return_value=peer),
                patch("msv1.time.time_ns", return_value=123000),
                patch("msv1.send_frame", return_value=(complete, 50)),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(["127.0.0.1", "--jpeg", str(fixture)]), 2)

        peer = MagicMock()
        peer.__enter__.return_value = peer
        with (
            patch("msv1.socket.socket", return_value=peer),
            patch("msv1.time.perf_counter", side_effect=[0, 0, 1]),
            patch("msv1.send_frame", return_value=(True, 50)),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["127.0.0.1", "--jpeg", str(fixture)]), 2)


if __name__ == "__main__":
    unittest.main()
