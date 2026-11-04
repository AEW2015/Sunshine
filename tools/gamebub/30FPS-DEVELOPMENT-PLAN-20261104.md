# Sunshine / Windows plan for verified 30 fps

Prepared 2026-11-04. This is the next-stage plan; unchecked gates are unverified.
It supersedes the older JPEG rate-escalation sequence for custom-codec work.

## Target and current baseline

Target: 720x480 full-color canvas, centered 720x405 active 16:9 image, 30 unique
presentations per second on MoonBub, followed by working PC audio and controller
input. Preserve the pinned integer placement/rounding. Do not lower resolution
or count repeated display refreshes as delivered frames. Defer 60 fps.

Windows baseline is Sunshine commit `19cdd7080e7ee181b9bd7a73f4ba5ac5400a36fc`,
branch `gamebub/windows-jpeg-retry-20261103` in `AEW2015/Sunshine`. Reference
MoonBub is `27a4dde6a7e2ea4fab09d892551ef542f05c8965`; review newer receiver
work separately and record any replacement pin before using it.

Completed: native GM01/CP02 encoder, HP01/HR01 patches, AR03 whole-frame cap,
mandatory candidate policy, body decoder and exact AF03/bank conformance.
Twenty isolated encoder cases match bytes; ten mandatory cases exercise
thirteen attempts. Forty-two native tests pass; Python completed 372 tests with
five existing skips. These establish software correctness, not streaming speed.
SR01 encoding, persistent analysis caching and live custom transport are absent.

Preserve the original checkout, installed Sunshine service and working JPEG/AV
baseline. Build and test the candidate separately. Never label custom data
H.264 or JPEG. All Windows native build/test commands use MSYS2 UCRT64 and
`cmake-build-*` directories; see [build instructions](V20-DEVELOPMENT.md).

## Work packages and exit gates

| Order | Owner | Deliverable | Exit gate |
| --- | --- | --- | --- |
| 1 | Windows + MoonBub | Pinned live wire/profile and recovery contract | Both implementations and golden transcripts agree; implemented versus proposed fields identified. |
| 2 | Windows | Native ownership/credit state machine and offline replay | All pinned transcripts plus fault injection pass with bounded storage and exact release/publication rules. |
| 3, parallel with 2 | Windows | Sustained native encoder/capture benchmark and measured optimizations | Correct output preserved; all attempts/costs counted; a 30 fps workload has bounded queues and adequate measured headroom. |
| 4, parallel with 2/3 | MoonBub | FPGA-only and concurrent receiver throughput evidence | Decoder/presentation and memory/transport can sustain the required initiation interval without growing backlog. |
| 5 | Windows + MoonBub | Negotiated standalone custom sender/receiver | Fixture and short low-rate hardware tests reconcile every frame and recover from defined failures. |
| 6 | Windows + MoonBub | Video-only 30 fps qualification | Rate ladder and 30-minute moving-content gate below pass. |
| 7 | Windows + MoonBub | Audio/input coexistence | Same video gate with audio and controller active; audio/input results reported separately. |
| 8 | Windows | Dedicated experimental Sunshine mode | Explicit negotiation, normal-client compatibility, startup/shutdown/recovery tests pass in a separate build. |

### 1. Freeze the live contract

Confirm capabilities, dimensions, map/HUD profile, frame cap, packet/chunk
layout, CRC coverage, timestamps, epoch/frame identities, ports and reset/rekey.
Start from the pinned GF03/FG19/PC18/QC18/AF03 kit; do not assume its offline
model is already deployed receiver firmware. Do not retrofit it into MSV1
without an explicit negotiated endpoint. Keep AV v1 audio/input separately
sequenced; agree lifecycle interaction rather than silently changing it.

Distinguish packet-buffer credit, request completion, frame-slot release and
decoded-reference publication. FINISHED must not free frame storage; RELEASE
must follow real drain; only validated AF03 publishes the reference. Preserve
the agreed transaction/token/slot bounds. Unknown outcomes retain ownership
until defined recovery proves it safe to release.

### 2. Implement and test ownership before network streaming

Replay the pinned 1,725-message transcript and verify exact expected state.
Add deterministic loss, duplication, reordering, delayed replies, wrong
kind/slot/epoch/tag, sequence rollover boundaries, CRC/truncation, exhausted
credit, cancellation and disconnect/restart tests. Assert bounded memory,
no double release, no reader/DMA use after release and no publication from an
incomplete or rejected frame. Record seed/transcript and final ownership state.
Use the existing native encoder as a builder, not a fabricated byte-count model.

Then add a localhost receiver emulator using the agreed packet format, bounded
queues and configurable receiver service delays. Run a ten-minute fault soak;
all frame outcomes must reconcile, with no leaked ownership or fabricated
credit. Reconnect must explicitly invalidate or re-establish reference state.

### 3. Benchmark, then optimize Windows

Use repeatable detailed moving gameplay plus live desktop capture. Record
source identity/hash, license where distributed, frame range and duration.
Keep easy and complex scenes separate. The twenty isolated fixtures remain
correctness oracles, not a sustained benchmark sequence.

Measure capture, letterbox/scaling, immutable source preparation, HUD coding,
RGB-to-YUV, forward transform, each quantization/entropy attempt, inverse/tag
work, candidate validation, discard, queue age and send time. Record actual
complete bytes, map, patch bytes, CPU, memory and p50/p95/p99/max stage times.

Optimize in this order, retaining golden/regression checks after each change:

1. Reuse source conversion/forward analysis across the four map attempts while
   retaining immutable frame identity and exact frozen arithmetic.
2. Avoid repeated allocations and copies with bounded reusable working storage.
   Candidate leases must prevent stale or cross-frame reuse.
3. Profile patch coding and tag/validation costs; reuse only work whose full
   source/reference/profile identity is proven. Do not remove integrity checks
   merely to obtain a faster benchmark.
4. Consider SIMD or bounded worker parallelism only where profiling justifies it.
   Require bit equality and cancellation/ownership tests.
5. Add SR01 encoding only after a measured benefit and decoder-contract check.

Always include losing attempts and cache misses. Report cold and warm behavior.
At 30 fps each bottleneck must sustain one frame per 33.33 ms; pipeline latency
may exceed this if overlap sustains throughput. Aim for headroom, not an average
that barely meets the deadline. Drop stale unsent candidates safely; never
abandon an owned transaction without the negotiated recovery procedure.

### 4. Receiver and bandwidth prerequisites

MoonBub must measure local decode/presentation first, then concurrent Wi-Fi,
queueing, QSPI, SDRAM and scanout with frame-correlated traces. Require measured
initiation intervals and backlog behavior, not just one-frame latency or
isolated QSPI bandwidth. Tag/checksum and presentation work must be included.

The old 2 Mbps cap is unsuitable for the current 30 fps workload. At the
49,152-byte cap, AR03 bodies alone need 11.80 Mbps at 30 fps. Actual radio load
also includes chunk/control traffic, reverse feedback, audio and retransmission
if negotiated. This is a budget calculation, not measured Wi-Fi capacity.
Set the test rate from measured useful concurrent throughput with headroom;
negotiate lower frame sizes/quality if it is insufficient. Keep resolution fixed.

### 5-7. Hardware test sequence

Before each run, record exact host/firmware/FPGA hashes, active overlap mode,
queue limits, viewport, endpoint/source IP, profile, frame-ID range and starting
counters. Verify the receiver accepts the actual sender. Start continuous host
packet/frame logs and receiver traces before transmission; use a camera for
visible update/geometry checks. Do not compare independent host/receiver clocks
by subtraction; correlate frame IDs and use synchronized or optical latency
measurement.

1. One known deterministic frame: verify packet acceptance, exact reconstruction,
   reference acknowledgement, display geometry and release.
2. Short low-rate key/P/promotion sequence: check reference evolution and one
   controlled recovery. Use a test session separate from the working baseline.
3. Video-only moving-content ladder: 60 seconds each at 5, 10, 15, 20 and 30 fps.
   Freeze content/profile for comparisons; change one pacing/quality variable
   per experiment. Stop escalation when a bottleneck appears and preserve its
   first frame-correlated trace.
4. Five minutes at 30 fps, then thirty minutes across detailed, moving scenes.
5. Repeat with audio and controller input. Preserve audio sequence/drain counters,
   underruns, input release-on-disconnect and measured control responsiveness.
   Give timely audio/input bounded service without starving video indefinitely.

Proposed initial 30 fps qualification gate, to agree with MoonBub before testing:

- At least 29.9 distinct presentations/s over the measured steady-state window;
  all scheduled slots, host skips/partials and receiver outcomes reconcile.
- No progressive backlog, silent freeze, reference corruption, core fault,
  buffer overflow or scanout underrun. No unexplained frame outcomes.
- Record frame-interval p50/p95/p99/max and investigate any steady-state gap
  over 100 ms; average FPS alone is insufficient.
- Report visible quality, selected-map distribution, requested HUD coverage,
  bitrate and source-to-display latency with the measurement method. Use an
  agreed per-game quality baseline so 30 fps is not achieved by unusable output.
- For combined operation, report audio underruns/gaps and input latency; do not
  call the combined experience qualified if video passes but audio/input fails.

These are proposed acceptance thresholds, not achieved results. Failed runs
remain evidence; do not silently retune settings inside a comparison.

### 8. Sunshine integration after the standalone path passes

Add an explicitly negotiated experimental mode with a minimal finite-session
configuration. Reuse capture, audio and input components where practical.
Keep video-only diagnostics and preserve ordinary Moonlight pairing, launch,
codec negotiation and streaming behavior. Do not remove shared functionality
from stock paths to slim the experimental path.

Test supported/unsupported capabilities, fallback, normal-client negotiation,
audio/input coexistence, disconnect/reconnect, clean shutdown and bounded worker
cleanup. Run the candidate separately; replacing/restarting the installed
service is outside this development plan.

## Immediate next tasks

- [ ] Send [the receiver prompt](MOONBUB-30FPS-PROMPT-20261104.md).
- [ ] Pin the jointly confirmed contract and transcript set.
- [ ] Implement Windows ownership replay while profiling sustained native encode.
- [ ] Obtain FPGA-only and concurrent receiver throughput measurements.
- [ ] Proceed to a short hardware fixture only when both ends implement the same
  contract; do not start another long JPEG run as a substitute for these gates.

Every report must separate encoding benchmark, localhost transport and verified
hardware presentation. Save resolution, FPS, quality, bitrate, latency method,
duration, hashes, counters and limitations. Never describe a target as achieved.
