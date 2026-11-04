# Game Bub host laboratory

This is an experimental host laboratory, pending receiver testing. `msv1.py`
sends one fixture, while `stream_sender.py` streams a clip or desktop using the
receiver's video-only UDP test protocol. Neither is an integrated Sunshine JPEG
mode or a receiver playback claim.
The installed Sunshine service and original checkout remain unchanged.

The latest application-specific handoff is
[`handoff/gamebub-app-codec-v14-20261103`](https://github.com/AEW2015/Sunshine/tree/handoff/gamebub-app-codec-v14-20261103),
paired with [Moonbub v14](https://github.com/AEW2015/moonbub/tree/handoff/gamebub-app-codec-v14-20261103).
Earlier handoffs remain frozen. Read the
[v14 results](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v14-20261103/docs/custom-codec-prototype-v14-2026-11-03.md)
and [HEVC/AV1 FPGA plan](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v14-20261103/docs/gamebub-hevc-av1-fpga-plan.md).

V14 implements actual AR01/AF01 acknowledged reconstructed-P references and
separate SR01 zero/DC/full residual syntax at 720×480. Recent references reduce
native mean bytes 25–29% versus a same-envelope immutable reference control;
bounded background pruning saves about 13% with explicit quality/host-work costs.
These gains are separate, not multiplied or combined in one implemented stream.

Bank-specific overlap then reaches 30 modeled IDs/s in a five-second held-out
window at 720×480. It delivers the same 179 source IDs as the immutable initial-key
control, with 34.63% smaller mean bodies and 34.57% fewer forward GF02/UDP/IP bytes.
This short base-video scenario has no SR01 or exact UI integration and does not
prove physical/native 30 fps or a production refresh policy.

Finite feedback experiments charge promotion reconstruction, tag generation,
transport and publication. They expose the cost of all-pending drains, test a
bank-specific alternative, and enforce expiry/deadline precedence during paid
ACK and decoder completion. Two retained YUV banks plus scratch/output/pending
storage still need a native memory and bandwidth implementation. No physical
30 fps, ESP32 receiver or FPGA decoder fit is proved.

The new Python sources, protocol contracts, tests and retained evidence live in
the paired Moonbub branch, including `experiments/verify_prototype_v14.py`.
This Sunshine fork contains the host handoff reference, not an integrated encoder
mode. AR01/AF01/SR01 are experimental dialects unsupported by installed peers.
Use the [current application-specific plan](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v14-20261103/docs/gamebub-application-specific-codec-plan.md)
for unifying residual/reference syntax, exact UI and native implementation.
V13 below is historical.

V13 implements real cap-before-commit source reuse: native combat preparation
falls 20.30→11.54 ms, while the distinct second sample pays 0.67% overhead.
Four-entry exact RGB565 region reuse cuts combat selector time 5.78→1.68 ms
and records 176 hits while the full image changes, with identical full packets.
Motion screening avoids costly real-source BM search at the cost of giving up
small byte savings. Both cache optimizations are conditional, not universal gains.

The measured-stage finite source-cache/fast-decoder run still falls short: the
180-distinct-frame UI comparison improves 119→121 strict and 121→123 eventual
presentations. A separate bounded-credit study integrates all three optimizations
and compares two versus three host transactions with unchanged two-slot receiver
ingress and three framebuffer roles. None of the Python models qualifies target
hardware memory, live transport or sustained physical 30 fps.

The new implementation, results, tests and `experiments/verify_prototype_v13.py`
live in the paired Moonbub branch. This fork carries the host handoff reference,
not an integrated native Sunshine mode. Use the
[current plan](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v13-20261103/docs/gamebub-application-specific-codec-plan.md)
for native-port, protocol and memory-service gates. V12 below is historical.

V12 keeps the primary 720×480 / 30 fps requirement. Measured exact zero/DC bypass
plus cached tables cuts full Python GM01/HG01 receive by approximately 8–11% with
identical pixels and reference planes. Exact last-source reuse produces identical
full GM01 packets: preparation improves 24.73→13.95 ms with 26 hits in the combat
sample, but changes 24.89→25.25 ms with no hits in the second sample. This PC cache
is not yet integrated into the finite candidate/commit controller. Blindly trying
both actual motion candidates roughly triples preparation for zero or small real
bit savings; do not enable that policy as a default.

Controlled 720×480 refresh scenarios remove a mid-window key and gain two strict
deliveries per 60-ID native window, without any 60/60 strict pass. The declared
service table remains separate from measured call wall times and target timing.
The new scheduler also rejects late ACKs after requested expiry while retaining
read ownership through drain. Older scheduler evidence stays frozen. Native
decoder porting, proper host-cache admission, a causal motion gate and versioned
reference-state work are next; sustained physical 30 fps remains unproved.

All new Python implementations and retained results live in the paired Moonbub
branch, including `experiments/verify_prototype_v12.py` and its provenance manifest.
This Sunshine branch carries the host handoff documentation, not an integrated
Sunshine codec mode or binary. The installed Windows service is unchanged.

V11 integrates actual HP01/HR01 temporal UI selection with complete HG01/GM01
bodies through finite GF02 and outer-content-bound GA01 software replay. Compact
temporal row patches save34.44% complete bytes versus HP01 at identical exact
area. BM01 bounded block prediction is a separate format with mixed real results
and paid search/vector overhead; it is not a universal replacement.

The primary product target remains **720×480 coded video at30fps**, preserving
720×405 active16:9 game content. The512×288/20fps cases are diagnostic comparisons.
The [updated plan](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v12-20261103/docs/gamebub-application-specific-codec-plan.md)
prioritizes compression, native decoder service and key/ACK/refresh scheduling
at the primary resolution. Current high-resolution replay remains below target;
no hardware30fps result or default refresh policy is qualified. The original
v11 handoff remains a frozen experiment snapshot.

The FPGA study separates constrained conformant HEVC, full AV1 porting and custom
inspired codecs. Existing public full AV1 builds exceed this Artix-7 unchanged;
lower resolution does not proportionally shrink fixed RTL/tool/state logic.
There are57 passing component/audit tests. These changes add no installed
Sunshine output mode, target firmware or bitstream and leave the installed
Windows Sunshine service untouched.

This performance-study work is published on
[`AEW2015/Sunshine:study/30fps-sim-20261102`](https://github.com/AEW2015/Sunshine/tree/study/30fps-sim-20261102).
The matching FPGA/firmware research and [developer handoff](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/dev-handoff-2026-11-03.md)
are on `AEW2015/moonbub:study/30fps-sim-20261102`. The Windows checkout and
`gamebub/host` clone instructions later in this document describe an earlier
host baseline; use the study branch above for these experimental additions.

The proposed custom-codec research track is described in the
[codec audit and revised plan](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/codec-development-audit-plan.md).
Tile/RLE and DPCM remain candidates to benchmark against the current JPEG
path; this document does not enable a new Sunshine codec mode.

The [Python design prototypes and measurements](https://github.com/AEW2015/moonbub/tree/study/30fps-sim-20261102/experiments/python-codec-study)
now compare these candidates against this laboratory's exact JPEG encoder.
They add offline compact-index/zero-run experiments, dependency-aware temporal
delivery, and a bounded JPEG wire-budget search. The search is a research
helper in Moonbub, not a new `stream_sender.py` option. The linked
[memory-service model](https://github.com/AEW2015/moonbub/tree/study/30fps-sim-20261102/experiments/python-memory-study)
uses recorded JPEG sizes to compare storage scenarios; neither model proves
real Windows capture, ESP32 forwarding, physical memory service or display FPS.

The [custom-codec follow-up report](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/custom-codec-prototype-progress-2026-11-03.md)
adds MED and fixed-Q14 transform comparisons, bounded sample stripes and a
finite-slot/framebuffer delivery model. The tested custom formats still lose
to receiver JPEG on rate/quality. Conditional steady model rates near30 fps
do not remove its phase-dependent count/latency failures or qualify hardware.
These research helpers do not change the installed Sunshine service or add a
new sender option.

[Iteration3](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/custom-codec-prototype-v3-2026-11-03.md)
adds DC/AC contexts, compressed-byte stripe decoding and a temporal transform
prototype with epoch-bound commit ACK checks. Short temporal samples use fewer
bytes than receiver JPEG at slightly lower PSNR; real-time feedback, memory,
visual quality and integration gates remain open. MT02/SS01 are research
formats and cannot be sent through this JPEG-only tool as installed modes.

[Iteration4](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/custom-codec-prototype-v4-2026-11-03.md)
actually re-encodes after capture skips under virtual ACK/cap timing and tests
an immutable-anchor overlap profile. It records conditional rate improvements,
cap/quality failures and Python service costs slower than real time. No
installed Sunshine mode, receiver support or physical30 fps is established.

[Iteration5](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/custom-codec-prototype-v5-2026-11-03.md)
adds actual byte-identical faster host preparation, a reference-only background
anchor protocol and causal quality restoration. Immutable-anchor P preparation
has23–25 ms medians on the Python host; unchanged key means remain78–111 ms.
The short conditional rate gains and synthetic recovery-quality result do not
establish sustained30 fps or add a Sunshine/ESP32/FPGA mode. Per-kind native
service, physical reference memory and integration remain implementation gates.

[Iteration6](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/custom-codec-prototype-v6-2026-11-03.md)
reduces host key preparation with lazy verification, fast entropy and token
lists: a paired24-key sample improves33.18→27.67 ms mean, with two calls still
over33.33 ms. Per-selected-packet measured Python services now drive the finite
model; short diagnostic counts remain28–29 with assumed8 ms receive and21–24
with measured Python receive. Exact arithmetic widths and a small/negative
narrow-integer timing result are retained. These are offline software studies,
not an installed streaming mode or physical30 fps/target DSP qualification.

[Iteration7](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v7-20261103/docs/custom-codec-prototype-v7-2026-11-03.md)
adds a compatible word coefficient reader (paired Python receive8–12% faster),
a new independent-frame macroblock quality-map codec, and exact dirty-tile
experiments. At nearly matched uniform16 bytes, declared priority-region PSNR
improves1.47–2.51 dB on the short real samples while background quality falls;
the237–395 ms offline search is not a live rate controller. The
[application-specific plan](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v7-20261103/docs/gamebub-application-specific-codec-plan.md)
selects a new temporal-residual plus ROI profile as the next prototype. These
formats require matching receiver support and do not add an installed Sunshine
mode or prove physical30 fps. The v6 handoff remains a separate snapshot.

[Iteration8](https://github.com/AEW2015/moonbub/blob/handoff/gamebub-app-codec-v8-20261103/docs/custom-codec-prototype-v8-2026-11-03.md)
implements actual GM01 temporal residuals plus priority quantization, bounded
two-candidate admission and shared transforms. ROI8/background16 improves
priority-region PSNR1.39–2.14 dB versus uniform GM01 at4.2–10.5% more bytes in
the codec sample. Normal preparation means20–24 ms exclude acquisition/receiver/
transport; fallback tails remain over33.33 ms. A conservative byte bound cuts
eight seeded-noise rejects113.7→25.0 ms without entropy serialization, with no
general normal/pressure speedup. The new GM01/GF01 golden vectors are in-process
software evidence, not an installed sender/firmware mode or physical30 fps.

Its [external-memory follow-up](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/docs/external-memory-audit-plan.md)
defines the SRAM/SDRAM qualification, queue-ownership and measured bandwidth
gates that must precede any receiver-buffer or frame-cap change.

For the experimental FPGA design with 48 KiB compressed-frame banks, the
standalone sender can be run with `--max-jpeg-bytes 49152`. It drops a JPEG
that exceeds the configured limit before sending any packet, records an
`oversize_drop`, and reduces quality for subsequent frames. It never truncates
the JPEG. The default remains the existing 262,144-byte MSV1 limit; select a
smaller cap only when the receiver actually implements that capacity. The cap
does not reduce the 720×480 canvas dimensions and does not guarantee a given
frame rate or image quality.

The optional `--jpeg-retry-quality-drop 10` retries an oversized JPEG once at
ten quality points lower (never below `--min-quality`). It drops the frame if
that still exceeds the cap. Retries are disabled by default. A retry costs CPU
time; the pipeline still discards a frame that is past `--max-age-ms` before
sending, so a successful retry is not guaranteed to reach the receiver in time.

Use `--frame-telemetry PATH` to write a second, bounded JSONL file in the
normalized format accepted by Moonbub's
[telemetry correlator](https://github.com/AEW2015/moonbub/tree/study/30fps-sim-20261102/telemetry-study).
By default the run uses a fresh UUID; `--telemetry-session-id` can set an ID
coordinated with receiver instrumentation. Each sampled capture gets a stable
session-local `frame_seq`, the actual 32-bit wire `frame_id`, and host monotonic
capture-start/end nanoseconds. Capture start is sampled before source
acquisition; for a clip that skips pacing slots, this includes decoding the
discarded clip frames. Capture end is sampled after acquiring/decoding the
selected frame and fitting/scaling it to the sender canvas. Thus capture-to-send
includes source and canvas preparation, encoding, queueing and packet submission;
it is not camera-only capture time. The existing Unix wall-clock wire timestamp
is retained separately as `capture_wall_us`. A `send` record is written only
after the local sender finishes submitting all frame datagrams; this is not
receiver ingress or presentation. Capture records without a send record expose skipped/replaced/failed frames to the
correlator, but do not identify a drop cause. Unmaterialized pacing slots have
no capture sequence and appear as wire-ID gaps. `--telemetry-evidence-kind`
defaults to `simulated`; use `hardware` only for a run actually performed with
the identified hardware. The independent output uses the existing asynchronous
logger's queue and 64 MiB file bound. Telemetry is disabled by default and does
not affect frame scheduling, packet contents, feedback handling, or the existing
event log. The resulting file can be passed directly to `correlate.py`; no
presentation event or cross-clock calibration is fabricated.

`frame_seq` and the telemetry session ID are host-only metadata; neither is
transmitted in MSV1. Receiver instrumentation must use the coordinated session
ID and map its observed 32-bit wire IDs to the host capture sequences. Preserve
the per-session mapping across wire-ID wrap; a raw frame ID alone is ambiguous
after wrap. This option does not add a protocol field or receiver stage.

Example:

```sh
python stream_sender.py 192.0.2.10 --clip game.mp4 --frames 300 --fps 30 \
  --log run-events.jsonl --frame-telemetry frame-telemetry.jsonl \
  --telemetry-evidence-kind simulated
```

The session UUID and telemetry logging drop/error counts are included in the
sender's final stdout summary. A saturated log can omit records; check those
counters before correlating.

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
Matched feedback events include the receiver's cumulative received and dropped
counts. A status-0 heartbeat may occur before a frame finishes; check counter
changes and the handheld's independent decode/display counters.
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
