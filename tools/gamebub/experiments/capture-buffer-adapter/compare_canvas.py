#!/usr/bin/env python3
"""Compare C++ bilinear canvas candidate with Pillow and PyAV canvas paths."""
import argparse
import json
import math
from pathlib import Path
import shlex
import subprocess
import sys

import av
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
GAMEBUB = HERE.parents[1]
sys.path.insert(0, str(GAMEBUB))
from host import canvas  # noqa: E402

WIDTH, HEIGHT = 1280, 720
NAMES = ('gradient', 'edge', 'checker1', 'stripes4')


def pattern(name):
    y, x = np.indices((HEIGHT, WIDTH), dtype=np.uint32)
    if name == 'gradient':
        red = (x * 255 + (WIDTH - 1) // 2) // (WIDTH - 1)
        green = (y * 255 + (HEIGHT - 1) // 2) // (HEIGHT - 1)
        blue = ((x + y) * 255 + (WIDTH + HEIGHT - 2) // 2) // (WIDTH + HEIGHT - 2)
        return np.stack((red, green, blue), axis=2).astype(np.uint8)
    if name == 'edge':
        right, lower = x >= WIDTH // 2, y >= HEIGHT // 2
        image = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        image[~lower & ~right] = (255, 0, 0)
        image[~lower & right] = (0, 255, 0)
        image[lower & ~right] = (0, 0, 255)
        image[lower & right] = (255, 255, 255)
        return image
    if name == 'checker1':
        value = (((x + y) % 2) * 255).astype(np.uint8)
        return np.repeat(value[:, :, None], 3, axis=2)
    if name == 'stripes4':
        bright = (x // 4) % 2 != 0
        image = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
        image[bright] = (255, 220, 30)
        image[~bright] = (10, 30, 180)
        return image
    raise ValueError(f'unknown pattern {name}')


def metrics(reference, actual):
    delta = np.abs(reference.astype(np.int16) - actual.astype(np.int16))
    mse = float(np.mean(delta.astype(np.float64) ** 2))
    return {
        'rgb_psnr_db': None if mse == 0 else 10 * math.log10(255 * 255 / mse),
        'mae_channel_levels': float(np.mean(delta)),
        'max_abs_channel_levels': int(delta.max()),
        'changed_channel_fraction': float(np.count_nonzero(delta) / delta.size),
        'mse': mse,
    }


def validate_geometry(image, label):
    if image.shape != (480, 720, 3):
        raise RuntimeError(f'{label}: wrong output dimensions {image.shape}')
    if np.any(image[:37]) or np.any(image[442:]):
        raise RuntimeError(f'{label}: expected 37 top and 38 bottom black rows')
    if not np.any(image[37]) or not np.any(image[441]):
        raise RuntimeError(f'{label}: expected content beginning at row 37 through 441')


def run_adapter(command, name, mode):
    proc = subprocess.run([*command, name, mode], check=True, stdout=subprocess.PIPE)
    expected = 720 * 480 * 3
    if len(proc.stdout) != expected:
        raise RuntimeError(f'C++ adapter returned {len(proc.stdout)} bytes, expected {expected}')
    return np.frombuffer(proc.stdout, dtype=np.uint8).reshape((480, 720, 3)).copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter-command', required=True,
                        help='C++ helper command; pattern name is appended as its final argument')
    parser.add_argument('--output', type=Path, default=HERE / 'canvas-comparison.json')
    args = parser.parse_args()
    command = shlex.split(args.adapter_command)
    if not command:
        parser.error('--adapter-command must not be empty')

    results = {
        'study': 'Synthetic RGB resampling implementation comparison',
        'input': {'size': f'{WIDTH}x{HEIGHT}', 'patterns': list(NAMES)},
        'canvas_geometry': {'output': '720x480', 'content': '720x405', 'top_black_rows': 37,
                            'bottom_black_rows': 38, 'fit': 'aspect-preserving center fit'},
        'paths': {
            'cpp_bilinear': 'isolated bilinear_letterbox_720x480; pixel-center bilinear, edge clamp, round-nearest',
            'cpp_area_reference': 'isolated area_letterbox_720x480; double-precision separable source-area coverage reference',
            'cpp_area_optimized': 'isolated optimized_area_letterbox_720x480; precomputed integer overlap weights and one final rounding',
            'pillow': 'adjacent host.canvas(PIL.Image), default LANCZOS',
            'pyav_ffmpeg': 'adjacent host.canvas(av.VideoFrame), RGB-to-RGB reformat with bilinear interpolation',
        },
        'comparisons': {},
        'caveats': [
            'Synthetic patterns are controlled resampling stimuli, not gameplay footage.',
            'PSNR and channel error summarize implementation differences only; they do not rank perceived quality.',
            'The 1-pixel checkerboard intentionally exceeds the output Nyquist limit. Different filtering can produce aliasing, blur or different phase patterns; its large error is expected and is not an acceptance threshold.',
            'This comparison does not measure capture, JPEG, runtime throughput, display output or receiver behavior.',
        ],
    }
    for name in NAMES:
        source = pattern(name)
        cpp_bilinear = run_adapter(command, name, 'bilinear')
        cpp_area = run_adapter(command, name, 'area')
        cpp_area_optimized = run_adapter(command, name, 'area_fast')
        pillow = np.asarray(canvas(Image.fromarray(source)), dtype=np.uint8)
        ffmpeg_frame = av.VideoFrame.from_ndarray(source, format='rgb24')
        pyav_ffmpeg = np.asarray(canvas(ffmpeg_frame), dtype=np.uint8)
        for label, image in (('cpp_bilinear', cpp_bilinear), ('cpp_area_reference', cpp_area),
                             ('cpp_area_optimized', cpp_area_optimized),
                             ('pillow', pillow), ('pyav_ffmpeg', pyav_ffmpeg)):
            validate_geometry(image, f'{name}/{label}')
        for mode, image in (('bilinear', cpp_bilinear), ('area', cpp_area), ('area_fast', cpp_area_optimized)):
            repeat = run_adapter(command, name, mode)
            if not np.array_equal(image, repeat):
                raise RuntimeError(f'{name}/{mode}: C++ output is not deterministic across repeated runs')
        results['comparisons'][name] = {
            'cpp_bilinear_vs_pillow_lanczos': metrics(pillow, cpp_bilinear),
            'cpp_bilinear_vs_pyav_ffmpeg_bilinear': metrics(pyav_ffmpeg, cpp_bilinear),
            'cpp_area_vs_pillow_lanczos': metrics(pillow, cpp_area),
            'cpp_area_vs_pyav_ffmpeg_bilinear': metrics(pyav_ffmpeg, cpp_area),
            'cpp_area_vs_cpp_bilinear': metrics(cpp_bilinear, cpp_area),
            'cpp_area_optimized_vs_reference': metrics(cpp_area, cpp_area_optimized),
            'cpp_area_optimized_vs_pillow_lanczos': metrics(pillow, cpp_area_optimized),
            'cpp_area_optimized_vs_pyav_ffmpeg_bilinear': metrics(pyav_ffmpeg, cpp_area_optimized),
            'pillow_vs_pyav_ffmpeg': metrics(pyav_ffmpeg, pillow),
        }
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    lines = [
        '# Synthetic canvas scaler comparison', '',
        'All paths produce 720×480 RGB with 720×405 content and 37/38 black top/bottom rows.',
        'PSNR and absolute channel error compare implementation outputs; they are not perceptual-quality scores.', '',
        '| Pattern | Comparison | PSNR dB | MAE/channel | Max abs error | Changed channel fraction |',
        '|---|---|---:|---:|---:|---:|',
    ]
    labels = (
        ('cpp_bilinear_vs_pillow_lanczos', 'C++ bilinear vs Pillow LANCZOS'),
        ('cpp_bilinear_vs_pyav_ffmpeg_bilinear', 'C++ bilinear vs PyAV/FFmpeg bilinear'),
        ('cpp_area_vs_pillow_lanczos', 'C++ area vs Pillow LANCZOS'),
        ('cpp_area_vs_pyav_ffmpeg_bilinear', 'C++ area vs PyAV/FFmpeg bilinear'),
        ('cpp_area_vs_cpp_bilinear', 'C++ area vs C++ bilinear'),
        ('cpp_area_optimized_vs_reference', 'C++ optimized area vs double reference'),
        ('cpp_area_optimized_vs_pillow_lanczos', 'C++ optimized area vs Pillow LANCZOS'),
        ('cpp_area_optimized_vs_pyav_ffmpeg_bilinear', 'C++ optimized area vs PyAV/FFmpeg bilinear'),
        ('pillow_vs_pyav_ffmpeg', 'Pillow LANCZOS vs PyAV/FFmpeg bilinear'),
    )
    for name in NAMES:
        for key, label in labels:
            item = results['comparisons'][name][key]
            lines.append(f"| {name} | {label} | {item['rgb_psnr_db']:.3f} | {item['mae_channel_levels']:.3f} | {item['max_abs_channel_levels']} | {item['changed_channel_fraction']:.4f} |")
    lines += ['',
              'The 1-pixel checkerboard is above output Nyquist. Its low cross-path PSNR reflects different alias/filter/phase outcomes and is expected for this stress pattern. Four-pixel stripes also expose filter behavior. Smooth gradient differences are small; hard-edge maxima depend on the scaler. These controlled patterns do not show which output looks preferable in gameplay.', '',
              'Synthetic inputs are not gameplay footage. No capture, JPEG, runtime throughput, display, receiver, or perceptual acceptance is tested. See `README.md` for exact reproduction commands.']
    (args.output.parent / 'SUMMARY.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
