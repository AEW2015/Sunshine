"""@brief AV v1 packet conformance adapter pinned to MoonBub dff54528.

This module sends no network traffic. CRC/session cookies are correlation, not
authentication. Video MSV1/MSF1 and stock Moonlight formats remain separate.
"""

import struct
import zlib
from dataclasses import dataclass

from audio_codec import BLOCK_BYTES, BLOCK_SAMPLES, RATE, validate_block

HEADER = struct.Struct("!4sBBHQIIHHIQII")
INPUT = struct.Struct("!8I")
NONCE = struct.Struct("!Q")
PORT = 5534
LEASE_NS = 500_000_000
KEEP_NS = 100_000_000
OFFER_NS = 2_000_000_000


@dataclass(frozen=True)
class Packet:
    """@brief Schema-checked packet fields; identity and ordering are session-layer checks."""

    magic: bytes
    kind: int
    session: int
    sequence: int = 0
    flags: int = 0
    timestamp_us: int = 0
    payload: bytes = b""

    def validate(self):
        """@brief Reject unsupported schemas, bounds and payload contents before encoding."""
        for value, lower, upper in (
            (self.session, 1, 1 << 64),
            (self.sequence, 0, 1 << 32),
            (self.timestamp_us, 0, 1 << 64),
        ):
            if type(value) is not int or not lower <= value < upper:
                raise ValueError("Invalid AV integer")
        if type(self.magic) is not bytes or type(self.kind) is not int:
            raise ValueError("Invalid AV packet class")
        if type(self.payload) is not bytes:
            raise ValueError("AV payload must be immutable bytes")
        schema = {
            (b"MSC1", 1): (0, 1, 0),
            (b"MSC1", 2): (8, 1, 1),
            (b"MSC1", 3): (0, 0, None),
            (b"MSC1", 4): (0, 0, None),
            (b"MSR1", 1): (8, 1, 0),
            (b"MSA1", 1): (BLOCK_BYTES, 0, None),
            (b"MSI1", 1): (INPUT.size, 0, None),
        }
        if (self.magic, self.kind) not in schema:
            raise ValueError("Unsupported AV packet class")
        length, allowed_flags, fixed_sequence = schema[self.magic, self.kind]
        if (
            type(self.flags) is not int
            or self.flags < 0
            or self.flags & ~allowed_flags
            or len(self.payload) != length
            or (fixed_sequence is not None and self.sequence != fixed_sequence)
        ):
            raise ValueError("Invalid AV flags, length or fixed sequence")
        if length == NONCE.size and NONCE.unpack(self.payload)[0] == 0:
            raise ValueError("Zero echoed nonce")
        if self.magic == b"MSA1":
            validate_block(self.payload)
        if self.magic == b"MSI1":
            values = INPUT.unpack(self.payload)
            if values[0] & ~0xFFF or values[6] & ~7:
                raise ValueError("Unsupported MSI1 button/state bits")

    def encode(self):
        """@brief Encode a 48-byte network-order header and CRC over header plus payload."""
        self.validate()
        samples = BLOCK_SAMPLES if self.magic == b"MSA1" else 0
        raw = (
            HEADER.pack(
                self.magic,
                1,
                self.kind,
                HEADER.size,
                self.session,
                self.sequence,
                RATE,
                samples,
                len(self.payload),
                self.flags,
                self.timestamp_us,
                0,
                0,
            )
            + self.payload
        )
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        return raw[:40] + struct.pack("!I", crc) + raw[44:]


def decode(raw):
    """@brief Decode exactly one datagram, validating every header field and whole CRC."""
    if type(raw) is not bytes or not HEADER.size <= len(raw) <= HEADER.size + BLOCK_BYTES:
        raise ValueError("Invalid AV datagram length/type")
    (
        magic,
        version,
        kind,
        size,
        session,
        sequence,
        rate,
        samples,
        length,
        flags,
        timestamp,
        crc,
        reserved,
    ) = HEADER.unpack_from(raw)
    if (
        version != 1
        or size != HEADER.size
        or rate != RATE
        or reserved
        or len(raw) != HEADER.size + length
        or samples != (BLOCK_SAMPLES if magic == b"MSA1" else 0)
    ):
        raise ValueError("Unsupported AV header")
    if zlib.crc32(raw[:40] + bytes(4) + raw[44:]) & 0xFFFFFFFF != crc:
        raise ValueError("Whole-packet AV CRC mismatch")
    packet = Packet(magic, kind, session, sequence, flags, timestamp, raw[HEADER.size :])
    packet.validate()
    return packet


def input_status(packet):
    """@brief Extract MSI1 counters, hiding stale FPGA fields when snapshot-valid is clear."""
    packet.validate()
    if packet.magic != b"MSI1":
        raise ValueError("Expected MSI1 status")
    buttons, accepted, rejected, queued, played, underruns, state, build = INPUT.unpack(
        packet.payload
    )
    valid = bool(state & 4)
    return {
        "buttons": buttons,
        "accepted_audio_blocks": accepted,
        "rejected_or_unconfirmed_audio_blocks": rejected,
        "queued_pcm_frames": queued if valid else None,
        "played_pcm_frames": played if valid else None,
        "underruns": underruns if valid else None,
        "state": state,
        "fpga_build_id": build,
    }
