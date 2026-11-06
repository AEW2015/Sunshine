"""@brief Finite Windows JPEG/AV v1 launcher, isolated from installed Sunshine.

All media and virtual input require explicit flags. --dry-run creates a manifest
without network, capture or virtual input. Stock Moonlight behavior is untouched.
"""

import argparse
import hashlib
import json
import math
import os
import site
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from capture_evidence import verify_stop
from capture_owner import CaptureOwner
from event_log import EventLog
from gamepad_backend import PROFILES
from live_session import run_av

HERE = Path(__file__).resolve().parent


def parser():
    """@brief Describe finite opt-in media modes and reproducible fixed video settings."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--receiver", required=True)
    result.add_argument("--bind", default="192.168.0.47")
    result.add_argument("--seconds", type=float, default=60)
    result.add_argument("--video", action="store_true")
    result.add_argument("--clip", type=Path, help="Use a saved clip instead of desktop capture")
    result.add_argument("--loop-clip", action="store_true")
    result.add_argument("--clip-selection", choices=("legacy", "native"), default="legacy")
    result.add_argument("--content-origin", choices=("center", "top-left"), default="center")
    result.add_argument("--audio", action="store_true")
    result.add_argument("--gamepad", action="store_true")
    result.add_argument(
        "--av-input",
        action="store_true",
        help="Keep input-only AV active without audio capture or virtual-gamepad injection",
    )
    result.add_argument("--profile", choices=PROFILES, default="standard")
    result.add_argument("--gain", type=float, default=0.75)
    result.add_argument("--fps", type=int, default=5)
    result.add_argument("--pacing-wait", choices=("sleep", "precise", "hybrid"), default="sleep")
    result.add_argument("--pacing-spin-us", type=int, default=600)
    result.add_argument("--capture-interface", help="Explicit dumpcap interface; capture is opt-in")
    result.add_argument("--capture-executable", default=r"C:\Program Files\Wireshark\dumpcap.exe")
    result.add_argument("--quality", type=int, default=25)
    result.add_argument("--mbps", type=float, default=2)
    result.add_argument("--deadline-ms", type=float, default=200)
    result.add_argument("--start-frame-id", type=int, required=True)
    result.add_argument("--video-port", type=int, default=5533)
    result.add_argument("--video-source-port", type=int, default=0)
    result.add_argument("--av-port", type=int, default=5534)
    result.add_argument("--av-source-port", type=int, default=0)
    result.add_argument(
        "--source-timeout",
        type=float,
        default=2,
        help="Report inactive audio callbacks after this interval; never invent PCM",
    )
    result.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory; existing evidence is never overwritten",
    )
    result.add_argument("--dry-run", action="store_true")
    return result


def validate(args):
    """@brief Reject invalid settings before directories, processes or traffic are created."""
    if not (args.video or args.audio or args.gamepad or args.av_input):
        raise ValueError("Select at least one of --video, --audio, --gamepad or --av-input")
    if args.clip is not None and not args.video:
        raise ValueError("--clip requires --video")
    if args.loop_clip and args.clip is None:
        raise ValueError("--loop-clip requires --clip")
    if args.clip_selection == "native" and args.clip is None:
        raise ValueError("--clip-selection native requires --clip")
    if getattr(args, "content_origin", "center") not in ("center", "top-left"):
        raise ValueError("Content origin must be center or top-left")
    if args.capture_interface and not (args.av_input or args.audio or args.gamepad):
        raise ValueError("Capture requires an AV owner so STOP can delimit coverage")
    if not 0 <= args.pacing_spin_us <= 1000 or (
        args.pacing_wait != "hybrid" and args.pacing_spin_us != 600
    ):
        raise ValueError("Hybrid spin tail must be0..1000us; nondefault requires hybrid mode")
    if any(
        not math.isfinite(v)
        for v in (args.seconds, args.gain, args.mbps, args.deadline_ms, args.source_timeout)
    ):
        raise ValueError("Settings must be finite")
    if not 0 < args.seconds <= 7200 or not 0 <= args.gain <= 1:
        raise ValueError("Duration must be within(0,7200], gain within[0,1]")
    if not 1 <= args.fps <= 30 or not 1 <= args.quality <= 95:
        raise ValueError("FPS must be1..30 and quality1..95")
    if args.mbps <= 0 or args.deadline_ms <= 0 or args.source_timeout <= 0:
        raise ValueError("Bitrate, deadline and source timeout must be positive")
    if not 0 <= args.start_frame_id <= 0xFFFFFFFF or math.ceil(args.seconds * args.fps) > 108000:
        raise ValueError("Frame ID or slot count out of bounds")
    if args.video and args.start_frame_id + math.ceil(args.seconds * args.fps) - 1 > 0xFFFFFFFF:
        raise ValueError("Requested video frame IDs would wrap; choose a fresh nonwrapping range")
    for port in (args.video_port, args.av_port):
        if not 1 <= port <= 65535:
            raise ValueError("Destination ports must be1..65535")
    for port in (args.video_source_port, args.av_source_port):
        if not 0 <= port <= 65535:
            raise ValueError("Source ports must be0..65535")
    if args.video and args.av_source_port and args.video_source_port == args.av_source_port:
        raise ValueError("AV and video require distinct source ports")


def video_command(args):
    """@brief Build a fixed-format child command with explicit source bind and wait.

    @param args Validated session options, including source, ports and pacing selection.
    @return Argument list for the separately owned video sender.
    """
    source = (
        ["--clip", str(args.clip), "--clip-selection", args.clip_selection]
        if args.clip
        else ["--desktop", "--desktop-backend", "ddagrab"]
    )
    if args.loop_clip:
        source.append("--loop-clip")
    return [
        getattr(sys, "_base_executable", sys.executable),
        "-u",
        str(HERE / "stream_sender.py"),
        args.receiver,
        "--bind",
        args.bind,
        *source,
        "--desktop-filter",
        "bilinear",
        "--frames",
        str(math.ceil(args.seconds * args.fps)),
        "--fps",
        str(args.fps),
        "--pacing-wait",
        args.pacing_wait,
        "--pacing-spin-us",
        str(args.pacing_spin_us),
        "--quality",
        str(args.quality),
        "--min-quality",
        str(args.quality),
        "--mbps",
        str(args.mbps),
        "--max-age-ms",
        str(args.deadline_ms),
        "--shift-right-px",
        "0",
        "--content-origin",
        getattr(args, "content_origin", "center"),
        "--start-frame-id",
        str(args.start_frame_id),
        "--port",
        str(args.video_port),
        "--source-port",
        str(args.video_source_port),
        "--packet-timing",
        "--log",
        str(args.output / "video.jsonl"),
    ]


class VideoProcess:
    """@brief Own exactly one sender child; bound wait/terminate/kill on session completion."""

    def __init__(self, args):
        """@brief Open new diagnostics before spawning an isolated video process."""
        self.process = None
        self.stdout = self.stderr = None
        environment = os.environ.copy()
        # Use the base interpreter directly on Windows, avoiding a venv redirector
        # process; explicit venv package paths retain the locked laboratory deps.
        environment["PYTHONPATH"] = os.pathsep.join([str(HERE), *site.getsitepackages()])
        try:
            self.stdout = (args.output / "video-summary.json").open("x", encoding="utf-8")
            self.stderr = (args.output / "video-stderr.txt").open("x", encoding="utf-8")
            self.process = subprocess.Popen(
                video_command(args),
                cwd=HERE,
                env=environment,
                stdout=self.stdout,
                stderr=self.stderr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except BaseException:
            for output in (self.stdout, self.stderr):
                if output is not None:
                    output.close()
            raise

    def close(self, grace=5):
        """@brief Return actual exit and forced-stop status; never stop an unrelated PID."""
        forced = False
        try:
            try:
                code = self.process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                forced = True
                self.process.terminate()
                try:
                    code = self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    code = self.process.wait(timeout=2)
            return {"exit_code": code, "forced_stop": forced}
        finally:
            self.stdout.close()
            self.stderr.close()


def verify_video_route(args):
    """@brief Verify the explicit video/AV source bind before opening evidence files.

    UDP connect selects a route without transmitting a datagram. It is skipped
    for dry runs. This guards ordinary static routes, not mid-session route changes.

    @param args Session options containing source bind, receiver and video port.
    @return Source IPv4 address reported by the bound, connected probe socket.
    @throws OSError If Windows cannot bind or connect the requested source.
    @throws ValueError If the reported source differs from the explicit bind.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind((args.bind, 0))
        probe.connect((args.receiver, args.video_port))
        source = probe.getsockname()[0]
    if source != args.bind:
        raise ValueError(f"Video route selects{source}, expected bind{args.bind}")
    return source


def run(args):
    """@brief Create a new evidence directory and run only the explicitly selected paths."""
    validate(args)
    clip_hash = None
    if args.clip is not None:
        args.clip = args.clip.resolve()
        with args.clip.open("rb") as source:
            clip_hash = hashlib.file_digest(source, "sha256").hexdigest()
    route = verify_video_route(args) if args.video and not args.dry_run else None
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {
        **vars(args),
        "output": str(args.output),
        "clip": str(args.clip.resolve()) if args.clip else None,
        "clip_sha256": clip_hash,
        "clip_start_offset_seconds": 0 if args.clip else None,
        "start_utc": datetime.now(UTC).isoformat(),
        "canvas": [720, 480],
        "active_16_9": [720, 405],
        "host_shift": 0,
        "content_origin": getattr(args, "content_origin", "center"),
        "video_route_preflight": route,
        "scope": "Host sends/ingress feedback; not verified decode/presentation/acoustics",
        "audio_bitrate_is_additional_to_video_cap": True,
        "source_hashes": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in (
                "session_launcher.py",
                "live_session.py",
                "live_audio.py",
                "audio_codec.py",
                "av_protocol.py",
                "av_session.py",
                "gamepad_backend.py",
                "stream_sender.py",
                "host.py",
                "msv1.py",
                "pipeline.py",
                "event_log.py",
                "pacing_wait.py",
                "capture_owner.py",
                "capture_evidence.py",
            )
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.dry_run:
        return {"dry_run": True, "video_command": video_command(args) if args.video else None}
    result, video, capture = {"end_to_end_verified": False}, None, None
    stop_wire = None
    with (args.output / "av.jsonl").open("x", encoding="utf-8") as output:
        log = EventLog(output)

        def event(kind, **fields):
            """@brief Submit bounded host events with one QPC clock domain."""
            nonlocal stop_wire
            log.submit({"event": kind, "monotonic_ns": time.perf_counter_ns(), **fields})
            if kind == "av_summary":
                result["av"] = fields
            if kind == "stop_sent" and capture is not None:
                stop_wire = bytes.fromhex(fields["wire_hex"])
                capture.record_stop()

        def ready():
            """@brief Start video only after AV ACTIVE, or directly in video-only mode."""
            nonlocal video
            if capture is not None:
                capture.health()
            if args.video:
                video = VideoProcess(args)
                event("video_started", pid=video.process.pid)

        def health():
            """@brief Abort AV promptly if its owned video sender fails."""
            if capture is not None:
                capture.health()
            if video is not None:
                code = video.process.poll()
                if code is not None and code != 0:
                    raise RuntimeError(f"Owned video sender exited with{code}")

        def video_finished():
            """@brief Keep AV active until the owned sender has closed its feedback/logs."""
            return video is not None and video.process.poll() == 0

        try:
            if args.capture_interface:
                import ipaddress

                source_ip = ipaddress.IPv4Address(args.bind)
                receiver_ip = ipaddress.IPv4Address(socket.gethostbyname(args.receiver))
                if source_ip.is_unspecified:
                    raise ValueError("Capture requires a concrete source IPv4 address")
                if (
                    not Path(args.capture_executable).is_file()
                    or not Path(args.capture_executable).with_name("tshark.exe").is_file()
                ):
                    raise FileNotFoundError(
                        "Capture requires installed dumpcap.exe and neighboring tshark.exe"
                    )
                capture = CaptureOwner(
                    args.output,
                    args.capture_interface,
                    f"udp and host {source_ip} and host {receiver_ip} and (port {args.video_port} or port {args.av_port})",
                    args.seconds + 120,
                    executable=args.capture_executable,
                )
                event("capture_started", **capture.start())
            av_active = args.audio or args.gamepad or args.av_input
            if av_active:
                # Bound capture startup and final feedback drain, while STOP follows
                # actual video completion rather than the nominal slot duration.
                av_args = (
                    argparse.Namespace(**{**vars(args), "seconds": args.seconds + 5})
                    if args.video
                    else args
                )
                result["av"] = run_av(
                    av_args,
                    event,
                    ready,
                    health=health,
                    stop_when=video_finished,
                )
                if video is not None and video.process.poll() is None:
                    raise TimeoutError("Owned video sender exceeded its finite AV grace")
            else:
                ready()
            if video is not None:
                result["video"] = video.close(grace=5 if av_active else args.seconds + 5)
                video = None
        except BaseException as error:
            result["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            if video is not None:
                try:
                    result["video"] = video.close(grace=0)
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    result["video"] = {"forced_stop": True, "cleanup_error": str(error)}
            result["media_end_utc"] = datetime.now(UTC).isoformat()
            if capture is not None and capture.process is not None:
                try:
                    result["capture"] = capture.close()
                    result["capture"]["complete"] = False
                    if result["capture"]["lifecycle_complete"] and stop_wire is not None:
                        verification = verify_stop(
                            capture.capture_path,
                            stop_wire,
                            args.bind,
                            tshark=Path(args.capture_executable).with_name("tshark.exe"),
                        )
                        result["capture"].update(verification)
                        result["capture"]["completion_scope"] = (
                            "Lifecycle and exact STOP verified at the capture point; RF delivery is unverified"
                        )
                        result["capture"]["complete"] = verification["stop_packet_verified"]
                except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                    result["capture"] = {
                        **result.get("capture", {}),
                        "complete": False,
                        "verification_error": str(error),
                    }
            result["logging"] = log.close()
            result["end_utc"] = datetime.now(UTC).isoformat()
            (args.output / "session-summary.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
    return result


def main(argv=None):
    """@brief Parse explicit finite media choices and return failure for incomplete shutdown."""
    cli = parser()
    args = cli.parse_args(argv)
    try:
        result = run(args)
    except (OSError, RuntimeError, ValueError, TimeoutError) as error:
        cli.exit(2, f"{error}\n")
    print(json.dumps(result, indent=2))
    worker = result.get("av", {}).get("audio_worker", {})
    return int(
        bool(
            result.get("video", {}).get("exit_code")
            or result.get("video", {}).get("forced_stop")
            or not worker.get("shutdown_complete", True)
            or worker.get("error")
            or result.get("av", {}).get("cleanup_errors")
            or result.get("av", {}).get("stop_error")
            or result.get("logging", {}).get("error")
            or result.get("logging", {}).get("dropped", 0)
            or ("capture" in result and not result["capture"].get("complete", False))
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
