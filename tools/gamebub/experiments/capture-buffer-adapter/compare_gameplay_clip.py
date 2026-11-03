#!/usr/bin/env python3
"""Compare isolated scaler outputs on uniformly sampled local clip frames."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import time

import av
import numpy as np
from PIL import Image, __version__ as pillow_version

HERE = Path(__file__).resolve().parent
GAMEBUB = HERE.parents[1]
sys.path.insert(0, str(GAMEBUB))
from host import canvas  # noqa: E402


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def nearest_rank(histogram, percentile):
    total = int(histogram.sum())
    rank = max(1, math.ceil(total * percentile))
    return int(np.searchsorted(np.cumsum(histogram), rank, side='left'))


def compare(reference, actual):
    delta = np.abs(reference.astype(np.int16) - actual.astype(np.int16)).astype(np.uint8)
    histogram = np.bincount(delta.reshape(-1), minlength=256).astype(np.int64)
    mse = float(np.square(delta.astype(np.float64)).mean())
    return {
        'mse': mse,
        'rgb_psnr_db': None if mse == 0 else 10 * math.log10(255 * 255 / mse),
        'mae_channel_levels': float(delta.mean()),
        'changed_channel_fraction': float(np.count_nonzero(delta) / delta.size),
        'p50_abs_channel_error': nearest_rank(histogram, .50),
        'p90_abs_channel_error': nearest_rank(histogram, .90),
        'p95_abs_channel_error': nearest_rank(histogram, .95),
        'p99_abs_channel_error': nearest_rank(histogram, .99),
        'p99_9_abs_channel_error': nearest_rank(histogram, .999),
        'max_abs_channel_error': int(histogram.nonzero()[0][-1]),
        'channel_error_histogram': histogram.tolist(),
    }


def aggregate_frame_metrics(rows, key):
    values = [row[key] for row in rows]
    ordered = sorted(values)
    return {
        'frame_count': len(values),
        'median_frame_mae': float(np.percentile(ordered, 50)),
        'p95_frame_mae': float(np.percentile(ordered, 95)),
        'max_frame_mae': float(max(values)),
        'frames_with_any_difference': sum(value > 0 for value in values),
    }


def summarize_histogram(histogram):
    histogram = np.asarray(histogram, dtype=np.int64)
    total = int(histogram.sum())
    squared_error = sum(index * index * int(count) for index, count in enumerate(histogram))
    mse = squared_error / total
    return {
        'compared_channel_values': total,
        'mse': mse,
        'rgb_psnr_db': None if mse == 0 else 10 * math.log10(255 * 255 / mse),
        'mae_channel_levels': sum(i * int(count) for i, count in enumerate(histogram)) / total,
        'changed_channel_fraction': 1.0 - int(histogram[0]) / total,
        'p50_abs_channel_error': nearest_rank(histogram, .50),
        'p90_abs_channel_error': nearest_rank(histogram, .90),
        'p95_abs_channel_error': nearest_rank(histogram, .95),
        'p99_abs_channel_error': nearest_rank(histogram, .99),
        'p99_9_abs_channel_error': nearest_rank(histogram, .999),
        'max_abs_channel_error': int(histogram.nonzero()[0][-1]),
        'channel_error_histogram': histogram.tolist(),
    }


def duration_summary(values_ns):
    values_ms = np.asarray(values_ns, dtype=np.float64) / 1e6
    return {
        'samples': int(values_ms.size),
        'p50_ms': float(np.percentile(values_ms, 50)),
        'p95_ms': float(np.percentile(values_ms, 95)),
        'max_ms': float(values_ms.max()),
    }


def verify_canvas(image, name):
    if image.shape != (480, 720, 3):
        raise RuntimeError(f'{name}: expected 720x480 RGB, got {image.shape}')
    if np.any(image[:37]) or np.any(image[442:]):
        raise RuntimeError(f'{name}: expected black letterbox rows 0..36 and 442..479')


def run_adapter(command, width, height, source_bytes):
    completed = subprocess.run(
        [*command, str(width), str(height), '-', '-'],
        input=source_bytes, check=True, capture_output=True,
    )
    fields = completed.stderr.decode('ascii').strip().split('\t', 1)
    if len(fields) != 2:
        raise RuntimeError(f'Unexpected C++ scaler timing record: {completed.stderr!r}')
    timing_ns, compiler = int(fields[0]), fields[1]
    output = np.frombuffer(completed.stdout, dtype=np.uint8)
    if output.size != 720 * 480 * 3:
        raise RuntimeError(f'C++ scaler wrote {output.size} bytes, expected 1,036,800')
    return output.reshape((480, 720, 3)), timing_ns, compiler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip', type=Path, required=True, help='Local 1280x720 video; never copied into the report')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--scale-command', required=True,
                        help='C++ raw-RGB scaler executable command')
    parser.add_argument('--output', type=Path, default=HERE / 'gameplay-scaler-comparison.json')
    args = parser.parse_args()
    if not args.clip.is_file() or not 2 <= args.samples <= 128:
        parser.error('clip must exist and samples must be in 2..128')
    command = shlex.split(args.scale_command)
    if not command:
        parser.error('--scale-command must not be empty')

    container = av.open(str(args.clip))
    stream = container.streams.video[0]
    if (stream.width, stream.height) != (1280, 720):
        raise ValueError(f'Expected 1280x720 input, got {stream.width}x{stream.height}')
    reported_frame_count = stream.frames
    codec_name = stream.codec_context.name
    average_rate = str(stream.average_rate)
    duration_seconds = None if stream.duration is None else float(stream.duration * stream.time_base)
    frame_count = sum(1 for _ in container.decode(stream))
    container.close()
    if frame_count < args.samples:
        raise ValueError(f'Clip reports only {frame_count} frames for {args.samples} samples')
    sample_indices = sorted({
        round(index * (frame_count - 1) / (args.samples - 1))
        for index in range(args.samples)
    })
    wanted = set(sample_indices)

    rows = []
    histograms = {
        'optimized_area_vs_pillow_lanczos': np.zeros(256, dtype=np.int64),
        'optimized_area_vs_pyav_ffmpeg_bilinear': np.zeros(256, dtype=np.int64),
    }
    timings = {'optimized_area_cpp': [], 'pillow_lanczos_canvas': [], 'pyav_ffmpeg_bilinear_canvas': []}
    compiler_version = None
    decoded = 0
    container = av.open(str(args.clip))
    stream = container.streams.video[0]
    try:
        for frame in container.decode(stream):
            index = decoded
            decoded += 1
            if index not in wanted:
                continue
            rgb = frame.to_ndarray(format='rgb24')
            if rgb.shape != (720, 1280, 3):
                raise RuntimeError(f'Frame {index}: unexpected decoded RGB shape {rgb.shape}')
            pillow_source = Image.fromarray(rgb, mode='RGB')

            start = time.perf_counter_ns()
            pillow_result = np.asarray(canvas(pillow_source), dtype=np.uint8)
            pillow_ns = time.perf_counter_ns() - start

            start = time.perf_counter_ns()
            ffmpeg_result = np.asarray(canvas(frame), dtype=np.uint8)
            ffmpeg_ns = time.perf_counter_ns() - start

            cpp_result, cpp_ns, compiler_version = run_adapter(
                command, 1280, 720, rgb.tobytes()
            )
            for name, image in (
                ('optimized_area_cpp', cpp_result),
                ('pillow_lanczos_canvas', pillow_result),
                ('pyav_ffmpeg_bilinear_canvas', ffmpeg_result),
            ):
                verify_canvas(image, f'frame {index}/{name}')

            pillow_diff = compare(pillow_result, cpp_result)
            ffmpeg_diff = compare(ffmpeg_result, cpp_result)
            histograms['optimized_area_vs_pillow_lanczos'] += np.asarray(
                pillow_diff.pop('channel_error_histogram'), dtype=np.int64
            )
            histograms['optimized_area_vs_pyav_ffmpeg_bilinear'] += np.asarray(
                ffmpeg_diff.pop('channel_error_histogram'), dtype=np.int64
            )
            rows.append({
                'decode_frame_index': index,
                'pts': frame.pts,
                'time_seconds': None if frame.time is None else float(frame.time),
                'pixel_difference_vs_pillow_lanczos': pillow_diff,
                'pixel_difference_vs_pyav_ffmpeg_bilinear': ffmpeg_diff,
                'cpu_ms': {
                    'optimized_area_cpp_kernel': cpp_ns / 1e6,
                    'pillow_lanczos_canvas': pillow_ns / 1e6,
                    'pyav_ffmpeg_bilinear_canvas': ffmpeg_ns / 1e6,
                },
            })
            timings['optimized_area_cpp'].append(cpp_ns)
            timings['pillow_lanczos_canvas'].append(pillow_ns)
            timings['pyav_ffmpeg_bilinear_canvas'].append(ffmpeg_ns)
    finally:
        container.close()
    if len(rows) != len(sample_indices):
        raise RuntimeError(f'Decoded {len(rows)} selected frames; expected {len(sample_indices)}')

    clip_path = args.clip.resolve()
    results = {
        'study': 'Offline sampled-gameplay scaler comparison',
        'source': {
            'path': str(clip_path),
            'sha256': file_sha256(clip_path),
            'size_bytes': clip_path.stat().st_size,
            'codec': codec_name,
            'width': stream.width,
            'height': stream.height,
            'decoded_frames': frame_count,
            'container_reported_frames': reported_frame_count,
            'reported_average_rate': average_rate,
            'duration_seconds': duration_seconds,
            'sample_indices_zero_based': sample_indices,
            'sample_count': len(rows),
        },
        'canvas': {
            'output': '720x480 RGB',
            'content': '720x405 centered fit',
            'expected_black_rows': {'top': 37, 'bottom': 38},
        },
        'paths': {
            'optimized_area_cpp_kernel': 'optimized_area_letterbox_720x480 on decoded frame converted to packed RGB; C++ timer excludes process startup and raw-RGB pipe transfer',
            'pillow_lanczos_canvas': 'existing host.canvas(PIL RGB), including conversion, LANCZOS resize and canvas composition',
            'pyav_ffmpeg_bilinear_canvas': 'existing host.canvas(av.VideoFrame), including FFmpeg RGB bilinear reformat and canvas composition',
        },
        'environment': {
            'python': sys.version.split()[0],
            'pyav': av.__version__,
            'pillow': pillow_version,
            'numpy': np.__version__,
            'platform': platform.platform(),
            'cpp_compiler': compiler_version,
        },
        'implementation': {
            'comparison_script_sha256': file_sha256(Path(__file__).resolve()),
            'cpp_helper_command': args.scale_command,
            'cpp_helper_source_sha256': file_sha256(HERE / 'scale_raw_rgb.cpp'),
            'scaler_source_sha256': file_sha256(HERE / 'capture_buffer.cpp'),
            'selection': 'round(i * (decoded_frame_count - 1) / (sample_count - 1)) for i=0..sample_count-1',
            'timing_repeats': 1,
        },
        'aggregate_pixel_differences': {
            key: summarize_histogram(hist)
            for key, hist in histograms.items()
        },
        'per_frame_error_summary': {
            'optimized_area_vs_pillow_lanczos': aggregate_frame_metrics(
                [row['pixel_difference_vs_pillow_lanczos'] for row in rows], 'mae_channel_levels'
            ),
            'optimized_area_vs_pyav_ffmpeg_bilinear': aggregate_frame_metrics(
                [row['pixel_difference_vs_pyav_ffmpeg_bilinear'] for row in rows], 'mae_channel_levels'
            ),
        },
        'cpu_costs': {
            name: duration_summary(values)
            for name, values in timings.items()
        },
        'frames': rows,
        'caveats': [
            'This is a limited 24-frame, uniformly spaced sample from one already-compressed local clip; it does not cover every game scene or source format.',
            'The container reports a frame count that differs from the number of frames actually decoded; sampling uses the counted decoded-frame sequence, and both values are recorded.',
            'RGB channel error and PSNR are implementation-difference metrics, not perceptual quality scores or gameplay acceptance.',
            'CPU figures are scaler/canvas function timings on this host. C++ kernel timing excludes process startup and raw-RGB pipe transfer; FFmpeg timing includes pixel-format conversion. They are not end-to-end or target-hardware measurements.',
            'No live capture, JPEG encoding, packetization, receiver, display, or hardware was used.',
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    summary = [
        '# Sampled Mass Effect clip scaler comparison', '',
        f"Input: `{clip_path.name}`, SHA-256 `{results['source']['sha256']}`, "
        f"{frame_count} decoded frames (container reported {reported_frame_count}) at {average_rate} fps; sampled {len(rows)} uniformly.",
        'Each path produces a 720×480 canvas with 720×405 content and 37/38 black top/bottom rows.',
        'Pixel errors compare C++ optimized area output with existing host canvas paths; they do not rank perceived quality.', '',
        '| Comparison | PSNR dB | MAE/channel | p50 abs error | p95 abs error | p99 abs error | Max abs error | Changed fraction |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for key, label in (
        ('optimized_area_vs_pillow_lanczos', 'Optimized area vs Pillow LANCZOS'),
        ('optimized_area_vs_pyav_ffmpeg_bilinear', 'Optimized area vs PyAV/FFmpeg bilinear'),
    ):
        item = results['aggregate_pixel_differences'][key]
        psnr = 'infinite' if item['rgb_psnr_db'] is None else f"{item['rgb_psnr_db']:.3f}"
        summary.append(
            f"| {label} | {psnr} | {item['mae_channel_levels']:.3f} | "
            f"{item['p50_abs_channel_error']} | {item['p95_abs_channel_error']} | "
            f"{item['p99_abs_channel_error']} | {item['max_abs_channel_error']} | "
            f"{item['changed_channel_fraction']:.4f} |"
        )
    summary += ['', '| Canvas path | p50 ms | p95 ms | max ms |', '|---|---:|---:|---:|']
    for key, label in (
        ('optimized_area_cpp', 'C++ optimized area kernel'),
        ('pillow_lanczos_canvas', 'Pillow LANCZOS canvas'),
        ('pyav_ffmpeg_bilinear_canvas', 'PyAV/FFmpeg bilinear canvas'),
    ):
        item = results['cpu_costs'][key]
        summary.append(f"| {label} | {item['p50_ms']:.3f} | {item['p95_ms']:.3f} | {item['max_ms']:.3f} |")
    summary += [
        '',
        'PSNR, absolute channel errors and CPU timings summarize only these sampled outputs and this host. C++ timing excludes helper process startup/raw-RGB pipe transfer; FFmpeg timing includes pixel-format conversion. No perceptual, end-to-end, live-capture or hardware claim is made.',
        'See `README.md` for the exact source provenance and reproduction command. No video frames are stored in this report.',
    ]
    (args.output.parent / 'gameplay-scaler-comparison.md').write_text('\n'.join(summary) + '\n')
    print(json.dumps({
        'output': str(args.output),
        'sample_count': len(rows),
        'pixel_differences': results['aggregate_pixel_differences'],
        'cpu_costs': results['cpu_costs'],
    }, indent=2))


if __name__ == '__main__':
    main()
