# Game Bub host laboratory

This is the initial offline milestone, pending coordination with the ESP32/FPGA
agent. It is **not a network sender or an integrated Sunshine JPEG mode**.
There is no socket code, selected packet format, or receiver playback claim.
The installed Sunshine service and original checkout remain unchanged.

## Windows setup and verification

Development checkout: `C:\ai\sunshine-gamebub`, branch `gamebub/host`, upstream
base `3d6e1d60`. The branch belongs to the original local repository through
`git worktree`; keep the original checkout available. Install Git, Python 3.11,
and uv. On this machine uv was installed with `py -3.11 -m pip install --user uv`;
`py -3.11 -m uv` works without changing PATH.

From the repository root, refresh the repository's own tooling:

```powershell
py -3.11 -m uv sync --locked
```

That project requires Python >=3.14; uv downloads a suitable interpreter.
The isolated laboratory uses Python 3.11..3.14 and its own lockfile, without
changing Sunshine's dependencies. From `tools\gamebub`:

```powershell
py -3.11 -m uv sync --locked
py -3.11 -m uv run --locked ruff check .
py -3.11 -m uv run --locked ruff format --check .
py -3.11 -m uv run --locked coverage run -m unittest -v
py -3.11 -m uv run --locked coverage run --append host.py --output artifacts\coverage-entry --frames 1 --link-mbps 1000
py -3.11 -m uv run --locked coverage run --append make_assets.py --output artifacts\coverage-fixtures
py -3.11 -m uv run --locked coverage report --fail-under=100
```

Use a fresh output directory for each run; measurement files are never overwritten.
The appended coverage commands exercise CLI entry points under instrumentation;
do not use that run for performance measurements. Regression tests use controlled
clocks for deterministic overload behavior, real JPEG encode/decode, a generated
60-Hz video input, and fixture regeneration checks. Coverage measures `host.py`
and `make_assets.py`.

## Capture and experiments

The default source is a deterministic moving pattern, not game footage:

```powershell
py -3.11 -m uv run --locked python host.py --output artifacts\patterns --frames 900 --fps 30 --quality 75 --link-mbps 20
py -3.11 -m uv run --locked python host.py --desktop --output artifacts\desktop --frames 300 --fps 30 --link-mbps 20
py -3.11 -m uv run --locked python host.py --clip C:\clips\game.mp4 --output artifacts\game --frames 1800 --fps 30 --quality 75 --link-mbps 20 --save-jpeg
```

Desktop capture uses Pillow `ImageGrab` on the primary display, in the interactive
user session. This is a software test path rather than Sunshine's DXGI capture.
Clips must have square pixels and strictly increasing PTS; normalize rotated or
anamorphic footage before use. Clip frames are sampled on the requested timeline;
EOF stops the run, and source starvation skips pacing slots without a queue.
Stale clip samples skip RGB conversion. The selected frame is scaled with
libswscale before conversion; image/desktop sources use Pillow Lanczos.
Capture, scale, encode, validation, modeled link delay, and optional file writes
all occur serially. Capture/scale and encode/validation timings are logged
separately. This implementation prioritizes conformance and bounded memory.

`--link-mbps` is a **simulation**, with no packet overhead, retransmission, Wi-Fi,
QSPI, or decoding/display costs. `--max-age-ms` defaults to 66.7 ms from capture
start to modeled completion. The model drops frames that cannot meet that bound.
Quality falls in steps of five to `--min-quality` (default 20), and recovers in
steps of one up to `--quality`. It also decreases when frame bytes exceed the
link's target-cadence budget. Pacing slots missed while processing are skipped.
There is at most one frame in process and no waiting-frame queue; no producer
thread can accumulate stale captured frames. 60 fps is deliberately rejected.

Each `frames.jsonl` entry includes frame ID, capture-relative microseconds,
quality, byte size, local CRC, parsed JPEG restrictions, capture/scale and
encode/validation time, skipped slots, modeled completion/drop or failure, frame
age, and cumulative counts/bytes. Calculate interval bitrate/FPS from cumulative
counts and elapsed seconds. Queue depth and waiting-queue age are zero by design;
frame age includes processing and modeled serialization. `summary.json` reports
duration, rates, sizes, quantiles, quality histogram, versions, and explicit null
receiver latency. Exit code 2 means a frame/capture failure; expected overload
drops have exit code 0 and remain visible in counters. Disk output is optional.

To exercise constraints, supply a local JSON profile, for example:

```json
{
  "subsampling": "4:2:2",
  "restart_mcus": 10,
  "max_frame_bytes": 262144,
  "huffman_sha256": "532fd667aa5541439e4fc89f189259b1b137993ca5dfcbb6970ab411aee79cdf"
}
```

These are **exploratory** values. The table fingerprint is SHA-256 over DHT table
definitions (selector, 16 code counts, symbols), sorted by selector, excluding
marker/segment lengths. Replace it with the accepted decoder sample fingerprint;
do not assume a decoder supports these values. The default profile has no pinned
fingerprint. Actual JPEG output is inspected for SOF0/8-bit three-component
YCbCr, 8-bit DQT 0/1, DHT selectors 0/1/16/17, one interleaved scan, subsampling,
DRI, restart sequence/count, exact EOI, frame-size bound, and software decode.
The header/restart inspector does not independently decode MCU entropy or prove
each restart's entropy position; receiver validation remains necessary. The
model's deadline is predicted completion; Windows scheduling can overshoot it,
and actual host frame ages are logged rather than treated as real-time guarantees.
This lab accepts a narrow JPEG subset; it does not validate an H.264 bitstream.

Pillow's documented JPEG options are the encoder interface, while emitted bytes
are the conformance evidence. See [Pillow JPEG documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg)
and [PyAV](https://pyav.org/docs/stable/). Dependency versions are locked locally.

## Deterministic receiver assets

`fixtures/` contains five source IDs (0, 1, 29, 30, 255), PNG canvases, 15 JPEGs,
and a versioned integrity manifest. Regenerate with:

```powershell
py -3.11 -m uv run --locked python make_assets.py --output artifacts\regenerated
```

Tests compare regenerated manifests to the committed reference. Review binary
and hash changes intentionally after dependency upgrades. Fine detail, moving
square, RGB bars, and a low-32-bit frame-ID patch test different receiver paths.
The frame-ID patch begins at source x=0,y=680; the canvas transform also applies
to it. Exact compressed-byte hashes are portable integrity checks; host-decoded
RGB hashes are informational because hardware IDCT rounding may differ.

## Sunshine integration gate and Windows native build

At inspection, `C:\msys64\msys2_shell.cmd`, CMake, and the UCRT64 compiler were
absent. The installed `SunshineService` was running from `C:\Program Files\Sunshine`.
No native Sunshine build, installation, service restart, or Moonlight session
was attempted. `src/` and stock protocol behavior are unchanged.

After the standalone receiver gate in the [protocol draft](protocol/0.1.0-draft.md)
passes, use a separately built candidate with its own configuration/state and
ports. `src/nvhttp.cpp` advertises stock codec capabilities, `src/rtsp.cpp` parses
video format/launch configuration, and `src/video.cpp`/`src/stream.cpp` connect
encoding and transport. A JPEG extension must have explicit server opt-in,
paired-client acceptance, a distinct identity/transport, and rejection of unknown
or mismatched capabilities. Merely adding a fourth integer to `videoFormat` is
insufficient; current encoder and packet assumptions must be audited together.

Install MSYS2 at `C:\msys64`; update it and install the UCRT64 dependencies listed
in the repository's [Windows build instructions](../../docs/building.md#windows),
including native Node.js for web assets. Record `pacman -Q`, Node, CMake, compiler,
and submodule revisions with build results. No MSYS2 packages were installed by
this milestone. From the candidate root, the required command forms are:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake -S . -B cmake-build-gamebub -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_TESTS=ON -DBUILD_DOCS=ON'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub --parallel 4'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub/tests/test_sunshine.exe'
```

These native commands are instructions for the later integration milestone,
**not verified build results**. Initialize all pinned submodules first. After any
native code changes, run `uv run --locked lb-update-clang-format` from the root
and inspect the diff. Add GoogleTest coverage through `tests/tests_common.h`,
following AGENTS.md include groups. Never run an installer, install a service,
reuse the installed configuration, or stop the working instance for these tests.

Required compatibility matrix before integration is delivered:

| Client/configuration | Required behavior | Current evidence |
| --- | --- | --- |
| Stock Moonlight; extension off/on | Existing pairing/launch/input and H.264/HEVC/AV1 behavior | Source unchanged; runtime tests pending |
| Experimental client; server off | JPEG request rejected | Not implemented |
| Experimental client; mismatched version/limits | Clean rejection before video | Not implemented |
| Experimental client; mutually accepted JPEG | Exact approved JPEG and packet layout | Receiver agreement pending |
| Video-only experimental client | No audio requirement; launch/input preserved where practical | Not implemented |
| Mixed clients/reconnect | No shared codec state leakage, stale session data rejected | Not implemented |

See [HANDOFF.md](HANDOFF.md) for the concrete receiver questions and
`measurements/` for host-only results. Detailed moving-game footage and a
physical receiver are required to complete the remaining measurements.

## Repeatable Big Buck Bunny input

The standard moving-video benchmark uses the first 30 seconds of the Renesas RZ
1080p/30 fps sample, pinned to repository revision
`d2bd12a41b496816ddb3dc040107690b38226bf1`. Blender's server rejected the download
from this environment; the mirror copy is identified by exact bytes below.
It includes opening/title material and is not an action-game stress test.

Attribution: (c) copyright 2008, Blender Foundation / www.bigbuckbunny.org.
[Original license and attribution](https://peach.blender.org/about/): CC BY 3.0.
[Mirror provenance](https://github.com/renesas-rz/media/blob/d2bd12a41b496816ddb3dc040107690b38226bf1/Big_Buck_Bunny/README.md)
documents the trim and frame-rate conversion. No movie bytes are committed here.

From `tools\gamebub`:

```powershell
New-Item -ItemType Directory -Force artifacts\media | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/renesas-rz/media/d2bd12a41b496816ddb3dc040107690b38226bf1/Big_Buck_Bunny/big_buck_bunny_1080p_30fps_30s.mp4' -OutFile artifacts\media\BigBuckBunny-1080p30-30s.mp4
Get-FileHash artifacts\media\BigBuckBunny-1080p30-30s.mp4 -Algorithm SHA256
py -3.11 -m uv run --locked python host.py --clip artifacts\media\BigBuckBunny-1080p30-30s.mp4 --output artifacts\bbb --frames 900 --fps 30 --quality 75 --link-mbps 20
```

Expected size: 19,068,285 bytes. Expected SHA-256:
`f03e635f0d24cdd8b7b482758b16f14eb0cbfa1056c23611a3a72cf3ff039ced`.
Run benchmarks without coverage, tests, or another benchmark concurrently. The
installed Sunshine service stays running, so this is the working-host environment,
not an otherwise idle isolated machine.
