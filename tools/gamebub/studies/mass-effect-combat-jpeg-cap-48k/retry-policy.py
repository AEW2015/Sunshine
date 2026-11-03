#!/usr/bin/env python3
"""Compare q90 drop-only with one same-frame q80 fallback, offline."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
GAMEBUB = HERE.parents[1]
PROJECT = HERE.parents[5]
sys.path.insert(0, str(GAMEBUB))
from host import Profile, canvas, clip_frames, encode  # noqa: E402

CAP_BYTES = 48 * 1024


def percentile(values, percentage):
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[low])
    portion = position - low
    return ordered[low] * (1 - portion) + ordered[high] * portion


def distribution(values, unit):
    return {
        'sample_count': len(values),
        'mean': statistics.fmean(values) if values else None,
        'p95': percentile(values, 95) if values else None,
        'max': max(values) if values else None,
        'unit': unit,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', type=Path, default=PROJECT / 'media' / 'mass-effect-combat.mp4')
    parser.add_argument('--fps', type=int, default=25)
    parser.add_argument('--initial-quality', type=int, default=90)
    parser.add_argument('--retry-quality', type=int, default=80)
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    if not args.clip.is_file():
        parser.error(f'clip not found: {args.clip}')
    if args.fps <= 0 or not 1 <= args.retry_quality < args.initial_quality <= 95:
        parser.error('need positive fps and 1 <= retry quality < initial quality <= 95')
    args.output.mkdir(parents=True, exist_ok=True)
    profile = Profile(subsampling='4:2:0', restart_mcus=0, max_frame_bytes=16 * 1024 * 1024)
    initial_sizes, selected_sizes = [], []
    initial_times, fallback_times, fallback_total_times = [], [], []
    fallback_qualities, emitted_qualities = [], []
    rows = []
    expected_quality_sizes = None
    sweep_path = HERE / 'per-frame.csv'
    if sweep_path.is_file():
        with sweep_path.open(newline='') as stream:
            expected_quality_sizes = {int(r['frame_id']): int(r[f'q{args.initial_quality}_bytes'])
                                      for r in csv.DictReader(stream)}

    with (args.output / 'retry-policy-per-frame.csv').open('w', newline='') as stream:
        columns = ['frame_id', 'pts_seconds', 'initial_bytes', 'initial_encode_ms',
                   'action', 'retry_bytes', 'retry_encode_ms', 'selected_quality', 'selected_bytes']
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for frame_id, source_frame in enumerate(clip_frames(args.clip, args.fps)):
            image = canvas(source_frame)
            start = time.perf_counter()
            initial_jpeg, _ = encode(image, args.initial_quality, profile)
            initial_ms = (time.perf_counter() - start) * 1000
            initial_sizes.append(len(initial_jpeg))
            initial_times.append(initial_ms)
            if expected_quality_sizes is not None and expected_quality_sizes.get(frame_id) != len(initial_jpeg):
                raise AssertionError(f'initial q{args.initial_quality} size disagrees with sweep at frame {frame_id}')

            retry_size, retry_ms, selected_quality = None, 0.0, args.initial_quality
            if len(initial_jpeg) <= CAP_BYTES:
                action, selected_jpeg = 'send_initial', initial_jpeg
            else:
                start = time.perf_counter()
                retry_jpeg, _ = encode(image, args.retry_quality, profile)
                retry_ms = (time.perf_counter() - start) * 1000
                retry_size = len(retry_jpeg)
                fallback_times.append(retry_ms)
                fallback_qualities.append(args.retry_quality)
                if retry_size <= CAP_BYTES:
                    action, selected_jpeg, selected_quality = 'send_retry', retry_jpeg, args.retry_quality
                else:
                    action, selected_jpeg, selected_quality = 'drop_after_retry', None, None
            fallback_total_times.append(initial_ms + retry_ms)
            if selected_jpeg is not None:
                selected_sizes.append(len(selected_jpeg))
                emitted_qualities.append(selected_quality)
            row = {
                'frame_id': frame_id,
                'pts_seconds': f'{float(source_frame.time):.9f}',
                'initial_bytes': len(initial_jpeg),
                'initial_encode_ms': f'{initial_ms:.6f}',
                'action': action,
                'retry_bytes': '' if retry_size is None else retry_size,
                'retry_encode_ms': f'{retry_ms:.6f}' if retry_ms else '',
                'selected_quality': '' if selected_quality is None else selected_quality,
                'selected_bytes': '' if selected_jpeg is None else len(selected_jpeg),
            }
            writer.writerow(row)
            rows.append(row)

    frames = len(initial_sizes)
    if expected_quality_sizes is not None and frames != len(expected_quality_sizes):
        raise AssertionError('policy and sweep sampled different frame counts')
    drop_only_sent = [size for size in initial_sizes if size <= CAP_BYTES]
    drop_only_drops = frames - len(drop_only_sent)
    retry_drops = frames - len(selected_sizes)
    result = {
        'study': 'Same-frame single-retry policy; offline host encode only',
        'source_file': str(args.clip.resolve()),
        'sampling_fps': args.fps,
        'sample_count': frames,
        'cap_bytes': CAP_BYTES,
        'initial_quality': args.initial_quality,
        'retry_quality': args.retry_quality,
        'profile': {'subsampling': '4:2:0', 'restart_mcus': 0, 'progressive': False,
                    'optimized_huffman': False},
        'comparison': {
            'drop_only': {
                'rule': 'Encode at initial quality; drop frame if size exceeds cap.',
                'sent_frames': len(drop_only_sent), 'dropped_frames': drop_only_drops,
                'drop_percent': drop_only_drops * 100 / frames,
                'chosen_quality_counts': {str(args.initial_quality): len(drop_only_sent)},
                'sent_jpeg_size': distribution(drop_only_sent, 'bytes'),
                'host_encode_validation_ms_per_capture': distribution(initial_times, 'milliseconds'),
                'total_encode_ms': sum(initial_times),
            },
            'one_lower_quality_retry': {
                'rule': 'Encode at initial quality; on oversize re-encode that same frame once at retry quality; drop only if retry remains oversized.',
                'retried_frames': len(fallback_times), 'retry_successes': emitted_qualities.count(args.retry_quality),
                'dropped_frames': retry_drops, 'drop_percent': retry_drops * 100 / frames,
                'chosen_quality_counts': {str(q): emitted_qualities.count(q) for q in sorted(set(emitted_qualities))},
                'sent_jpeg_size': distribution(selected_sizes, 'bytes'),
                'host_retry_encode_validation_ms': distribution(fallback_times, 'milliseconds'),
                'host_encode_validation_ms_per_capture_including_retry': distribution(fallback_total_times, 'milliseconds'),
                'total_encode_ms_including_retry': sum(fallback_total_times),
            },
        },
        'scope': 'No sender invocation or transmission. Encode timings are this Linux host/Pillow run and include Sunshine host JPEG inspection and software decode validation.',
    }
    (args.output / 'retry-policy-results.json').write_text(json.dumps(result, indent=2) + '\n')
    drop = result['comparison']['drop_only']
    retry = result['comparison']['one_lower_quality_retry']
    drop_size, retry_size = drop['sent_jpeg_size'], retry['sent_jpeg_size']
    drop_time = drop['host_encode_validation_ms_per_capture']
    retry_time = retry['host_encode_validation_ms_per_capture_including_retry']
    lines = [
        '# Single lower-quality retry comparison', '',
        f"**Offline only:** {frames:,} frames at native {args.fps} fps; initial q{args.initial_quality}, one q{args.retry_quality} retry when q{args.initial_quality} exceeds {CAP_BYTES:,} bytes. No frames were transmitted.", '',
        '| Policy | Sent | Dropped | Chosen qualities | Sent JPEG p95 / max bytes | Encode-validation ms/frame mean / p95 | Total encode-validation ms |',
        '|---|---:|---:|---|---:|---:|---:|',
    ]
    for label, policy, sent, size, timing, total in (
        ('Drop-only', drop, drop['sent_frames'], drop_size, drop_time, drop['total_encode_ms']),
        ('One same-frame retry', retry, retry_size['sample_count'], retry_size, retry_time,
         retry['total_encode_ms_including_retry']),
    ):
        choices = ', '.join(f"q{quality}: {count}" for quality, count in policy['chosen_quality_counts'].items())
        lines.append(
            f"| {label} | {sent:,} | {policy['dropped_frames']:,} ({policy['drop_percent']:.2f}%) | "
            f"{choices} | {size['p95']:.0f} / {size['max']:.0f} | "
            f"{timing['mean']:.3f} / {timing['p95']:.3f} | {total:,.0f} |"
        )
    overhead = (retry['total_encode_ms_including_retry'] / drop['total_encode_ms'] - 1) * 100
    lines += [
        '',
        f"The retry ran on {retry['retried_frames']:,} initial oversize frames and fit {retry['retry_successes']:,} at q{args.retry_quality}. It eliminated {drop['dropped_frames']:,} drops in this sample. Total host encode-validation time increased by {overhead:.1f}% in this run. Timings include Sunshine host JPEG inspection and software decode validation; they do not predict Windows frame deadlines.",
        '',
        'The 48 KiB cap applies to JPEG bytes only; framing and transport overhead are excluded. See `README.md` for source, canvas, encoder profile and limitations.',
    ]
    (args.output / 'POLICY-SUMMARY.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
