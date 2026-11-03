# Portable capture buffer adapter prototype

This isolated C++ prototype validates a borrowed four-byte BGRA/BGRX source
buffer and copies its R/G/B channels into a tightly packed owned RGB vector. It
accepts row padding, discards alpha/unused X, checks dimensions, pitch, source
length and size arithmetic, and limits the output allocation to 64 MiB. The
test mutates the input after copying to verify ownership.

It also has a fixed 720×480 canvas candidate with bilinear, reference area,
and optimized area implementations. All three
preserve aspect ratio, fit the image into a centered 720×405 content viewport
on black, and round output dimensions to nearest integer. Bilinear mode samples
pixel centers with edge-clamping and round-to-nearest channel values. Area mode
uses separable source-pixel coverage averaging on reducing axes and bilinear
sampling on expanding axes; its double-precision intermediate is capped at
64 MiB. A 16:9 source fills 720×405
with 37 black rows above and 38 below. A 1:1 source fits as a centered 405×405
square. Odd dimensions are supported. These simple filters are deterministic
for the tested compiler/input, but they are not tuned or perceptual-quality
matches for Sunshine's scaler, Pillow LANCZOS, or any production capture path.

It does not call DXGI, Windows APIs, Sunshine platform code or the service. It
does not capture, rotate, composite a cursor, encode JPEG, packetize MSV1 or
transmit. It is a small buffer/scaler candidate for a future standalone
capture adapter, not evidence of a working capture path.

Build and run the self-contained tests from this directory:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/bench_capture_buffer
```

## Validation record

Built and tested in the `radiant-xrdp` container, using scratch build trees
outside the repository at `/tmp/gamebub-capture-buffer-adapter-build` and
`/tmp/gamebub-capture-buffer-adapter-warnings`. A third Debug build with
ASan/UBSan used `/tmp/gamebub-capture-buffer-adapter-sanitizers`. Toolchain:
CMake 3.28.3, GNU C++ 13.3.0, C++20. All three CTest runs passed (1/1 test
executable, with twelve internal test functions). The warning build used
`-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion`; compilation emitted
no warnings. ASan/UBSan reported no issues.

The paired synthetic scaler-only probe used a generated 1280×720 RGB buffer,
three warmups and 35 calls per mode in the Release warning build. Bilinear
measured p50 5.534 ms/p95 5.616 ms; double reference area measured
20.939/21.003 ms; precomputed integer area measured 3.895/3.992 ms. Timing
includes output/scratch/plan allocation but excludes capture, BGRA-to-RGB
copy, JPEG and transport. This small single-container CPU microbenchmark is
not a throughput claim for a game, target machine or full streaming path.

## Comparison against existing canvas paths

`compare_canvas.py` runs four deterministic 1280×720 patterns through bilinear,
double-reference area and optimized integer-area C++ modes, then compares
against the adjacent `host.canvas()` behavior for both
Pillow images (LANCZOS) and PyAV frames (FFmpeg RGB bilinear). Patterns are a
smooth gradient, quadrant edge, 1-pixel checkerboard, and 4-pixel stripes.
Each path is checked for the same 720×405 fit geometry, and the C++ output is
run twice to check determinism. `canvas-comparison.json` contains RGB PSNR,
MAE, maximum absolute channel error and changed-channel fraction;
`SUMMARY.md` has the compact table.

Across the gradient, edge, checkerboard and stripes, optimized integer-area
output was within 1 channel level of the double reference (maximum observed
difference 1). The checkerboard deliberately exceeds the output Nyquist limit.
Against Pillow, area measured 49.705 dB PSNR, 0.684 MAE and max error 4,
while bilinear measured 16.494 dB, 25.881 and 100. Against FFmpeg bilinear,
area measured 46.599 dB, 0.926 and 6; bilinear measured 16.457 dB, 26.123 and
100. Four-pixel stripes also differ: area vs FFmpeg bilinear measured
27.492 dB/4.697 MAE, compared with bilinear at 22.065 dB/11.763 MAE. These
values show pixel differences on these synthetic stimuli, not which output
looks preferable in gameplay. Different filters and phases can produce
distinct aliasing/averaging. No gameplay footage, capture, JPEG, real-time
load, display, or receiver is involved.

Reproduce from the prototype root after building `dump_canvas_pattern` in the
container scratch build:

```sh
/home/lori/gamebub-streaming-prototype/.venv/bin/python \
  repos/sunshine-30fps-study/tools/gamebub/experiments/capture-buffer-adapter/compare_canvas.py \
  --adapter-command 'docker exec radiant-xrdp env -u LD_LIBRARY_PATH /tmp/gamebub-capture-buffer-adapter-warnings/dump_canvas_pattern' \
  --output repos/sunshine-30fps-study/tools/gamebub/experiments/capture-buffer-adapter/canvas-comparison.json
```

The container's Lattice SDK sets `LD_LIBRARY_PATH` to an older `libstdc++`
which prevents its system CMake binary from starting. The successful commands
cleared only that variable for the process:

```sh
env -u LD_LIBRARY_PATH cmake -S . -B /tmp/gamebub-capture-buffer-adapter-build \
  -DCMAKE_BUILD_TYPE=Release
env -u LD_LIBRARY_PATH cmake --build /tmp/gamebub-capture-buffer-adapter-build --parallel 2
env -u LD_LIBRARY_PATH ctest --test-dir /tmp/gamebub-capture-buffer-adapter-build --output-on-failure
env -u LD_LIBRARY_PATH cmake -S . -B /tmp/gamebub-capture-buffer-adapter-warnings \
  -DCMAKE_BUILD_TYPE=Release \
  '-DCMAKE_CXX_FLAGS=-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion'
env -u LD_LIBRARY_PATH cmake --build /tmp/gamebub-capture-buffer-adapter-warnings --parallel 2
env -u LD_LIBRARY_PATH ctest --test-dir /tmp/gamebub-capture-buffer-adapter-warnings \
  --output-on-failure
env -u LD_LIBRARY_PATH cmake -S . -B /tmp/gamebub-capture-buffer-adapter-sanitizers \
  -DCMAKE_BUILD_TYPE=Debug \
  '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' \
  '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined'
env -u LD_LIBRARY_PATH cmake --build /tmp/gamebub-capture-buffer-adapter-sanitizers --parallel 2
env -u LD_LIBRARY_PATH ctest --test-dir /tmp/gamebub-capture-buffer-adapter-sanitizers \
  --output-on-failure
env -u LD_LIBRARY_PATH /tmp/gamebub-capture-buffer-adapter-warnings/bench_capture_buffer
```
