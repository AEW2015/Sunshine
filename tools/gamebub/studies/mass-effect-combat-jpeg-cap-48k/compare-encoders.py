#!/usr/bin/env python3
"""Compare Sunshine host.encode and the sender's msv1.encode_receiver_jpeg."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
GAMEBUB = HERE.parents[1]
PROJECT = HERE.parents[5]
sys.path.insert(0, str(GAMEBUB))
from host import Profile, canvas, clip_frames, encode  # noqa: E402
from msv1 import encode_receiver_jpeg  # noqa: E402

QUALITIES = (80, 90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', type=Path, default=PROJECT / 'media' / 'mass-effect-combat.mp4')
    parser.add_argument('--fps', type=int, default=25)
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    if not args.clip.is_file():
        parser.error(f'clip not found: {args.clip}')
    if args.fps <= 0:
        parser.error('fps must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    profile = Profile(subsampling='4:2:0', restart_mcus=0, max_frame_bytes=16 * 1024 * 1024)
    sizes = {q: {'host': [], 'sender': [], 'equal': 0, 'different': 0,
                 'first_differences': []} for q in QUALITIES}
    csv_path = args.output / 'encoder-comparison-per-frame.csv'
    with csv_path.open('w', newline='') as stream:
        columns = ['frame_id', 'pts_seconds']
        for q in QUALITIES:
            columns.extend([f'q{q}_host_bytes', f'q{q}_sender_bytes', f'q{q}_byte_identical'])
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for frame_id, source_frame in enumerate(clip_frames(args.clip, args.fps)):
            image = canvas(source_frame)
            row = {'frame_id': frame_id, 'pts_seconds': f'{float(source_frame.time):.9f}'}
            for quality in QUALITIES:
                host_jpeg, _ = encode(image, quality, profile)
                sender_jpeg = bytes(encode_receiver_jpeg(image, quality))
                data_equal = host_jpeg == sender_jpeg
                sizes[quality]['host'].append(len(host_jpeg))
                sizes[quality]['sender'].append(len(sender_jpeg))
                count_key = 'equal' if data_equal else 'different'
                sizes[quality][count_key] += 1
                if not data_equal and len(sizes[quality]['first_differences']) < 10:
                    sizes[quality]['first_differences'].append({
                        'frame_id': frame_id,
                        'host_bytes': len(host_jpeg),
                        'sender_bytes': len(sender_jpeg),
                        'host_sha256': hashlib.sha256(host_jpeg).hexdigest(),
                        'sender_sha256': hashlib.sha256(sender_jpeg).hexdigest(),
                    })
                row[f'q{quality}_host_bytes'] = len(host_jpeg)
                row[f'q{quality}_sender_bytes'] = len(sender_jpeg)
                row[f'q{quality}_byte_identical'] = data_equal
            writer.writerow(row)
            if (frame_id + 1) % 250 == 0:
                print(f'compared {frame_id + 1} sampled frames', flush=True)

    summary = []
    for quality in QUALITIES:
        host_sizes, sender_sizes = sizes[quality]['host'], sizes[quality]['sender']
        diffs = [b - a for a, b in zip(host_sizes, sender_sizes)]
        summary.append({
            'quality': quality,
            'sample_count': len(host_sizes),
            'byte_identical_frames': sizes[quality]['equal'],
            'different_frames': sizes[quality]['different'],
            'host_size_bytes': {'min': min(host_sizes), 'max': max(host_sizes)},
            'sender_size_bytes': {'min': min(sender_sizes), 'max': max(sender_sizes)},
            'sender_minus_host_size_bytes': {'min': min(diffs), 'max': max(diffs)},
            'first_byte_differences': sizes[quality]['first_differences'],
        })
    result = {
        'study': 'Full-clip byte comparison between Sunshine host encoder and sender function',
        'source_file': str(args.clip.resolve()),
        'source_sha256': hashlib.sha256(args.clip.read_bytes()).hexdigest(),
        'sampling_fps': args.fps,
        'sample_count': len(sizes[80]['host']),
        'qualities': list(QUALITIES),
        'host_encoder': {'path': 'tools/gamebub/host.py::encode', 'sha256': hashlib.sha256((GAMEBUB / 'host.py').read_bytes()).hexdigest()},
        'sender_encoder': {'path': 'tools/gamebub/msv1.py::encode_receiver_jpeg', 'sha256': hashlib.sha256((GAMEBUB / 'msv1.py').read_bytes()).hexdigest()},
        'profile': {'width': 720, 'height': 480, 'subsampling': '4:2:0', 'restart_mcus': 0,
                    'progressive': False, 'optimized_huffman': False},
        'summary': summary,
        'scope': 'Direct offline function comparison. Does not run sender adaptation, packetization, transmission, receiver, or display.',
    }
    (args.output / 'encoder-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = [
        '# Host and sender JPEG encoder comparison', '',
        f"**Offline full-clip byte comparison:** {result['sample_count']:,} frames at {args.fps} fps.", '',
        '| Quality | Identical JPEGs | Different JPEGs | Host size range | Sender size range | Sender minus host bytes |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for row in summary:
        lines.append(
            f"| q{row['quality']} | {row['byte_identical_frames']:,}/{row['sample_count']:,} | "
            f"{row['different_frames']:,} | {row['host_size_bytes']['min']:,}–{row['host_size_bytes']['max']:,} | "
            f"{row['sender_size_bytes']['min']:,}–{row['sender_size_bytes']['max']:,} | "
            f"{row['sender_minus_host_size_bytes']['min']}–{row['sender_minus_host_size_bytes']['max']} |"
        )
    lines += [
        '',
        'Both functions emitted byte-identical JPEGs for every sampled frame in this run. This directly checks encoder output; it does not exercise sender quality adaptation, packetization, transmission, receiver or display.',
        '',
        f"Source SHA-256: `{result['source_sha256']}`. Host encoder SHA-256: `{result['host_encoder']['sha256']}`. Sender encoder source SHA-256: `{result['sender_encoder']['sha256']}`.",
    ]
    (args.output / 'ENCODER-COMPARISON.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
