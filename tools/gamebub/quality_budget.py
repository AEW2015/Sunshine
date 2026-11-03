"""@brief Offline JPEG quality and MSV1 bandwidth study; no network or playback."""

import argparse
import hashlib
import io
import json
import math
import statistics
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from host import CONTENT_HEIGHT, HEIGHT, WIDTH, canvas, clip_frames
from msv1 import MAX_PAYLOAD, VIDEO, encode_receiver_jpeg


def viewport(width, height):
    """@brief Compute the content rectangle used for a square-pixel source.

    @param width Source width in pixels.
    @param height Source height in pixels.
    @return Pillow crop bounds within the 720x480 canvas.
    """
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("Source dimensions must be positive integers")
    scale = min(WIDTH / width, CONTENT_HEIGHT / height)
    out_w, out_h = max(1, round(width * scale)), max(1, round(height * scale))
    left, top = (WIDTH - out_w) // 2, (HEIGHT - out_h) // 2
    return left, top, left + out_w, top + out_h


def psnr(original, decoded, bounds):
    """@brief Calculate RGB PSNR inside the content rectangle, excluding black bars.

    @param original RGB source canvas before JPEG encoding.
    @param decoded RGB canvas decoded from JPEG.
    @param bounds Content crop rectangle.
    @return PSNR in dB, or None for identical pixels. This is not a perceptual score.
    """
    diff = ImageChops.difference(original.crop(bounds), decoded.crop(bounds))
    rms = ImageStat.Stat(diff).rms
    mse = sum(value * value for value in rms) / 3
    return 10 * math.log10(255 * 255 / mse) if mse else None


def summarize(values):
    """@brief Return mean, median, nearest-rank p95 and maximum for nonempty data."""
    if not values:
        raise ValueError("At least one value is required")
    ordered = sorted(values)
    return {
        "mean": statistics.mean(ordered),
        "p50": statistics.median(ordered),
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "max": ordered[-1],
    }


def run(path, output, samples=300, skip=300, fps=30, qualities=(20, 35, 50, 65, 75), frames=None):
    """@brief Compare actual encoded frame sizes and quality on identical source frames.

    @param path Source clip, used for provenance and default frame decoding.
    @param output New JSON output path; existing results are never overwritten.
    @param samples Maximum number of frames to analyze.
    @param skip Number of timeline samples to skip before measuring.
    @param fps Target frame rate used for timeline sampling and bitrate calculation.
    @param qualities JPEG quality values to compare.
    @param frames Optional decoded-frame iterator for tests.
    @return Machine-readable host-only results; no network or playback is measured.
    """
    if (
        type(samples) is not int
        or not 1 <= samples <= 9000
        or type(skip) is not int
        or not 0 <= skip <= 108000
        or type(fps) is not int
        or not 1 <= fps <= 30
        or not qualities
        or len(set(qualities)) != len(qualities)
        or any(type(q) is not int or not 1 <= q <= 95 for q in qualities)
    ):
        raise ValueError("Invalid sampling or JPEG quality options")
    source_hash = None
    if frames is None:
        with path.open("rb") as source:
            source_hash = hashlib.file_digest(source, "sha256").hexdigest()
    frames = clip_frames(path, fps) if frames is None else frames
    counts = {q: {"jpeg": [], "wire": [], "psnr": []} for q in qualities}
    started = time.perf_counter()
    sampled = 0
    try:
        for _ in range(skip):
            next(frames)
        for _ in range(samples):
            frame = next(frames)
            bounds = viewport(frame.width, frame.height)
            original = canvas(frame)
            for quality in qualities:
                jpeg = encode_receiver_jpeg(original, quality)
                wire = len(jpeg) + math.ceil(len(jpeg) / MAX_PAYLOAD) * VIDEO.size
                with Image.open(io.BytesIO(jpeg)) as decoded:
                    decoded.load()
                    score = psnr(original, decoded.convert("RGB"), bounds)
                counts[quality]["jpeg"].append(len(jpeg))
                counts[quality]["wire"].append(wire)
                if score is not None:
                    counts[quality]["psnr"].append(score)
            sampled += 1
    except StopIteration:
        pass
    finally:
        if hasattr(frames, "close"):
            frames.close()
    if sampled == 0:
        raise ValueError("No source frames available after skip")
    result = {
        "scope": "offline host JPEG comparison; no network or playback",
        "source_sha256": source_hash,
        "samples": sampled,
        "requested_samples": samples,
        "source_exhausted": sampled < samples,
        "skip": skip,
        "target_fps": fps,
        "resolution": [WIDTH, HEIGHT],
        "elapsed_s": time.perf_counter() - started,
        "end_to_end_verified": False,
        "qualities": {},
    }
    for quality, values in counts.items():
        jpeg_stats, wire_stats = summarize(values["jpeg"]), summarize(values["wire"])
        scores = values["psnr"]
        result["qualities"][str(quality)] = {
            "jpeg_bytes": jpeg_stats,
            "msv1_bytes": wire_stats,
            "mean_msv1_mbps_at_target": wire_stats["mean"] * fps * 8 / 1e6,
            "p95_frame_msv1_mbps_at_target": wire_stats["p95"] * fps * 8 / 1e6,
            "rgb_content_psnr_db": summarize(scores) if scores else None,
            "identical_frames": sampled - len(scores),
        }
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    return result


def main(argv=None):
    """@brief Run the offline comparison without contacting a receiver."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--skip", type=int, default=300)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--qualities", type=int, nargs="+", default=(20, 35, 50, 65, 75))
    args = parser.parse_args(argv)
    try:
        result = run(
            args.clip, args.output, args.samples, args.skip, args.fps, tuple(args.qualities)
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
