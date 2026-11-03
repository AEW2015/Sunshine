# Game Bub host laboratory

This is an experimental host laboratory, pending receiver testing. `msv1.py`
sends one fixture, while `stream_sender.py` streams a clip or desktop using the
receiver's video-only UDP test protocol. Neither is an integrated Sunshine JPEG
mode or a receiver playback claim.
The installed Sunshine service and original checkout remain unchanged.

See [the optimization and validation backlog](OPTIMIZATION-PLAN.md) for
prioritized pipeline, audio, controller, and compatibility work and the tests
and hardware measurements each item needs.

An optional, default-off native MSV1 packet serializer has been built and tested
against the receiver's golden packets. It does not enable a Sunshine streaming
mode; see [native build evidence](measurements/native-msv1-build.md).

The target product is one dedicated 720×480/30 fps video, audio and simple
button mode, rather than a general Moonlight feature set. Its exact codec and
audio profile await the receiver agent; see the
[current protocol draft](protocol/0.5.0-draft.md). The wider options below are
laboratory controls for experiments, not proposed end-user modes.

`realtime.py` contains a latest-video slot, bounded audio queue, logical
button-state tracker and a 12-button Sunshine gamepad flag mapping. Audio drops
signal discontinuity; disconnect returns held buttons for release. These
components are tested independently and are not yet
connected to a capture device, network transport, or Windows input injection.
They use host monotonic timestamps. Stop old producers and gate old sessions before
resetting the objects; they do not themselves identify or authenticate a session.

`pipeline.py` is an experimental two-worker primitive: it copies a prepared
720x480 RGB capture, keeps at most one waiting raw frame and one waiting JPEG,
and checks capture age before encoding and sending. Its caller must pace capture,
provide receiver-conforming encoding and a deadline-aware sender, handle feedback,
and ensure callbacks return promptly: `close()` drains and joins both workers but
cannot interrupt a blocked callback. It does not itself send network traffic,
adapt quality, connect to Sunshine, or establish receiver playback.
Capture timestamps supplied to the default pipeline must come from
`time.perf_counter_ns()`, the same high-resolution monotonic clock used by its
workers and packet pacing; Unix timestamps remain separate protocol metadata.

## Windows setup and verification

Development checkout: `C:\ai\sunshine-gamebub`, branch `gamebub/host`, upstream
base `3d6e1d60`. The branch belongs to the original local repository through
`git worktree`; keep the original checkout available. Install Git, Python 3.11,
and uv. On this machine uv was installed with `py -3.11 -m pip install --user uv`;
`py -3.11 -m uv` works without changing PATH.

Published fork: https://github.com/AEW2015/Sunshine/tree/gamebub/host.
For a fresh machine, clone to an unused directory:

```powershell
git clone --branch gamebub/host --recurse-submodules https://github.com/AEW2015/Sunshine.git C:\ai\sunshine-gamebub-clean
Set-Location C:\ai\sunshine-gamebub-clean
```

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
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage run -m unittest -v'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage run --append host.py --output artifacts/coverage-entry --frames 1 --link-mbps 1000'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage run --append make_assets.py --output artifacts/coverage-fixtures'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage run --append msv1.py 127.0.0.1 --jpeg fixtures/receiver-pattern-720x480-420-q65.jpg --deadline-ms 0.001 || test $? -eq 2'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage run --append stream_sender.py --help'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage run --append reference_loopback.py --help'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked coverage report --fail-under=100'
```

Use a fresh output directory for each run; measurement files are never overwritten.
The appended coverage commands exercise CLI entry points under instrumentation;
do not use that run for performance measurements. Regression tests use controlled
clocks for deterministic overload behavior, real JPEG encode/decode, a generated
60-Hz video input, and fixture regeneration checks. Coverage measures `host.py`
`make_assets.py`, `realtime.py`, `seed_pairing.py`, `msv1.py`, `pipeline.py`,
`stream_sender.py`, `controller.py`, `quality.py`, `event_log.py`, and
`reference_loopback.py`.

`controller.py` tracks the 12-bit feedback snapshots and logs translated
Windows-style gamepad flags. It rejects old video-frame identities, emits a
neutral state after 500 ms without accepted input feedback, and requires a
newer frame after timeout. It does not create a Windows controller or inject
input. MSF1 has no input sequence number, so reordered button snapshots sharing
one video frame cannot be distinguished; an ordered, authenticated input
session must be agreed and tested before using these states to drive games.

## Continuous video test sender

On the intended trusted test LAN, after the receiver team enables Test MJPEG
and supplies its address, replace the example address and input path:

```powershell
py -3.11 -m uv run --locked python stream_sender.py 192.168.1.50 --clip C:\clips\game.mp4 --log artifacts\game-run.jsonl --frames 900
py -3.11 -m uv run --locked python stream_sender.py 192.168.1.50 --desktop --log artifacts\desktop-run.jsonl --frames 300
```

The optional `--desktop-filter box` uses a faster resize filter in one static
desktop microbenchmark, but its visual quality on moving games is unverified.
The default stays bilinear; see [DXGI probe results](measurements/dxgi-desktop-probe.md).

Use a new log filename each run. The default is 30 fps, 20 Mbps of MSV1
datagrams, 200 ms maximum host age and adaptive JPEG quality 20..75. Lower
network-layer overhead is not included. It captures or reads frames, scales to
the 720x480 canvas, uses one latest raw and encoded slot, and logs encoded sizes,
quality, encode time, frame/queue age, sends and matching feedback. Summary FPS
and bitrate include a 300 ms final feedback grace period. Exit status 0 means at
least one matching accepted ingress response, 2 means none; either result can
include drops and does not establish FPGA decode or display. Inspect the log and
receiver output. The test receiver's restart/session rules apply to frame IDs.
The pinned firmware locks onto the first sender's IP **and UDP source port**
for its test session. Restarting the sender with a new ephemeral port will be
ignored until the receiver test session is restarted. For a coordinated host
restart within the same receiver session, use `--source-port` to retain the
same local port and `--start-frame-id` to choose an ID newer than every frame
previously started, using the receiver's wrapping serial-number rule. The
caller must know the last attempted ID; logging may be incomplete after a crash.
Otherwise restart the receiver's Test MJPEG session before restarting the host.
Each actual encoder output is checked for the exact receiver profile and decoded
in software once; immutable verified bytes are then packetized without repeating
that validation. Other supplied JPEG bytes are validated before transmission.

JSONL events are written by a separate bounded worker so file writes do not
hold the sender/feedback lock. The queue is limited to 256 KiB and the log file
to 64 MiB; records may be dropped when either bound is reached or the file
fails. The printed final summary reports written and dropped records and any
I/O error. A summary record is attempted in JSONL but can itself be dropped
when logging is saturated. Shutdown waits for the file writer to return.

The quality controller decreases promptly on oversized wire budget, send failure,
or receiver busy/drop feedback. It requires 30 consecutive small encoded frames
and recent accepted feedback before raising quality by one point. It does not
estimate or guarantee actual Wi-Fi throughput.

The socket is nonblocking. Failures and partial frames are counted, later SOF
recovers per receiver protocol, and busy/drop feedback lowers JPEG quality.
After 750 ms without matching feedback or a current-frame heartbeat, the sender
offers at most one recovery frame per second. Only feedback matching a new probe
restores normal sending. This timeout is an experimental host policy based on
the receiver's documented 250 ms heartbeat and needs physical-network testing.
It does not authenticate the peer, stream audio, inject buttons, or provide a
Sunshine mode. Use only an isolated trusted network. A
[localhost receiver-reference run](measurements/stream-reference-loopback.md)
is not a hardware measurement.

For a moving-game input, the [Xonotic recording and localhost measurements](measurements/xonotic-loopback.md)
include a source URL, license, and hash. The reference receiver is a host-process
test, not evidence of ESP32/FPGA playback.

## Send a single receiver test frame

The receiver's MSV1/MSF1 protocol is unauthenticated and video-only. Use it only
on the intended trusted test LAN after the Game Bub agent configures the receiver
and provides its IPv4 address. No keys or input are injected by this command.
The sender validates the restricted JPEG profile and reports success only after
matching ingress feedback; that does not establish decode or presentation.
Use `--source-port` to keep a fixed sender port when the receiver pins its peer;
restart the receiver session if a previous sender used a different source port.
Optionally pass `--packet-log artifacts\packets.json` to record each datagram's
frame offset, payload size and host monotonic send time. The file must not
already exist. Records are collected in memory and written after transmission;
they do not prove delivery or share a clock with the receiver.

```powershell
py -3.11 -m uv run --locked python msv1.py 192.168.1.50 --jpeg fixtures\frame-00000000-420-r0.jpg --frame-id 1
```

Substitute the actual receiver address. The selected JPEG is the exact frame-0
4:2:0 fixture that the receiver team separately verified in FPGA RTL simulation.
A new command during the same receiver
session must use a newer frame ID; the receiver resets its baseline on session
disconnect. The default sender rate is 20 Mbps including MSV1 headers, with a
200 ms frame deadline and one-second feedback timeout. Exit code 2 indicates a
deadline, dropped/busy response, or missing matching feedback. This command is a
single-fixture bring-up tool, not a clip/desktop streaming implementation.
See [the protocol draft](protocol/0.5.0-draft.md) for limitations.

To additionally compile and test the receiver's exact Rust parser on the host,
install the MSYS2 `mingw-w64-ucrt-x86_64-rust` package and clone the receiver
repository. The test reads the pinned `75f8497` revision directly through Git;
it checks the source hash, valid-frame acceptance, CRC rejection, recovery on a
new frame, missing/duplicate packets, invalid start flags, and frame-ID wrap.
It uses temporary files and no physical receiver.

```powershell
git clone --no-checkout https://github.com/AEW2015/moonbub.git C:\ai\moonbub-reference
$env:MOONBUB_REFERENCE = 'C:/ai/moonbub-reference'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python -m unittest test_receiver_integration -v'
```

The integration test is skipped when `MOONBUB_REFERENCE` is unset. The recorded
host-only results are in `measurements/msv1-firmware-parser.json` and the
`msv1-*-loopback.json` files.

## Preparing a known client without a PIN prompt

If the receiver agent confirms the ESP32 client implements Sunshine's existing
certificate-based control protocol, prepare a new state file from that device's
**public** certificate. This is optional preparation for that specific protocol;
the custom Game Bub transport and its identity mechanism are still undecided.
Do not use Sunshine's public test certificate as a device identity.

From `tools\gamebub`, with a real device public certificate and an existing,
separate output directory:

```powershell
py -3.11 -m uv run --locked python seed_pairing.py --client-cert C:\path\gamebub-public.pem --output artifacts\gamebub-candidate-state.json
```

The output must not already exist. It contains a generated Sunshine ID and one
enabled client certificate in the state format used by this Sunshine revision.
The command validates the certificate's X.509 syntax, prints its public SHA-256
fingerprint, rejects extra private-key material, and never overwrites a file.
The actual candidate must be explicitly configured to use that separate state;
this tool does not modify configuration or launch Sunshine. The paired device
must hold the corresponding private key. No real device certificate or handshake
has been tested, and this preparation does not implement a custom transport.

The stock Web UI password is separate from client pairing. This state file does
not disable the Web UI, remove its password flow, or implement passwordless
dedicated mode. An unconfigured stock Web UI can expose its setup flow. A slim
candidate needs explicit listener/UI changes and testing after receiver agreement.

## Capture and experiments

The default source is a deterministic moving pattern, not game footage:

```powershell
py -3.11 -m uv run --locked python host.py --output artifacts\patterns --frames 900 --fps 30 --quality 75 --link-mbps 20
py -3.11 -m uv run --locked python host.py --desktop --output artifacts\desktop --frames 300 --fps 30 --link-mbps 20
py -3.11 -m uv run --locked python host.py --desktop --desktop-filter bilinear --output artifacts\desktop-fast --frames 300 --fps 30 --link-mbps 20
py -3.11 -m uv run --locked python host.py --clip C:\clips\game.mp4 --output artifacts\game --frames 1800 --fps 30 --quality 75 --link-mbps 20 --save-jpeg
```

Clip frames use libswscale bilinear conversion to the fitted viewport; this is
faster in the recorded host experiment but changes resampled detail. The
deterministic image fixtures retain their existing Pillow scaling path.
Desktop capture uses Pillow `ImageGrab` on the primary display, in the interactive
user session. This is a software test path rather than Sunshine's DXGI capture.
Clips must have square pixels and strictly increasing PTS; normalize rotated or
anamorphic footage before use. Clip frames are sampled on the requested timeline;
EOF stops the run, and source starvation skips pacing slots without a queue.
Stale clip samples skip RGB conversion. The selected frame is scaled with
libswscale before conversion; image/desktop sources default to Pillow Lanczos.
For desktop only, `--desktop-filter bicubic` or `bilinear` trades resize quality
for speed. Bilinear can soften small text and fine detail; assess the actual game
image before selecting it. The selected filter is recorded in `summary.json`.
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
The header/restart inspector searches marker prefixes in native code and still
checks the same marker sequence; every encoded image also gets a software decode.
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

At the initial inspection, MSYS2 and its UCRT64 toolchain were absent. They are
now installed at `C:\msys64` for the separate candidate build. The installed
`SunshineService` continues to run from `C:\Program Files\Sunshine`; it has not
been replaced or restarted. `src/` and stock protocol behavior are unchanged.

After the standalone receiver gate in the [protocol draft](protocol/0.5.0-draft.md)
passes, use a separately built candidate with its own configuration/state and
ports. `src/nvhttp.cpp` advertises stock codec capabilities, `src/rtsp.cpp` parses
video format/launch configuration, and `src/video.cpp`/`src/stream.cpp` connect
encoding and transport. A JPEG extension must have explicit server opt-in,
paired-client acceptance, a distinct identity/transport, and rejection of unknown
or mismatched capabilities. Merely adding a fourth integer to `videoFormat` is
insufficient; current encoder and packet assumptions must be audited together.

On a fresh machine, install MSYS2 at `C:\msys64`; update it and install the UCRT64 dependencies listed
in the repository's [Windows build instructions](../../docs/building.md#windows),
including native Node.js for web assets. Record `pacman -Q`, Node, CMake, compiler,
and submodule revisions with build results. From the candidate root, the required
command forms are:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake -S . -B cmake-build-gamebub -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=ON -DBUILD_DOCS=OFF -DSUNSHINE_ENABLE_TRAY=OFF -DCUDA_FAIL_ON_MISSING=OFF -DDOTNET_EXECUTABLE='
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub --parallel 4'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub/tests/test_sunshine.exe'
```

If native Node.js is not on the build PATH, provide its `npm.cmd` with
`-DNPM=C:/path/to/node/npm.cmd`. The empty `DOTNET_EXECUTABLE` disables optional
WiX packaging when a .NET runtime exists without an SDK; remove that setting
if a configured WiX installer is required. The flags build the stock Sunshine
test baseline without the tray; they do not implement Game Bub streaming.
Initialize all pinned submodules first. After any
native code changes, run `uv run --locked lb-update-clang-format` from the root
and inspect the diff. Add GoogleTest coverage through `tests/tests_common.h`,
following AGENTS.md include groups. Never run an installer, install a service,
reuse the installed configuration, or stop the working instance for these tests.

After the test build passes, configure a separate slim release candidate without
the tray, test binaries, or generated documentation:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake -S . -B cmake-build-gamebub-release -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF -DBUILD_DOCS=OFF -DSUNSHINE_ENABLE_TRAY=OFF'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub-release --parallel 4'
```

This existing tray option skips Sunshine's tray/Qt dependency path. It does not
remove the web server, stock codecs, or pairing protocol. The release build and
its size have not yet been measured; no candidate has been installed.

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
