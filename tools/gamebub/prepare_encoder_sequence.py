"""@brief Export finite, hash-bound RGB8 clip frames for native offline codec profiling.

Selection is explicitly resampled or unique native decode order, followed by
the existing canvas transform. The export never loops or presents repeated
source timestamps as distinct frames.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import av

from host import HEIGHT, WIDTH, canvas, clip_frames

SCHEMA = "gamebub-v20-rgb8-sequence-v1"
FRAME_BYTES = WIDTH * HEIGHT * 3
MAX_FRAMES = 1800
NATIVE_POLICY = (
    "no resampling: unique decoded native frames; skip before requested relative PTS offset"
)


def native_rate(path):
    """@brief Read a declared nominal stream rate without presenting it as measured content FPS."""
    with av.open(str(path)) as container:
        rate = container.streams.video[0].average_rate
        if (
            rate is None
            or rate <= 0
            or not 1 <= rate.numerator <= 1_000_000
            or not 1 <= rate.denominator <= 1_000_000
        ):
            raise ValueError("Native source requires a positive nominal rate")
        return {"numerator": rate.numerator, "denominator": rate.denominator}


def native_frames(path):
    """@brief Decode each original presentation frame once, with no resampling or repetition."""
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        if stream.sample_aspect_ratio not in (None, 1):
            raise ValueError("Normalize nonsquare pixels before sequence export")
        yield from container.decode(stream)


def file_identity(path):
    """@brief Hash the saved clip with bounded reads before publishing frame descriptors."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while data := source.read(1024 * 1024):
            digest.update(data)
            size += len(data)
    if size == 0:
        raise ValueError("Sequence source clip is empty")
    return size, digest.hexdigest()


def export(
    clip, output, frames=60, fps=None, offset_us=0, expected_sha256=None, selection="resampled"
):
    """@brief Export one bounded RGB canvas at a time, with no implicit clip repetition.

    @param clip Saved input video; its bytes are hashed before decode.
    @param output New directory, never an existing destination.
    @param frames Requested unique selected frames, from1 through1800.
    @param fps Existing resampler's integer sampling rate; omitted means30, native mode forbids it.
    @param offset_us Nonnegative relative offset; sampled mode rounds up to its sampling grid.
    @param expected_sha256 Optional expected lowercase source SHA256.
    @param selection Resampled unique frames, or native-decoded frames without a sampling grid.
    @return Complete manifest; incomplete exports never publish manifest.json.
    """
    if selection not in ("resampled", "native-decoded"):
        raise ValueError("Sequence source selection mode")
    if selection == "native-decoded" and fps is not None:
        raise ValueError("Native selection has no resampling FPS")
    if fps is None:
        fps = 30
    if (
        type(frames) is not int
        or not 1 <= frames <= MAX_FRAMES
        or type(fps) is not int
        or not 1 <= fps <= 30
        or type(offset_us) is not int
        or not 0 <= offset_us <= 86_400_000_000
    ):
        raise ValueError("Sequence frame/rate/offset bounds")
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
    ):
        raise ValueError("Sequence source hash format")
    clip, output = Path(clip), Path(output)
    if output.exists():
        raise FileExistsError(output)
    size, digest = file_identity(clip)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("Sequence source hash mismatch")
    native = selection == "native-decoded"
    rate = native_rate(clip) if native else None
    selected = native_frames(clip) if native else clip_frames(clip, fps)
    first_sample = (offset_us * fps + 999_999) // 1_000_000
    manifest = {
        "schema": SCHEMA,
        "label": clip.name,
        "geometry": {"width": WIDTH, "height": HEIGHT, "channels": 3},
        "source": {
            "kind": "saved_clip",
            "file_name": clip.name,
            "bytes": size,
            "sha256": digest,
            "requested_offset_us": offset_us,
            "selection_mode": selection,
            "native_rate": rate,
            "sample_fps": None if native else fps,
            "first_sample_index": None if native else first_sample,
            "first_decoded_id": None,
            "pts_origin_us": None,
            "resampling_policy": NATIVE_POLICY
            if native
            else "existing clip_frames: source at or before sample; ceil offset to sampling grid",
            "canvas_policy": "existing canvas: aspect-preserving fit into centered720x405 within720x480",
            "loop": False,
            "repeated_source_timestamps": False,
        },
        "frames": [],
    }
    previous = previous_decoded = -1
    try:
        for sample, frame in enumerate(selected):
            if frame.time is None or not math.isfinite(frame.time) or frame.time < 0:
                raise ValueError("Sequence requires nonnegative finite source timestamps")
            pts_us = round(frame.time * 1_000_000)
            if pts_us > (1 << 63) - 1:
                raise ValueError("Sequence source timestamp bound")
            if sample == 0:
                manifest["source"]["pts_origin_us"] = pts_us
            if native:
                if pts_us <= previous_decoded:
                    raise ValueError("Repeated/nonmonotonic native source timestamp")
                previous_decoded = pts_us
                if pts_us - manifest["source"]["pts_origin_us"] < offset_us:
                    continue
            elif sample < first_sample:
                continue
            if pts_us <= previous:
                raise ValueError("Repeated/nonmonotonic source timestamp; lower the sample rate")
            image = canvas(frame)
            raw = image.tobytes()
            if image.mode != "RGB" or image.size != (WIDTH, HEIGHT) or len(raw) != FRAME_BYTES:
                raise ValueError("Sequence requires exact720x480 RGB8 canvases")
            if not manifest["frames"]:
                output.mkdir(parents=True, exist_ok=False)
                (output / "frames").mkdir()
                if native:
                    manifest["source"]["first_decoded_id"] = sample
            name = f"frames/frame-{len(manifest['frames']):06d}.rgb"
            (output / name).write_bytes(raw)
            manifest["frames"].append(
                {
                    "id": sample,
                    "pts_us": pts_us,
                    **(
                        {"relative_pts_us": pts_us - manifest["source"]["pts_origin_us"]}
                        if native
                        else {"sample_time_us": sample * 1_000_000 // fps}
                    ),
                    "rgb": {
                        "path": name,
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "dtype": "|u1",
                        "shape": [HEIGHT, WIDTH, 3],
                    },
                }
            )
            previous = pts_us
            if len(manifest["frames"]) == frames:
                break
        if len(manifest["frames"]) != frames:
            raise ValueError("Source clip ended before the requested finite sequence; no loop")
    finally:
        selected.close()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv=None):
    """@brief Export a new saved-clip sequence without overwriting previous measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--selection", choices=("resampled", "native-decoded"), default="resampled")
    parser.add_argument("--offset-us", type=int, default=0)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    result = export(
        args.clip,
        args.output_dir,
        args.frames,
        args.fps,
        args.offset_us,
        args.expected_sha256,
        args.selection,
    )
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "frames": len(result["frames"]),
                "source": result["source"],
                "hardware_verified": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
