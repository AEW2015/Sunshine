"""@brief Offline capture, baseline JPEG validation, and bounded-link experiments.

No network transport is selected here. File output and a simulated serial link
allow host work before the FPGA agent agrees to a codec and wire protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import struct
import time
import zlib
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

import av
from av.video.reformatter import Interpolation
from PIL import Image, ImageDraw, ImageGrab, features

WIDTH, HEIGHT = 720, 480
CONTENT_HEIGHT = 405


@dataclass(frozen=True)
class Profile:
    """@brief Local encoder experiment settings; this is not a negotiated protocol."""

    subsampling: str = "4:2:0"
    restart_mcus: int = 0
    max_frame_bytes: int = 262144
    huffman_sha256: str | None = None

    def __post_init__(self):
        """@brief Reject settings that the baseline laboratory cannot represent."""
        if type(self.restart_mcus) is not int or type(self.max_frame_bytes) is not int:
            raise ValueError("Restart interval and frame bound must be integers")
        if self.subsampling not in ("4:4:4", "4:2:2", "4:2:0"):
            raise ValueError("Unsupported chroma subsampling")
        if not 0 <= self.restart_mcus <= 65535 or not 1 <= self.max_frame_bytes <= 16777216:
            raise ValueError("Invalid restart interval or frame bound")
        if self.huffman_sha256 is not None and (
            not isinstance(self.huffman_sha256, str)
            or len(self.huffman_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.huffman_sha256)
        ):
            raise ValueError("Huffman digest must be lowercase SHA-256")


def canvas(
    image: Image.Image | av.VideoFrame, resampling: Image.Resampling = Image.Resampling.LANCZOS
) -> Image.Image:
    """@brief Fit a source without distortion inside a centered 720x405 viewport.

    @param image Source RGB-compatible image with square pixels.
    @param resampling Pillow resize filter for image sources; video uses bilinear libswscale.
    @return A 720x480 RGB canvas; 16:9 input has 37 top and 38 bottom black rows.
    """
    scale = min(WIDTH / image.width, CONTENT_HEIGHT / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    if isinstance(image, av.VideoFrame):
        # Scale only the selected decoded frame, before allocating a full-size RGB image.
        image = image.reformat(
            width=size[0], height=size[1], format="rgb24", interpolation=Interpolation.BILINEAR
        ).to_image()
    else:
        image = image.convert("RGB").resize(size, resampling)
    result = Image.new("RGB", (WIDTH, HEIGHT))
    result.paste(
        image,
        ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2),
    )
    return result


def shift_canvas_right(image: Image.Image, pixels: int) -> Image.Image:
    """@brief Translate a prepared canvas right, filling left with black and cropping right.

    This moves pixels inside the encoded frame; it does not move the receiver's
    panel viewport or change dimensions, aspect ratio or the JPEG profile.

    @param image Prepared RGB 720x480 canvas; never mutated or retained.
    @param pixels Rightward translation in whole pixels, from 0 to 719.
    @return A new owned RGB 720x480 image, including for a zero-pixel shift.
    @throws ValueError If the canvas or shift is outside the supported bounds.
    """
    if (
        not isinstance(image, Image.Image)
        or image.mode != "RGB"
        or image.size != (WIDTH, HEIGHT)
        or type(pixels) is not int
        or not 0 <= pixels < WIDTH
    ):
        raise ValueError("Expected RGB 720x480 canvas and right shift 0..719")
    result = Image.new("RGB", (WIDTH, HEIGHT))
    result.paste(image, (pixels, 0))
    return result


@cache
def pattern_indices() -> Image.Image:
    """@brief Cache indexed fine-detail pixels so fixture rendering does not dominate timing.

    @return Immutable-by-convention palette image; callers must copy before editing.
    """
    image = Image.new("P", (1280, 720))
    draw = ImageDraw.Draw(image)
    for y in range(360, 720, 8):
        for x in range(0, 1280, 8):
            value = ((x // 8) * 73 + (y // 8) * 151) & 255
            draw.rectangle((x, y, x + 7, y + 7), fill=value)
    return image


def pattern(frame_id: int) -> Image.Image:
    """@brief Generate deterministic moving RGB bars, fine detail, and an ID patch.

    @param frame_id Nonnegative sequence number; its low 32 bits appear as a patch.
    @return A square-pixel 1280x720 RGB test image, before letterboxing.
    """
    indices = pattern_indices().copy()
    palette = []
    for index in range(256):
        value = (index + frame_id * 17) & 255
        palette.extend((value, (value * 3) & 255, (value * 7) & 255))
    indices.putpalette(palette)
    image = indices.convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = ("white", "yellow", "cyan", "green", "magenta", "red", "blue", "black")
    for i, color in enumerate(colors):
        draw.rectangle((i * 160, 0, (i + 1) * 160 - 1, 359), fill=color)
    x = (frame_id * 13) % 1184
    draw.rectangle((x, 240, x + 95, 335), fill="white", outline="black", width=4)
    for bit in range(32):
        draw.rectangle(
            (bit * 20, 680, bit * 20 + 19, 719), fill="white" if frame_id & (1 << bit) else "black"
        )
    return image


def inspect_jpeg(data: bytes) -> dict:
    """@brief Parse actual baseline JPEG syntax and summarize decoder restrictions.

    @param data Complete JPEG interchange image, including SOI and EOI.
    @return Dimensions, component sampling, table digest, and restart information.
    @throws ValueError For truncation, nonbaseline coding, or unsupported scan syntax.
    """
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Missing JPEG SOI")
    pos, sof, sos, dri = 2, None, None, 0
    tables = {}
    quantizers = set()
    while pos < len(data):
        if data[pos] != 255 or pos + 1 >= len(data):
            raise ValueError("Invalid JPEG marker")
        marker = data[pos + 1]
        pos += 2
        if pos + 2 > len(data):
            raise ValueError("Truncated marker length")
        length = int.from_bytes(data[pos : pos + 2], "big")
        if length < 2 or pos + length > len(data):
            raise ValueError("Truncated marker payload")
        payload = data[pos + 2 : pos + length]
        pos += length
        if marker == 0xC0:
            if sof is not None or len(payload) != 15 or payload[0] != 8 or payload[5] != 3:
                raise ValueError("Expected one 8-bit, three-component SOF0")
            sof = payload
        elif marker == 0xC4:
            offset = 0
            while offset < len(payload):
                if offset + 17 > len(payload):
                    raise ValueError("Truncated Huffman table")
                key = payload[offset]
                end = offset + 17 + sum(payload[offset + 1 : offset + 17])
                if key not in (0, 1, 16, 17) or key in tables or end > len(payload):
                    raise ValueError("Invalid or duplicate Huffman table")
                tables[key] = payload[offset:end]
                offset = end
        elif marker == 0xDB:
            offset = 0
            while offset < len(payload):
                key = payload[offset]
                if key not in (0, 1) or key in quantizers or offset + 65 > len(payload):
                    raise ValueError("Expected unique 8-bit quantization tables 0/1")
                quantizers.add(key)
                offset += 65
        elif marker == 0xDD:
            if len(payload) != 2 or dri:
                raise ValueError("Invalid restart interval")
            dri = int.from_bytes(payload, "big")
        elif marker == 0xDA:
            sos = payload
            break
        elif not (0xE0 <= marker <= 0xEF or marker == 0xFE):
            raise ValueError("Only baseline sequential JPEG is accepted")
    if sof is None or sos != bytes((3, 1, 0, 2, 17, 3, 17, 0, 63, 0)):
        raise ValueError("Expected a single interleaved baseline YCbCr scan")
    if set(tables) != {0, 1, 16, 17} or quantizers != {0, 1}:
        raise ValueError("Missing Huffman or quantization tables")
    precision, height, width, count = struct.unpack(">BHHB", sof[:6])
    components = [list(sof[i : i + 3]) for i in range(6, 15, 3)]
    expected = {0x11: "4:4:4", 0x21: "4:2:2", 0x22: "4:2:0"}
    if (
        components[0][0] != 1
        or components[0][2] != 0
        or components[0][1] not in expected
        or components[1:] != [[2, 17, 1], [3, 17, 1]]
        or not width
        or not height
    ):
        raise ValueError("Unsupported YCbCr component layout")
    restarts = []
    while pos < len(data):
        # Ordinary entropy bytes cannot be markers; search for the next prefix in C.
        pos = data.find(b"\xff", pos)
        if pos < 0:
            raise ValueError("Missing JPEG EOI")
        pos += 1
        if pos >= len(data):
            raise ValueError("Truncated entropy marker")
        marker = data[pos]
        pos += 1
        if marker == 0:
            continue
        if 0xD0 <= marker <= 0xD7:
            if not dri or marker != 0xD0 + len(restarts) % 8:
                raise ValueError("Unexpected restart marker sequence")
            restarts.append(marker)
        elif marker == 0xD9 and pos == len(data):
            break
        else:
            raise ValueError("Unexpected marker in entropy stream or trailing data")
    else:
        raise ValueError("Missing JPEG EOI")
    sampling = components[0][1]
    mcus = math.ceil(width / (8 * (sampling >> 4))) * math.ceil(height / (8 * (sampling & 15)))
    if len(restarts) != ((mcus - 1) // dri if dri else 0):
        raise ValueError("Restart count does not match MCU geometry")
    return {
        "width": width,
        "height": height,
        "precision": precision,
        "components": count,
        "subsampling": expected[sampling],
        "restart_mcus": dri,
        "restart_count": len(restarts),
        "huffman_sha256": hashlib.sha256(b"".join(tables[k] for k in sorted(tables))).hexdigest(),
    }


def encode(image: Image.Image, quality: int, profile: Profile) -> tuple[bytes, dict]:
    """@brief Encode and inspect every JPEG rather than trusting encoder options.

    @param image Letterboxed RGB canvas.
    @param quality JPEG quantizer quality, 1 through 95; not a perceptual score.
    @param profile Local experiment constraints, pending FPGA agreement.
    @return JPEG bytes and parsed metadata; oversize frames are rejected.
    """
    if not 1 <= quality <= 95 or image.size != (WIDTH, HEIGHT):
        raise ValueError("Expected quality 1..95 and a 720x480 canvas")
    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=quality,
        subsampling=profile.subsampling,
        optimize=False,
        progressive=False,
        restart_marker_blocks=profile.restart_mcus,
    )
    data = output.getvalue()
    metadata = inspect_jpeg(data)
    if (
        metadata["subsampling"] != profile.subsampling
        or metadata["restart_mcus"] != profile.restart_mcus
    ):
        raise ValueError("Encoder did not honor sampling or restart restrictions")
    if profile.huffman_sha256 is not None and metadata["huffman_sha256"] != profile.huffman_sha256:
        raise ValueError("Huffman tables differ from receiver reference")
    if len(data) > profile.max_frame_bytes:
        raise OverflowError("JPEG exceeds frame-size bound")
    # Also exercise the entropy decoder; header inspection alone is insufficient.
    with Image.open(io.BytesIO(data)) as decoded:
        decoded.load()
    return data, metadata


def clip_frames(path: Path, fps: int) -> Iterator[av.VideoFrame]:
    """@brief Resample a clip using presentation timestamps, with bounded lookahead.

    @param path Video input with monotonic presentation timestamps and square pixels.
    @param fps Desired timeline sample rate, at most 30 during initial testing.
    @return Decoded frames; conversion waits until selection so stale samples are cheap.
    """
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        if stream.sample_aspect_ratio not in (None, 1):
            raise ValueError("Normalize nonsquare pixels before this experiment")
        current, origin, tick, previous = None, None, 0, -math.inf
        for frame in container.decode(stream):
            if frame.time is None or frame.time <= previous:
                raise ValueError("Clip requires strictly increasing presentation timestamps")
            previous = frame.time
            if origin is None:
                origin = frame.time
            timestamp = frame.time - origin
            while current is not None and tick / fps < timestamp:
                yield current
                tick += 1
            current = frame
        if current is not None:
            last_duration = (
                current.duration * float(current.time_base)
                if current.duration
                else 1 / float(stream.average_rate or fps)
            )
            while tick / fps < previous - origin + last_duration:
                yield current
                tick += 1


def looping_clip_frames(path, fps, *, clip_reader=clip_frames):
    """@brief Reopen a saved clip without retaining decoded frames or spinning on empty input.

    @param path Source clip path.
    @param fps Desired resampled timeline rate.
    @param clip_reader Injectable finite clip iterator factory.
    @return Repeated decoded frames; closing releases the active reader.
    """
    while True:
        frames = clip_reader(path, fps)
        emitted = False
        try:
            for frame in frames:
                emitted = True
                yield frame
        finally:
            frames.close()
        if not emitted:
            return


@dataclass
class LinkModel:
    """@brief Zero-queue simulated link; never a receiver or Wi-Fi measurement."""

    bitrate: float
    max_age: float
    next_free: float = 0.0

    def reserve(self, size: int, captured: float, now: float) -> float | None:
        """@brief Reserve serialization time only when the entire frame meets its age bound.

        @param size Encoded byte count; simulated overhead is zero.
        @param captured Host monotonic capture start in seconds.
        @param now Current host monotonic time in seconds.
        @return Completion time or None when stale; a rejected frame consumes no capacity.
        """
        finish = max(self.next_free, now) + size * 8 / self.bitrate
        if finish - captured > self.max_age:
            return None
        self.next_free = finish
        return finish


def run(args) -> dict:
    """@brief Run a paced file-sink experiment and emit per-attempt JSONL plus a summary.

    @param args Validated command-line namespace.
    @return Host-only measurements, explicitly excluding receiver and display latency.
    """
    profile = Profile(**json.loads(args.profile.read_text()) if args.profile else {})
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "frames.jsonl").exists() or (args.output / "summary.json").exists():
        raise ValueError("Use a fresh output directory to preserve earlier measurements")
    frames = clip_frames(args.clip, args.fps) if args.clip else None
    link = LinkModel(args.link_mbps * 1e6, args.max_age_ms / 1000)
    quality, counts, sizes, ages, encode_times, quality_counts = (
        args.quality,
        Counter(),
        [],
        [],
        [],
        Counter(),
    )
    start, slot, encoded_total, completed_total = time.perf_counter(), 0, 0, 0
    with (args.output / "frames.jsonl").open("w", encoding="utf-8") as log:
        while slot < args.frames:
            due = start + slot / args.fps
            time.sleep(max(0, due - time.perf_counter()))
            captured = time.perf_counter()
            elapsed_slot = min(args.frames - 1, int((captured - start) * args.fps))
            skipped = max(0, elapsed_slot - slot)
            counts["skipped_slots"] += skipped
            slot += skipped
            row = {
                "frame_id": slot,
                "capture_us": round((captured - start) * 1e6),
                "quality": quality,
                "skipped_slots": skipped,
            }
            try:
                if frames is not None:
                    # Skip stale clip samples; never accumulate a decoded-frame queue.
                    for _ in range(skipped + 1):
                        image = next(frames)
                else:
                    image = ImageGrab.grab() if args.desktop else pattern(slot)
                prepared = (
                    canvas(image, Image.Resampling[args.desktop_filter.upper()])
                    if args.desktop
                    else canvas(image)
                )
                encoding_start = time.perf_counter()
                data, metadata = encode(prepared, quality, profile)
                encoded = time.perf_counter()
                encoding_ms = (encoded - encoding_start) * 1000
                encode_times.append(encoding_ms)
                sizes.append(len(data))
                encoded_total += len(data)
                quality_counts[quality] += 1
                row.update(
                    bytes=len(data),
                    crc32=f"{zlib.crc32(data):08x}",
                    encode_ms=encoding_ms,
                    capture_and_scale_ms=(encoding_start - captured) * 1000,
                    jpeg=metadata,
                )
                finish = link.reserve(len(data), captured, encoded)
                if finish is None:
                    counts["stale"] += 1
                    row["status"] = "stale"
                    quality = max(args.min_quality, quality - 5)
                else:
                    # One in-flight simulated frame. Disk output is outside the link model.
                    time.sleep(max(0, finish - time.perf_counter()))
                    age_ms = (time.perf_counter() - captured) * 1000
                    ages.append(age_ms)
                    row.update(
                        status="simulated_complete",
                        queue_age_ms=0,
                        frame_age_ms=age_ms,
                        queue_depth=0,
                        simulated_latency_ms=(finish - captured) * 1000,
                    )
                    if args.save_jpeg:
                        (args.output / f"{slot:08d}.jpg").write_bytes(data)
                    counts["simulated_complete"] += 1
                    completed_total += len(data)
                    budget = args.link_mbps * 1e6 / (8 * args.fps)
                    if len(data) > budget or age_ms > args.max_age_ms * 0.8:
                        quality = max(args.min_quality, quality - 5)
                    elif len(data) < budget * 0.7:
                        quality = min(args.quality, quality + 1)
            except StopIteration:
                counts["eof"] += 1
                break
            except (OSError, ValueError, OverflowError, av.FFmpegError) as error:
                row.update(status="failure", error=f"{type(error).__name__}: {error}")
                counts["failures"] += 1
                quality = max(args.min_quality, quality - 5)
            row.update(
                elapsed_s=time.perf_counter() - start,
                encoded_frames=len(sizes),
                encoded_total_bytes=encoded_total,
                simulated_complete_frames=counts["simulated_complete"],
                simulated_complete_bytes=completed_total,
            )
            log.write(json.dumps(row) + "\n")
            log.flush()
            slot += 1
    if frames is not None:
        frames.close()
    duration = time.perf_counter() - start
    summary = {
        "measurement": "host_encoding_and_zero_overhead_link_simulation",
        "end_to_end_verified": False,
        "resolution": [WIDTH, HEIGHT],
        "content_viewport": [0, 37, WIDTH, CONTENT_HEIGHT],
        "target_fps": args.fps,
        "duration_s": duration,
        "source": str(args.clip)
        if args.clip
        else ("desktop" if args.desktop else "synthetic_not_game_footage"),
        "desktop_filter": args.desktop_filter if args.desktop else None,
        "profile": asdict(profile),
        "counts": dict(counts),
        "encoded_fps": len(sizes) / duration,
        "simulated_complete_fps": counts["simulated_complete"] / duration,
        "encoded_mbps": encoded_total * 8 / duration / 1e6,
        "simulated_complete_mbps": completed_total * 8 / duration / 1e6,
        "encoded_bytes": {
            "mean": encoded_total / len(sizes) if sizes else 0,
            "max": max(sizes, default=0),
        },
        "encode_ms": distribution(encode_times),
        "host_age_ms": distribution(ages),
        "quality_histogram": dict(quality_counts),
        "configured_link_mbps": args.link_mbps,
        "queue_capacity_frames": 0,
        "receiver_latency_ms": None,
        "versions": {
            "pyav": av.__version__,
            "pillow": Image.__version__,
            "libjpeg_turbo": features.version_feature("libjpeg_turbo"),
        },
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def distribution(values: list[float]) -> dict:
    """@brief Compute nearest-rank median, p95, and maximum; empty input produces nulls.

    @param values Measured host durations in milliseconds.
    @return Sample count and duration quantiles.
    """
    ordered = sorted(values)
    return {
        "count": len(values),
        **{
            name: ordered[max(0, math.ceil(p * len(values)) - 1)] if values else None
            for name, p in (("p50", 0.5), ("p95", 0.95), ("max", 1))
        },
    }


def main(argv=None) -> int:
    """@brief Parse bounded experiment arguments; return nonzero on any frame failures.

    @param argv Optional command-line argument list.
    @return Zero for a successful host experiment, two for frame failures.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--clip", type=Path)
    source.add_argument("--desktop", action="store_true")
    parser.add_argument(
        "--desktop-filter", choices=("lanczos", "bicubic", "bilinear"), default="lanczos"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--min-quality", type=int, default=20)
    parser.add_argument("--link-mbps", type=float, default=20)
    parser.add_argument("--max-age-ms", type=float, default=66.7)
    parser.add_argument("--save-jpeg", action="store_true")
    args = parser.parse_args(argv)
    if (
        not 1 <= args.frames <= 108000
        or not 1 <= args.fps <= 30
        or not 1 <= args.min_quality <= args.quality <= 95
        or not math.isfinite(args.link_mbps)
        or args.link_mbps <= 0
        or not math.isfinite(args.max_age_ms)
        or args.max_age_ms <= 0
    ):
        parser.error(
            "Require frames 1..108000, fps 1..30, quality 1..95, and finite positive limits"
        )
    try:
        summary = run(args)
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(summary, indent=2))
    return 2 if summary["counts"].get("failures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
