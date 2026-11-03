#!/usr/bin/env python3
"""Offline size sweep using the Sunshine Game Bub canvas and JPEG encoder."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import av
import PIL

HERE = Path(__file__).resolve().parent
GAMEBUB = HERE.parents[1]
PROJECT = HERE.parents[5]
sys.path.insert(0, str(GAMEBUB))
from host import Profile, canvas, clip_frames, encode  # noqa: E402

CAP_BYTES = 48 * 1024
DEFAULT_QUALITIES = (35, 50, 65, 75, 80, 85, 90, 95)


def percentile(values, percentage):
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', type=Path, default=PROJECT / 'media' / 'mass-effect-combat.mp4')
    parser.add_argument('--fps', type=int, default=25,
                        help='Sampling cadence; default uses source native 25 fps without duplicate cadence samples')
    parser.add_argument('--qualities', type=int, nargs='+', default=DEFAULT_QUALITIES)
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    if not args.clip.is_file():
        parser.error(f'clip not found: {args.clip}')
    if args.fps <= 0 or not args.qualities or any(type(q) is not int or not 1 <= q <= 95 for q in args.qualities):
        parser.error('fps must be positive and qualities must be in 1..95')
    if len(set(args.qualities)) != len(args.qualities):
        parser.error('qualities must be unique')
    args.output.mkdir(parents=True, exist_ok=True)

    with av.open(str(args.clip)) as source:
        source_stream = source.streams.video[0]
        source_info = {
            'codec': source_stream.codec_context.name,
            'width': source_stream.width,
            'height': source_stream.height,
            'average_rate': str(source_stream.average_rate),
            'declared_frames': source_stream.frames,
            'container_duration_seconds': source.duration / av.time_base if source.duration else None,
            'sample_aspect_ratio': str(source_stream.sample_aspect_ratio)
            if source_stream.sample_aspect_ratio else None,
        }
    profile = Profile(subsampling='4:2:0', restart_mcus=0, max_frame_bytes=16 * 1024 * 1024)
    sizes = {q: [] for q in args.qualities}
    oversize = {q: 0 for q in args.qualities}
    per_frame_path = args.output / 'per-frame.csv'
    with per_frame_path.open('w', newline='') as stream:
        columns = ['frame_id', 'pts_seconds'] + [f'q{q}_bytes' for q in args.qualities]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for frame_id, source_frame in enumerate(clip_frames(args.clip, args.fps)):
            pts = float(source_frame.time)
            image = canvas(source_frame)
            row = {'frame_id': frame_id, 'pts_seconds': f'{pts:.9f}'}
            for quality in args.qualities:
                jpeg, metadata = encode(image, quality, profile)
                if metadata['width'] != 720 or metadata['height'] != 480:
                    raise AssertionError('encoder returned unexpected canvas dimensions')
                size = len(jpeg)
                sizes[quality].append(size)
                oversize[quality] += size > CAP_BYTES
                row[f'q{quality}_bytes'] = size
            writer.writerow(row)
            if (frame_id + 1) % 250 == 0:
                print(f'encoded {frame_id + 1} sampled frames', flush=True)

    if not sizes or not all(sizes.values()):
        raise RuntimeError('sampling yielded no video frames')
    if len({len(v) for v in sizes.values()}) != 1:
        raise AssertionError('quality runs sampled different frame counts')
    summaries = []
    for quality in args.qualities:
        samples = sizes[quality]
        summaries.append({
            'quality': quality,
            'sample_count': len(samples),
            'mean_bytes': sum(samples) / len(samples),
            'p95_bytes': percentile(samples, 95),
            'max_bytes': max(samples),
            'oversize_count': oversize[quality],
            'oversize_percent': oversize[quality] * 100 / len(samples),
            'oversize_frame_ids': [i for i, size in enumerate(samples) if size > CAP_BYTES],
        })
    metadata = {
        'study': 'Offline Sunshine Game Bub JPEG size sweep',
        'source_file': str(args.clip.resolve()),
        'source_sha256': hashlib.sha256(args.clip.read_bytes()).hexdigest(),
        'sampling_fps': args.fps,
        'source_video': source_info,
        'sample_count': len(next(iter(sizes.values()))),
        'canvas': {'width': 720, 'height': 480, 'content_viewport': 'centered 720x405, black letterbox'},
        'encoder_profile': {'implementation': 'repos/sunshine-30fps-study/tools/gamebub/host.py encode()',
                            'pillow_quality_values': list(args.qualities), 'subsampling': '4:2:0',
                            'restart_mcus': 0, 'progressive': False, 'optimized_huffman': False},
        'cap_bytes': CAP_BYTES,
        'encoder_validation_bound_bytes': profile.max_frame_bytes,
        'runtime_versions': {'python': sys.version.split()[0], 'pillow': PIL.__version__, 'pyav': av.__version__},
        'summary': summaries,
        'scope': 'Local encode and file measurement only; no sender, network, receiver, or transmission used.'
    }
    (args.output / 'results.json').write_text(json.dumps(metadata, indent=2) + '\n')
    lines = [
        '# Mass Effect combat JPEG sizes',
        '',
        f"**Offline software encode; {metadata['sample_count']} frames at {args.fps} samples/s. JPEG cap: {CAP_BYTES:,} bytes (48 KiB), inclusive.**",
        '',
        '| Pillow quality | Mean bytes | p95 bytes | Max bytes | Over cap | Over-cap rate |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for row in summaries:
        lines.append(f"| {row['quality']} | {row['mean_bytes']:.0f} | {row['p95_bytes']:.0f} | {row['max_bytes']} | {row['oversize_count']}/{row['sample_count']} | {row['oversize_percent']:.2f}% |")
    lines += [
        '',
        'The cap applies to JPEG payload bytes only. MSV1 framing, UDP/IP overhead, timing, network transmission and receiver behavior are excluded.',
        '',
        f"Source SHA-256: `{metadata['source_sha256']}`. Canvas: 720×480, centered 720×405 viewport with black letterbox. Encoder: Pillow baseline JPEG, 4:2:0, no restart markers, progressive scans or optimized Huffman tables. See `README.md` for the complete source and method caveats.",
    ]
    (args.output / 'SUMMARY.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({k: v for k, v in metadata.items() if k != 'summary'}, indent=2))
    print((args.output / 'SUMMARY.md').read_text())


if __name__ == '__main__':
    main()
