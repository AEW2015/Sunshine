"""@brief MoonBub MSV1 video-only test transport; not a Sunshine codec mode.

The receiver's experimental protocol has no authentication or audio. Use only
with the intended test peer on a trusted LAN. No traffic is sent on import.
"""

import argparse
import json
import math
import socket
import struct
import time
import zlib
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from host import HEIGHT, WIDTH, inspect_jpeg

VIDEO = struct.Struct("!4sBBHIHHIIHHIQ")
FEEDBACK = struct.Struct("!4sBBHIIIIQ")
MAX_FRAME = 262144
MAX_PAYLOAD = 1024
STANDARD_HUFFMAN = "532fd667aa5541439e4fc89f189259b1b137993ca5dfcbb6970ab411aee79cdf"
EXPECTED_MARKERS = (0xE0, 0xDB, 0xDB, 0xC0, 0xC4, 0xC4, 0xC4, 0xC4, 0xDA)


def validate_receiver_jpeg(data: bytes) -> dict:
    """@brief Verify the conservative decoder profile before any network transmission.

    @param data Complete JPEG interchange frame.
    @return Parsed JPEG metadata for logging.
    @throws ValueError If JPEG size, marker layout or codec restrictions differ.
    """
    if not 0 < len(data) <= MAX_FRAME:
        raise ValueError("JPEG exceeds receiver frame bounds")
    metadata = inspect_jpeg(data)
    if (metadata["width"], metadata["height"]) != (WIDTH, HEIGHT):
        raise ValueError("Unsupported receiver dimensions")
    if (
        metadata["subsampling"] != "4:2:0"
        or metadata["restart_mcus"] != 0
        or metadata["huffman_sha256"] != STANDARD_HUFFMAN
    ):
        raise ValueError("Unsupported receiver JPEG profile")
    pos, markers = 2, []
    while True:
        marker = data[pos + 1]
        length = int.from_bytes(data[pos + 2 : pos + 4], "big")
        markers.append(marker)
        if marker == 0xE0 and data[pos + 4 : pos + 9] != b"JFIF\x00":
            raise ValueError("Expected JFIF APP0 marker")
        pos += 2 + length
        if marker == 0xDA:
            break
    if tuple(markers) != EXPECTED_MARKERS:
        raise ValueError("Unsupported JPEG marker order")
    with Image.open(BytesIO(data)) as image:
        image.load()
    return metadata


class ValidatedJpeg(bytes):
    """@brief Immutable JPEG validated once against the receiver's exact test profile.

    This is an internal correctness marker, not an authentication boundary.
    Construct it normally from ordinary bytes; do not bypass the constructor.
    """

    def __new__(cls, data):
        """@brief Validate complete immutable JPEG bytes before constructing the marker."""
        if type(data) is not bytes:
            raise ValueError("Expected immutable JPEG bytes")
        validate_receiver_jpeg(data)
        return super().__new__(cls, data)


def encode_receiver_jpeg(image, quality):
    """@brief Encode and validate one exact receiver-profile JPEG.

    @param image RGB 720x480 source canvas.
    @param quality JPEG quality from 1 to 95.
    @return Immutable validated JPEG, ready for MSV1 packetization.
    @throws ValueError If image, quality or actual JPEG format is unsupported.
    """
    if (
        not isinstance(image, Image.Image)
        or image.mode != "RGB"
        or image.size != (WIDTH, HEIGHT)
        or type(quality) is not int
        or not 1 <= quality <= 95
    ):
        raise ValueError("Expected RGB 720x480 and JPEG quality 1..95")
    output = BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=quality,
        subsampling="4:2:0",
        optimize=False,
        progressive=False,
        restart_marker_blocks=0,
    )
    return ValidatedJpeg(output.getvalue())


def frame_datagrams(jpeg: bytes, frame_id: int, capture_us: int, payload_size: int = MAX_PAYLOAD):
    """@brief Yield a validated complete frame as sequential MSV1 UDP datagrams.

    @param jpeg Baseline JPEG satisfying the receiver profile.
    @param frame_id Unsigned 32-bit frame identifier; callers handle wrapping.
    @param capture_us Unsigned Unix capture timestamp in microseconds.
    @param payload_size Maximum bytes per chunk, at most 1024.
    @return Iterator of network-order datagrams; no fixture length prefix is sent.
    """
    if (
        type(frame_id) is not int
        or not 0 <= frame_id <= 0xFFFFFFFF
        or type(capture_us) is not int
        or not 0 <= capture_us <= 0xFFFFFFFFFFFFFFFF
        or type(payload_size) is not int
        or not 1 <= payload_size <= MAX_PAYLOAD
    ):
        raise ValueError("Invalid MSV1 identifier, timestamp or payload size")
    if type(jpeg) is not ValidatedJpeg:
        validate_receiver_jpeg(jpeg)
    crc = zlib.crc32(jpeg)
    for offset in range(0, len(jpeg), payload_size):
        payload = jpeg[offset : offset + payload_size]
        flags = (1 if offset == 0 else 0) | (2 if offset + len(payload) == len(jpeg) else 0)
        yield (
            VIDEO.pack(
                b"MSV1",
                1,
                1,
                flags,
                frame_id,
                WIDTH,
                HEIGHT,
                len(jpeg),
                offset,
                len(payload),
                0,
                crc,
                capture_us,
            )
            + payload
        )


@dataclass(frozen=True)
class Feedback:
    """@brief Receiver ingress feedback; it does not establish display or authentication."""

    status: int
    buttons: int
    frame_id: int
    free_bytes: int
    received_frames: int
    dropped_frames: int
    capture_us: int


@dataclass
class Pacer:
    """@brief Preserve the next transmission time across consecutive frames."""

    next_due: float | None = None


def parse_feedback(data: bytes) -> Feedback:
    """@brief Parse a complete MSF1 feedback packet from the already connected peer.

    @param data Received feedback datagram.
    @return Parsed feedback; free bytes are advisory rather than FIFO credits.
    @throws ValueError For wrong length, version, magic or status.
    """
    if len(data) != FEEDBACK.size:
        raise ValueError("Invalid MSF1 feedback length")
    magic, version, status, buttons, frame, free, received, dropped, stamp = FEEDBACK.unpack(data)
    if magic != b"MSF1" or version != 1 or status > 3:
        raise ValueError("Unsupported MSF1 feedback")
    return Feedback(status, buttons, frame, free, received, dropped, stamp)


def gamebub_buttons(mask: int) -> frozenset[str]:
    """@brief Translate the receiver's FPGA button bits into local logical names.

    @param mask Unsigned 16-bit MSF1 button field with reserved bits clear.
    @return Active gameplay button names; no Windows input is injected.
    @throws ValueError If reserved bits are set or the field is invalid.
    """
    if type(mask) is not int or mask < 0 or mask & ~0xFFF:
        raise ValueError("Invalid Game Bub button mask")
    names = ("select", "start", "r", "l", "right", "left", "down", "up", "y", "x", "b", "a")
    return frozenset(name for bit, name in enumerate(names) if mask & (1 << bit))


def send_frame(
    sock,
    jpeg,
    frame_id,
    capture_us,
    bytes_per_second,
    deadline,
    clock=time.perf_counter,
    sleeper=time.sleep,
    pacer=None,
):
    """@brief Pace one frame on a connected datagram socket, aborting when stale.

    @param sock Connected UDP socket; authentication is outside this test protocol.
    @param jpeg Complete receiver-compatible JPEG.
    @param frame_id Unsigned wrapping frame ID.
    @param capture_us Host Unix capture timestamp in microseconds.
    @param bytes_per_second Positive finite rate including MSV1 headers.
    @param deadline Absolute host monotonic deadline for this frame.
    @param clock Injectable monotonic seconds clock.
    @param sleeper Injectable wait function.
    @param pacer Optional sender-owned Pacer shared across consecutive frames.
    @return Pair of (completed, bytes sent); incomplete frames recover on newer SOF.
    """
    if not math.isfinite(bytes_per_second) or bytes_per_second <= 0 or not math.isfinite(deadline):
        raise ValueError("Rate and deadline must be finite; rate must be positive")
    next_due, sent = pacer.next_due if pacer is not None else None, 0
    for packet in frame_datagrams(jpeg, frame_id, capture_us):
        now = clock()
        due = max(next_due, now) if next_due is not None else now
        duration = len(packet) / bytes_per_second
        if due + duration > deadline:
            return False, sent
        delay = due - now
        if delay > 0:
            sleeper(delay)
        now = clock()
        if now + duration > deadline:
            return False, sent
        count = sock.send(packet)
        if count != len(packet):
            raise OSError("Partial UDP datagram send")
        sent += count
        next_due = now + duration
        if pacer is not None:
            pacer.next_due = next_due
    return True, sent


def main(argv=None):
    """@brief Send one fixture and report ingress feedback, without claiming playback.

    @param argv Optional command-line arguments for a trusted test receiver.
    @return Zero when matching ingress feedback is received; two otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Test receiver address on a trusted LAN")
    parser.add_argument("--jpeg", required=True, type=Path)
    parser.add_argument("--port", type=int, default=5533)
    parser.add_argument("--mbps", type=float, default=20)
    parser.add_argument("--frame-id", type=int, default=1)
    parser.add_argument("--deadline-ms", type=float, default=200)
    parser.add_argument("--feedback-timeout", type=float, default=1)
    args = parser.parse_args(argv)
    if (
        not 1 <= args.port <= 65535
        or not 0 <= args.frame_id <= 0xFFFFFFFF
        or any(
            not math.isfinite(n) or n <= 0
            for n in (args.mbps, args.deadline_ms, args.feedback_timeout)
        )
    ):
        parser.error("Invalid port, frame ID, rate, deadline or feedback timeout")
    try:
        jpeg = args.jpeg.read_bytes()
        capture_us = time.time_ns() // 1000
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((args.target, args.port))
            sock.setblocking(False)
            done, size = send_frame(
                sock,
                jpeg,
                args.frame_id,
                capture_us,
                args.mbps * 1e6 / 8,
                time.perf_counter() + args.deadline_ms / 1000,
            )
            feedback = None
            if done:
                until = time.perf_counter() + args.feedback_timeout
                while time.perf_counter() < until:
                    sock.settimeout(max(0.001, until - time.perf_counter()))
                    try:
                        value = parse_feedback(sock.recv(FEEDBACK.size + 1))
                    except TimeoutError:
                        break
                    if value.frame_id == args.frame_id and value.capture_us == capture_us:
                        feedback = value
                        break
        result = {
            "sent_complete": done,
            "msv1_bytes": size,
            "feedback": asdict(feedback) if feedback else None,
            "end_to_end_verified": False,
            "scope": "single test frame; ingress only",
        }
        print(json.dumps(result, indent=2))
        return 0 if feedback is not None and feedback.status == 0 else 2
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
