# Portable capture buffer adapter prototype

This isolated C++ prototype validates a borrowed four-byte BGRA/BGRX source
buffer and copies its R/G/B channels into a tightly packed owned RGB vector. It
accepts row padding, discards alpha/unused X, checks dimensions, pitch, source
length and size arithmetic, and limits the output allocation to 64 MiB. The
test mutates the input after copying to verify ownership.

It also has a fixed 720×480 canvas candidate. It preserves aspect ratio, fits
the image into a centered 720×405 content viewport on black, rounds output
dimensions to nearest integer, and bilinearly samples pixel centers with
edge-clamping and round-to-nearest channel values. A 16:9 source fills 720×405
with 37 black rows above and 38 below. A 1:1 source fits as a centered 405×405
square. Odd dimensions are supported. This simple filter is deterministic for
the tested compiler/input, but it is not a tuned or perceptual-quality match
for Sunshine's scaler, Pillow LANCZOS, or any production capture path.

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
executable, with ten internal test functions). The warning build used
`-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion`; compilation emitted
no warnings. ASan/UBSan reported no issues.

The synthetic scaler-only probe used a generated 1280×720 RGB buffer, warmed
with three calls and measured 35 calls in the Release warning build. It
reported min 5.410 ms, p50 5.601 ms, p95 5.704 ms, max 6.634 ms. Timing
includes output allocation, but excludes capture, BGRA-to-RGB copy, JPEG and
transport. This is a small single-container CPU microbenchmark, not a
throughput claim for a game, target machine or full streaming path.

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
