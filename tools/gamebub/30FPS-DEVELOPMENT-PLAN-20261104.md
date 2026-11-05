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

### Receiver coordination update, 2026-11-04

The latest operator readiness report is v27/build50, overlap/queue32. The
[20-second 5 fps video-only control](measurements/v27-control-5fps-20261104.md)
completed 100 full sends with 98 accepted replies and two rejected. The sender
is stopped. Receiver totals reconcile 98 received/decoded/presented and two
Sequence gaps, with zero application queue drops and no core fault/overflow/
underrun or observed reboot. Host timestamps show all requested offsets sent
in order; the loss/reordering location is unresolved before rate escalation.
This supersedes the installation
hold described in the earlier update below.

Earlier user status: v27 was installing, so sender traffic was on hold. V26 was the
last verified runtime: installed around 6:38 p.m. America/Denver on November 4,
with runtime ELF verification and a subsequent USB identity check. After v27
reboots, use its fresh identity/configuration/counters for the short existing
JPEG diagnostic control. Earlier unflashed-version statements below are
historical and do not require repeating the v26 installation.

The receiver team confirmed CP23/HC22/HD22 as the first complete-fixture target;
CP25 is not selected. Its ready AKD1 ROM-fed AR03/GM01/CP02 KEY diagnostic is
an earlier component image, not complete CP23 support. No complete custom
decoder/local loader has been reported for either full profile.

The receiver team's supplied coordinated plan adopts this development order.
It reports that the custom FPGA work is currently an exact reconstruction
component, not a complete parser/entropy/bank/tag/patch/scanout decoder or
qualified bitstream. Its C gateway helpers are not a deployed custom endpoint.
At that earlier update, the v22 ESP application was built but unflashed. These were receiver-reported
capabilities; Windows has not independently probed or reproduced them.

Consequently, complete custom FPGA-only throughput, concurrent receiver
throughput and the limiting performance stage remain unknown. A live custom
fixture test must wait for complete, source-bound implementations on both ends.
Receiver sources/artifact manifests must be reproducibly published before
Windows depends on a replacement revision. Coordinate hardware changes and
stream windows explicitly; this update schedules no flash or sender run.

The receiver also identifies missing physical-drain events in the 1,725-message
histories. Message replay alone cannot prove full ownership state. Gate 2 now
requires explicit model events and agreed expected states in addition to those
wire logs; simulated drain events must never be presented as hardware evidence.

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
Do not invent an ACK-of-FINISHED packet. Any change to the pinned kit requires
a jointly versioned contract and vectors rather than a unilateral extension.

### 2. Implement and test ownership before network streaming

Replay the pinned 1,725-message histories for wire parsing and ordering checks.
Separately agree a complete state transcript containing explicit ingress,
read/DMA/decode drain and publication events, expected state after transitions,
and provenance distinguishing model events from physical observations. Verify
full ownership against that transcript; do not infer drain from a message log.
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

A new [v25 motion-codec study changes the media grammar](measurements/hd22-baseline-v25-gate-20261104.md).
The receiver team has since retained CP23 for the first complete fixture;
CP25 is not selected. Its source does not establish a complete
FPGA decoder or endpoint. The native HD22 patch decoder and exact-word replay
extend the current baseline; whole HC22/CP23 transactions remain separate.

Windows now also reconstructs the [static CP23 independent-refresh subset](measurements/v24-composed-refresh-20261104.md):
AR03 key base, all four nonreferenced LEGACY HUD regions, exact complete image
hash and independently constructed JA23. Checked-in packet/ACK assets make a
local first-frame handoff concrete. This is not HD22/P-frame state conformance,
live transport or a performance result. The receiver's decoder/loader remains
the first local hardware dependency; networked testing needs both endpoints.

Windows now has [bounded host reset-control replay](measurements/v24-host-reset-20261104.md)
for the pinned nominal/loss/reboot campaigns and explicit modeled owner gates.
The published traces omit owner/drain facts, so this is not complete ownership
or receiver-reset replay. CP23/JA23 media, fresh-epoch key/full-HUD enforcement,
durable recovery and the physical decoder/endpoint gates remain open.

Windows has since added an offline RS24 parser/serializer and pinned-byte
replay of all 124 v24 controls. See [the checkpoint and reproduction steps](measurements/v24-reset-wire-20261104.md).
This closes the wire-syntax subtask only. Full reset/ownership transition replay,
CP23/JA23 media conformance and a compatible custom hardware endpoint remain open.
The WoW demo is stopped; its incomplete measurement is [recorded separately](measurements/wow-demo-20261104.md).

JPEG/AV is the existing hardware streaming path. The earlier v22 app-only demo
does not establish the current v27 runtime or readiness. Confirm post-update
source binding, identity and fresh counters before another controlled run.
The available AKD1 component artifact does not establish a complete CP23 fixture,
custom streaming receiver or custom port.

A newer offline study at MoonBub `4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`
adds CP23/JA23/RS24 profile/reset modeling with explicit drain/write/vblank
inputs. Review and pin those models/transcripts jointly as the next contract
task; do not assume compatibility with the current v20 native wire helpers or
claim an installed recovery service from the model. The older 1,725 wire logs
still do not independently prove complete ownership state.

Hardware scheduling now has a separate
[readiness request](MOONBUB-HARDWARE-READINESS-REQUEST-20261104.md) and
[published-source audit](measurements/receiver-readiness-20261104.md).
Distinguish an existing JPEG/AV check, an FPGA-only functional fixture and a
networked custom fixture. The first functional frame need not meet 30 fps;
complete compatible implementations and an agreed safe-stop window are its gate.

Windows offline progress now includes exact native transport wire codecs,
the 1,725-message wire campaign, a bounded sender intent/reply helper and
continuous generated-motion profiling with frame-local analysis reuse. See
[the implementation and measurements](measurements/v20-transport-and-generated-profile-20261104.md).
These do not close full ownership/recovery, localhost fault-soak, fresh moving
gameplay/capture or live custom endpoint gates.

- [x] Receive and reconcile the receiver team's coordinated plan; their response
  adopts the custom-first order and identifies the missing full pipeline and
  ownership-model events. This does not confirm a live contract or hardware readiness.
- [ ] Pin the jointly confirmed contract and transcript set.
- [x] Replay pinned RS24 host control transitions, retries and reboot epochs offline.
- [x] Verify the independent key/full-LEGACY-HUD CP23 subset and prepare exact first-frame assets.
- [ ] Receive reproducibly published receiver source/artifact manifests and
  full-state model transcripts with explicit drain events.
- [ ] Implement Windows ownership replay while profiling sustained native encode.
- [ ] Obtain FPGA-only and concurrent receiver throughput measurements.
- [ ] Proceed to a short hardware fixture only when both ends implement the same
  contract; do not start another long JPEG run as a substitute for these gates.

Every report must separate encoding benchmark, localhost transport and verified
hardware presentation. Save resolution, FPS, quality, bitrate, latency method,
duration, hashes, counters and limitations. Never describe a target as achieved.
