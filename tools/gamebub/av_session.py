"""@brief Transport-independent AV v1 host handshake, sequence spaces and input lease.

Callers must use one peer-bound UDP socket and tick expiry independently of
video/input arrival. This adapter is not a live socket runner or audio queue.
"""

import secrets

from av_protocol import INPUT, KEEP_NS, LEASE_NS, NONCE, OFFER_NS, Packet, decode, input_status
from windows_gamepad import OrderedInput


class AvSession:
    """@brief One host session with a fresh nonce and independently ordered MSI1 input."""

    def __init__(self, peer, sink, audio=False, nonce=None):
        """@brief Pin a peer and digital sink; random nonzero 64-bit nonce is the default."""
        if nonce is None:
            nonce = secrets.randbelow((1 << 64) - 1) + 1
        Packet(b"MSC1", 1, nonce, flags=int(audio)).validate()
        if type(audio) is not bool or not isinstance(peer, tuple) or len(peer) != 2:
            raise ValueError("Invalid AV peer/audio mode")
        self.peer, self.sink, self.audio_enabled, self.nonce = peer, sink, audio, nonce
        self.state = "hello"
        self.cookie = self.offered_ns = self.last_clock_ns = None
        self.input = self.status = self.last_keep_ns = None
        self.control_sequence, self.audio_sequence = 2, 0
        sink.set_buttons(0)

    def _time(self, now_ns):
        """@brief Require monotonic host time, also across rejected datagrams."""
        if (
            type(now_ns) is not int
            or now_ns < 0
            or (self.last_clock_ns is not None and now_ns < self.last_clock_ns)
        ):
            raise ValueError("Invalid AV host monotonic clock")
        self.last_clock_ns = now_ns

    def hello(self, now_ns):
        """@brief Build an initial/retried HELLO without replacing its nonce."""
        self._time(now_ns)
        if self.state != "hello":
            raise RuntimeError("HELLO is only valid before accepting an offer")
        return Packet(
            b"MSC1", 1, self.nonce, flags=int(self.audio_enabled), timestamp_us=now_ns // 1000
        ).encode()

    def offer(self, raw, peer, now_ns):
        """@brief Accept only a matching peer/nonce/flags OFFER before preparing START."""
        self._time(now_ns)
        if peer != self.peer or self.state != "hello":
            return False
        packet = decode(raw)
        if (
            packet.magic != b"MSR1"
            or packet.flags != int(self.audio_enabled)
            or packet.payload != NONCE.pack(self.nonce)
        ):
            return False
        self.cookie, self.offered_ns, self.state = packet.session, now_ns, "offered"
        return True

    def start(self, now_ns):
        """@brief Build/retry START1 for this offer; do not reset sequence spaces on retry."""
        self._time(now_ns)
        if self.state not in ("offered", "starting", "active"):
            raise RuntimeError("START requires a matching pending offer")
        if self.state != "active" and now_ns - self.offered_ns >= OFFER_NS:
            self.close()
            raise TimeoutError("AV offer expired locally; create a fresh session")
        if self.state != "active":
            self.state = "starting"
        return Packet(
            b"MSC1",
            2,
            self.cookie,
            sequence=1,
            flags=int(self.audio_enabled),
            timestamp_us=now_ns // 1000,
            payload=NONCE.pack(self.nonce),
        ).encode()

    def receive_input(self, raw, peer, now_ns):
        """@brief Confirm ACTIVE and apply only newer MSI1 for the matching cookie/source."""
        self._time(now_ns)
        if peer != self.peer or self.state not in ("starting", "active"):
            return False
        packet = decode(raw)
        if packet.magic != b"MSI1" or packet.session != self.cookie:
            return False
        values = INPUT.unpack(packet.payload)
        if not values[6] & 1 or bool(values[6] & 2) != self.audio_enabled:
            return False
        if self.input is None:
            # Generic adapter's local token is not the wire representation.
            self.input = OrderedInput(self.cookie.to_bytes(16, "big"), self.sink, LEASE_NS)
            self.last_keep_ns = now_ns
        try:
            accepted = self.input.accept(
                self.cookie.to_bytes(16, "big"), packet.sequence, values[0], now_ns
            )
        except OSError:
            self.close()
            raise
        if accepted:
            self.state, self.status = "active", input_status(packet)
        return accepted

    def keepalive(self, now_ns):
        """@brief Build a newer KEEPALIVE every 100ms, independent of video/audio IDs."""
        self._time(now_ns)
        if self.state != "active":
            raise RuntimeError("KEEPALIVE requires ACTIVE confirmation")
        if now_ns - self.last_keep_ns < KEEP_NS:
            return None
        packet = Packet(
            b"MSC1", 3, self.cookie, sequence=self.control_sequence, timestamp_us=now_ns // 1000
        ).encode()
        self.control_sequence = (self.control_sequence + 1) & 0xFFFFFFFF
        self.last_keep_ns = now_ns
        return packet

    def prepare_audio(self, block, now_ns):
        """@brief Allocate sequence per encoded block before any bounded-queue discard.

        @return One MSA1 datagram; caller owns deadline/bounded queue and actual send.
        """
        self._time(now_ns)
        if self.state != "active" or not self.audio_enabled:
            raise RuntimeError("Audio requires an ACTIVE audio-enabled session")
        packet = Packet(
            b"MSA1",
            1,
            self.cookie,
            sequence=self.audio_sequence,
            timestamp_us=now_ns // 1000,
            payload=block,
        ).encode()
        self.audio_sequence = (self.audio_sequence + 1) & 0xFFFFFFFF
        return packet

    def expire_input(self, now_ns):
        """@brief Neutralize at 500ms without newer MSI1; a newer same-cookie MSI1 may recover."""
        self._time(now_ns)
        try:
            return self.input.expire(now_ns) if self.input is not None else False
        except OSError:
            self.close()
            raise

    def stop(self, now_ns):
        """@brief Build next-sequence STOP and release controls even if no reply will arrive."""
        self._time(now_ns)
        if self.state not in ("starting", "active"):
            self.close()
            return None
        packet = Packet(
            b"MSC1", 4, self.cookie, sequence=self.control_sequence, timestamp_us=now_ns // 1000
        ).encode()
        self.control_sequence = (self.control_sequence + 1) & 0xFFFFFFFF
        self.close()
        return packet

    def close(self):
        """@brief End input injection; caller retains ownership of socket/backend cleanup."""
        if self.state != "closed":
            self.state = "closed"
            if self.input is not None:
                self.input.close()
            else:
                self.sink.set_buttons(0)
