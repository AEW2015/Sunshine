"""@brief AV v1 handshake and independent input/audio/control sequencing regressions."""

import unittest
from unittest.mock import MagicMock, patch

from av_protocol import INPUT, KEEP_NS, LEASE_NS, NONCE, OFFER_NS, Packet, decode
from av_session import AvSession

PEER = ("192.0.2.1", 5534)
OTHER = ("192.0.2.1", 5535)


def status(cookie=2, sequence=0, buttons=0, state=5):
    """@brief Build a complete test MSI1 with an independent sequence and cached counters."""
    return Packet(
        b"MSI1", 1, cookie, sequence=sequence, payload=INPUT.pack(buttons, 0, 0, 0, 0, 0, state, 0)
    ).encode()


class AvSessionTests(unittest.TestCase):
    """@brief Fake sinks and datagrams never inject input or contact a receiver."""

    def offered(self, audio=False):
        """@brief Construct a valid pending offer for deterministic host nonce1/cookie2."""
        sink = MagicMock()
        session = AvSession(PEER, sink, audio=audio, nonce=1)
        wire = Packet(b"MSR1", 1, 2, flags=int(audio), payload=NONCE.pack(1)).encode()
        self.assertTrue(session.offer(wire, PEER, 0))
        return session, sink

    def active(self, audio=False):
        """@brief Confirm a started session with its initial ACTIVE MSI1."""
        session, sink = self.offered(audio)
        session.start(0)
        self.assertTrue(session.receive_input(status(state=7 if audio else 5), PEER, 0))
        return session, sink

    def test_handshake_and_input_only_control_lifecycle(self):
        """@brief Preserve nonce/cookie across retries and require ACTIVE before data/keepalive."""
        sink = MagicMock()
        session = AvSession(PEER, sink, nonce=1)
        self.assertEqual(decode(session.hello(0)).session, 1)
        self.assertEqual(decode(session.hello(1)).sequence, 0)
        self.assertFalse(session.expire_input(2))
        self.assertFalse(session.receive_input(status(), PEER, 3))
        self.assertFalse(session.offer(b"invalid", OTHER, 4))
        for packet in (
            Packet(b"MSC1", 1, 1),
            Packet(b"MSR1", 1, 2, flags=1, payload=NONCE.pack(1)),
            Packet(b"MSR1", 1, 2, payload=NONCE.pack(3)),
        ):
            self.assertFalse(session.offer(packet.encode(), PEER, 5))
        with self.assertRaises(ValueError):
            session.offer(b"invalid", PEER, 6)
        offer = Packet(b"MSR1", 1, 2, payload=NONCE.pack(1)).encode()
        self.assertTrue(session.offer(offer, PEER, 7))
        self.assertFalse(session.offer(offer, PEER, 8))
        with self.assertRaises(RuntimeError):
            session.hello(9)
        start = decode(session.start(10))
        self.assertEqual((start.session, start.sequence, start.payload), (2, 1, NONCE.pack(1)))
        self.assertEqual(decode(session.start(11)).sequence, 1)
        for raw, peer in (
            (status(), OTHER),
            (status(3), PEER),
            (Packet(b"MSC1", 3, 2).encode(), PEER),
            (status(state=4), PEER),
            (status(state=7), PEER),
        ):
            self.assertFalse(session.receive_input(raw, peer, 12))
        self.assertTrue(session.receive_input(status(buttons=1 << 11), PEER, 13))
        self.assertEqual(sink.set_buttons.call_args.args, (0x1000,))
        self.assertIsNone(session.keepalive(14))
        keep = decode(session.keepalive(KEEP_NS + 13))
        self.assertEqual((keep.sequence, keep.kind, keep.flags), (2, 3, 0))
        # An active START receipt retry must not reset the control/input sequence spaces.
        self.assertEqual(decode(session.start(KEEP_NS + 14)).sequence, 1)
        self.assertEqual(session.state, "active")
        self.assertFalse(session.receive_input(status(sequence=0), PEER, KEEP_NS + 15))
        stop = decode(session.stop(KEEP_NS + 16))
        self.assertEqual((stop.kind, stop.sequence), (4, 3))
        self.assertEqual(sink.set_buttons.call_args.args, (0,))
        self.assertIsNone(session.stop(KEEP_NS + 17))
        session.close()

    def test_independent_audio_sequence_and_control_wrap(self):
        """@brief Discarded prepared blocks retain sequence gaps; control wrap is independent."""
        session, _ = self.active(audio=True)
        first = decode(session.prepare_audio(bytes(512), 1))
        session.prepare_audio(bytes(512), 2)  # Deliberately discard a queued block.
        third = decode(session.prepare_audio(bytes(512), 3))
        self.assertEqual((first.sequence, third.sequence), (0, 2))
        self.assertEqual((first.flags, first.session), (0, 2))
        session.audio_sequence = 0xFFFFFFFF
        self.assertEqual(decode(session.prepare_audio(bytes(512), 4)).sequence, 0xFFFFFFFF)
        self.assertEqual(decode(session.prepare_audio(bytes(512), 5)).sequence, 0)
        session.control_sequence = 0xFFFFFFFF
        self.assertEqual(decode(session.keepalive(KEEP_NS)).sequence, 0xFFFFFFFF)
        self.assertEqual(decode(session.keepalive(KEEP_NS * 2)).sequence, 0)
        self.assertEqual(decode(session.stop(KEEP_NS * 2 + 1)).sequence, 1)

    def test_input_reorder_wrap_and_exact_500ms_release(self):
        """@brief Video-independent MSI1 ordering and timeout cannot be refreshed by stale data."""
        session, sink = self.offered()
        session.start(0)
        self.assertTrue(session.receive_input(status(sequence=0xFFFFFFFF, buttons=1 << 7), PEER, 0))
        self.assertFalse(session.receive_input(status(sequence=0xFFFFFFFF), PEER, LEASE_NS - 2))
        self.assertFalse(session.expire_input(LEASE_NS - 1))
        self.assertTrue(session.expire_input(LEASE_NS))
        self.assertFalse(session.expire_input(LEASE_NS + 1))
        self.assertEqual(sink.set_buttons.call_args.args, (0,))
        self.assertFalse(session.receive_input(status(sequence=0xFFFFFFFE), PEER, LEASE_NS + 2))
        self.assertFalse(session.receive_input(status(sequence=0x7FFFFFFF), PEER, LEASE_NS + 3))
        self.assertTrue(
            session.receive_input(status(sequence=0, buttons=1 << 10), PEER, LEASE_NS + 4)
        )
        self.assertEqual(sink.set_buttons.call_args.args, (0x2000,))
        session.close()

    def test_expiry_unstarted_and_invalid_clocks(self):
        """@brief Offer expiry and malformed local calls cannot activate a session."""
        session, sink = self.offered()
        with self.assertRaises(TimeoutError):
            session.start(OFFER_NS)
        self.assertEqual(session.state, "closed")
        self.assertEqual(sink.set_buttons.call_args.args, (0,))
        unstarted = AvSession(PEER, MagicMock(), nonce=1)
        for operation in (unstarted.start, unstarted.keepalive):
            with self.assertRaises(RuntimeError):
                operation(0)
        with self.assertRaises(RuntimeError):
            unstarted.prepare_audio(bytes(512), 0)
        self.assertIsNone(unstarted.stop(0))
        session, _ = self.active()
        with self.assertRaises(RuntimeError):
            session.prepare_audio(bytes(512), 1)
        for now in (-1, True, 0):
            with self.assertRaises(ValueError):
                session.keepalive(now)
        session, _ = self.offered()
        session.start(0)
        self.assertEqual(decode(session.stop(1)).sequence, 2)

    def test_random_nonce_and_initial_validation(self):
        """@brief Fresh nonzero 64-bit nonce generation never uses a clock-derived cookie."""
        with patch("av_session.secrets.randbelow", return_value=7):
            self.assertEqual(AvSession(PEER, MagicMock()).nonce, 8)
        for peer, audio, nonce in (
            (None, False, 1),
            ((1,), False, 1),
            (PEER, 1, 1),
            (PEER, False, 0),
            (PEER, False, 2**64),
        ):
            with self.assertRaises(ValueError):
                AvSession(peer, MagicMock(), audio, nonce)

    def test_driver_failure_neutralizes_and_closes(self):
        """@brief Driver errors during input or timeout end the host input session."""
        for expire in (False, True):
            session, sink = self.active()
            if expire:
                session.receive_input(status(sequence=1, buttons=1 << 11), PEER, 1)
            sink.set_buttons.side_effect = [OSError("driver disappeared"), None]
            with self.assertRaises(OSError):
                if expire:
                    session.expire_input(LEASE_NS + 2)
                else:
                    session.receive_input(status(sequence=1, buttons=1 << 11), PEER, 1)
            self.assertEqual(session.state, "closed")
            self.assertEqual(sink.set_buttons.call_args.args, (0,))


if __name__ == "__main__":
    unittest.main()
