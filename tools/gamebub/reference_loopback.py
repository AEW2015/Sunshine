"""@brief Reproduce a continuous MSV1 test against the pinned host receiver on localhost.

This test does not contact an ESP32 or establish decode, display or Wi-Fi results.
"""

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import threading
import types
from pathlib import Path
from types import SimpleNamespace

import av

from host import clip_frames, looping_clip_frames
from msv1 import MAX_FRAME
from stream_sender import run

REVISION = "75f8497b6ffefadd8c0403728b93ccfbbfa02f52"
REFERENCE_SHA256 = "01a083f4794c7ced7e73eece60eac9d32cdacf589c6bc72b6c91c72e945cc9e5"
REFERENCE_PATH = "host/moonshine/protocol.py"


def load_reference(repository):
    """@brief Load the exact hash-checked receiver reference from a local Git repository.

    @param repository Path to a clone containing the pinned MoonBub revision.
    @return The verified Python receiver module.
    @throws ValueError If source bytes do not match the recorded hash.
    """
    data = subprocess.check_output(
        ["git", "-C", str(repository), "show", f"{REVISION}:{REFERENCE_PATH}"]
    )
    if hashlib.sha256(data).hexdigest() != REFERENCE_SHA256:
        raise ValueError("Receiver reference source hash mismatch")
    name = "gamebub_pinned_reference"
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(data, REFERENCE_PATH, "exec"), module.__dict__)  # noqa: S102 - pinned hash checked
    return module


class ReferencePeer:
    """@brief Loopback-only UDP harness around the receiver's pinned reassembler."""

    def __init__(self, reference):
        """@brief Bind an ephemeral localhost port and start the receiver thread."""
        self.reference = reference
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.settimeout(0.05)
        self.port = self.socket.getsockname()[1]
        self.stop = threading.Event()
        self.stats = {"complete": 0, "invalid_datagrams": 0, "reply_errors": 0}
        self.thread = threading.Thread(target=self._serve, name="moonbub-reference")
        self.thread.start()

    def _serve(self):
        """@brief Reassemble datagrams and acknowledge complete CRC-checked frames."""
        decoder = self.reference.Reassembler()
        while not self.stop.is_set():
            try:
                data, address = self.socket.recvfrom(2048)
            except TimeoutError:
                continue
            try:
                result = decoder.accept(data)
            except ValueError:
                self.stats["invalid_datagrams"] += 1
                continue
            if result is None:
                continue
            packet, _ = result
            self.stats["complete"] += 1
            feedback = self.reference.FEEDBACK.pack(
                b"MSF1",
                1,
                0,
                0,
                packet.frame_id,
                0,
                self.stats["complete"],
                self.stats["invalid_datagrams"],
                packet.capture_us,
            )
            try:
                self.socket.sendto(feedback, address)
            except OSError:
                self.stats["reply_errors"] += 1

    def close(self):
        """@brief Stop the loopback receiver and return its counters."""
        self.stop.set()
        self.thread.join()
        self.socket.close()
        return dict(self.stats)


def loop_clip(path, fps):
    """@brief Repeat a clip for a soak test without retaining decoded frames.

    @param path Source video path.
    @param fps Desired output timeline rate.
    @return Iterator of decoded frames; an empty clip terminates without spinning.
    """
    yield from looping_clip_frames(path, fps, clip_reader=clip_frames)


def run_reference(args, source=None):
    """@brief Run the sender against the pinned localhost peer.

    @param args Namespace containing repository, source, timing, and log options.
    @param source Optional image iterator used by tests instead of a clip.
    @return Sender summary and reference ingress counters.
    """
    reference = load_reference(args.reference_repo)
    peer = ReferencePeer(reference)
    if source is None and getattr(args, "loop", False):
        source = loop_clip(args.clip, args.fps)
    options = SimpleNamespace(
        target="127.0.0.1",
        port=peer.port,
        source_port=0,
        start_frame_id=0,
        log=args.log,
        clip=args.clip,
        desktop_backend=getattr(args, "desktop_backend", "imagegrab"),
        packet_timing=getattr(args, "packet_timing", False),
        fps=args.fps,
        mbps=args.mbps,
        max_age_ms=args.max_age_ms,
        quality=args.quality,
        min_quality=args.min_quality,
        max_jpeg_bytes=getattr(args, "max_jpeg_bytes", MAX_FRAME),
        jpeg_retry_quality_drop=getattr(args, "jpeg_retry_quality_drop", 0),
        frames=args.frames,
        pacing_wait=getattr(args, "pacing_wait", "sleep"),
        pacing_spin_us=getattr(args, "pacing_spin_us", 600),
    )
    try:
        sender = run(options, source)
    finally:
        received = peer.close()
    return {
        "reference_revision": REVISION,
        "reference_sha256": REFERENCE_SHA256,
        "receiver": received,
        "sender": sender,
        "hardware_playback_verified": False,
    }


def main(argv=None):
    """@brief Run an explicitly requested local reference benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--clip", type=Path)
    source.add_argument("--desktop", action="store_true")
    parser.add_argument("--desktop-backend", choices=("imagegrab", "ddagrab"), default="imagegrab")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument(
        "--packet-timing", action="store_true", help="Log each sent packet's timing"
    )
    parser.add_argument("--frames", type=int, default=900)
    parser.add_argument(
        "--loop", action="store_true", help="Repeat the clip until frame count is reached"
    )
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--pacing-wait", choices=("sleep", "precise", "hybrid"), default="sleep")
    parser.add_argument("--pacing-spin-us", type=int, default=600)
    parser.add_argument("--mbps", type=float, default=20)
    parser.add_argument("--max-age-ms", type=float, default=200)
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--min-quality", type=int, default=20)
    parser.add_argument(
        "--max-jpeg-bytes",
        type=int,
        default=MAX_FRAME,
        help="Maximum complete JPEG bytes; must match receiver capacity",
    )
    parser.add_argument(
        "--jpeg-retry-quality-drop",
        type=int,
        default=0,
        help="Retry an oversized JPEG once at lower quality; 0 disables",
    )
    args = parser.parse_args(argv)
    if (args.loop and not args.clip) or (args.desktop_backend != "imagegrab" and not args.desktop):
        parser.error("--loop requires --clip; --desktop-backend requires --desktop")
    if not 1 <= args.frames <= 108000:
        parser.error("Frame count must be 1..108000")
    if not 1 <= args.max_jpeg_bytes <= MAX_FRAME:
        parser.error(f"Maximum JPEG bytes must be 1..{MAX_FRAME}")
    if not 0 <= args.jpeg_retry_quality_drop <= 94:
        parser.error("JPEG retry quality drop must be 0..94")
    try:
        result = run_reference(args)
    except (OSError, ValueError, av.FFmpegError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0 if result["receiver"]["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
