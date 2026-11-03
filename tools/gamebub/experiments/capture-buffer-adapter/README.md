# Portable capture buffer adapter prototype

This isolated C++ prototype validates a borrowed four-byte BGRA/BGRX source
buffer and copies its R/G/B channels into a tightly packed owned RGB vector. It
accepts row padding, discards alpha/unused X, checks dimensions, pitch, source
length and size arithmetic, and limits the output allocation to 64 MiB. The
test mutates the input after copying to verify ownership.

It does not call DXGI, Windows APIs, Sunshine platform code or the service. It
does not capture, scale, rotate, composite a cursor, encode JPEG, packetize
MSV1 or transmit. It is a small boundary primitive for a future standalone
capture adapter, not evidence of a working capture path.

Build and run the self-contained tests from this directory:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
```

## Validation record

Built and tested in the `radiant-xrdp` container, using scratch build trees
outside the repository at `/tmp/gamebub-capture-buffer-adapter-build` and
`/tmp/gamebub-capture-buffer-adapter-warnings`. Toolchain: CMake 3.28.3,
GNU C++ 13.3.0, Release configuration, C++20. Both CTest runs passed (1/1
test executable; it runs the six test functions above). The second build used
`-Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion`; compilation emitted
no warnings.

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
```
