# Game Bub: Sunshine and Windows development plan

Current custom-codec work follows the
[30 fps development plan (2026-11-04)](30FPS-DEVELOPMENT-PLAN-20261104.md).
Use the accompanying [MoonBub agent prompt](MOONBUB-30FPS-PROMPT-20261104.md)
for receiver/FPGA coordination. The earlier JPEG work and measurements below
remain historical evidence.

Status: proposed work; unchecked items are not completed or verified.
Prepared 2026-11-03 following the `study/30fps-sim-20261102` audit.

Progress: sections 1 and 2 completed on the candidate branch. The capacity-limited
soak delivered 17,998/18,000 scheduled frames; one oversize retry was safely
rejected and one waiting JPEG was replaced. The physical 5 fps comparison sent
1,500 frames with 15 rejected feedback responses. Its reliability gate remains
open pending receiver trace correlation. Independent receiver counters confirm
1,485 decoded/presented and 15 dropped, with zero application-queue packet
drops and a high-water mark of 26/32. See
[the validation report](measurements/jpeg-capacity-retry-validation-20261103.md).

A [continuously recorded repeat](measurements/handheld-recorder-repeat-20261103.md)
sent IDs 5117..6616: 1,488 independently counted presentations and 12 drops,
all twelve identified as decoder-Busy admission rejections at offset 0. The
application queue had zero packet drops and peaked at 26/32. V19 overlap was
then tested before introducing admission-wait firmware.

The [v19 overlap comparison](measurements/handheld-v19-overlap-5fps-5m-6718-20261103.md)
passes the five-minute 5 fps milestone: IDs 6718..8217 all received, decoded
and presented, zero new frame or queue packet drops, high-water 25/32, and no
reported core faults/overflows/underruns. A camera check showed the game image
near the end; motion was not monitored optically throughout. Next is a short
10 fps exploration with the same receiver application and queue, followed by
longer confirmation if stable. Admission-wait firmware stays separate if Busy
returns. Physical 30 fps, live-capture performance and end-to-end latency remain
unverified.

The [20-second 10 fps exploration](measurements/handheld-v19-overlap-10fps-20s-8218-20261103.md)
sent IDs 8218..8417: 161 complete, 28 partial and 11 zero-byte deadline refusals.
All 161 complete frames were independently counted decoded/presented. Receiver
queue packet drops, errors and core faults were zero, and no Busy diagnostics
were recorded. Next investigate host pacing/queue age and deadline prediction;
keep admission-wait firmware separate. Any deadline, quality or pacing change
must be measured individually against this unchanged-settings baseline.

The [completed timing comparison](measurements/10fps-partial-frame-timing-comparison-20261103.md)
compares all 28 partials, 161 complete sends and 11 preflight refusals. It
supports host queue/pacing investigation: partial-frame encode median 2.222 ms,
encoded wait median 82.804 ms, and packet gap median 4.984 ms versus 4.256 ms
configured. An isolated sleep probe reproduced the gap scale without a socket.
Keep quality25, 2 Mbps, 200 ms and v19/application unchanged while adding
missing host stage/deadline/wait observability and evaluating no-burst pacing
offline. Do not select bitrate or quality changes from mean frame size alone;
the nominal one-second peak workload exceeds the cap.

The [twenty-minute live desktop run including Elden Ring](measurements/elden-ring-live-desktop-10fps-20m-9000-20261103.md)
confirms 11,893 received/decoded/presented (9.906 presentations/s by counters),
50 receiver-recorded Busy rejections and 20 host partials with individually
unresolved receiver reasons. Two host zero-byte refusals and 35 skipped slots
complete the 12,000-slot accounting. Queue drops and reported faults/overflows/
underruns were zero; session high-water was29/32. Busy admission is now a
demonstrated separate problem from host pacing/deadline failures. Investigate
commit/READY timing and test a bounded admission-wait receiver candidate
separately, including queue-pressure measurements; keep host pacing changes
in their own measured comparison. Physical centering also remains open.

The [five-minute desktop run after the MoonBub margin change](measurements/desktop-10fps-5m-21000-20261103.md)
adds a distinct receiver bottleneck:36 application-queue packet drops,32/32
high-water, first at22842 offset3072. All2,605 received frames were decoded and
presented,350 dropped;2,955 receiver outcomes leave one unexplained against
2,956 host nonzero sends. Frame22849's receiver disposition was not retained.
Correlate queue arrivals and consumer/QSPI waits before increasing load or
adding admission waits. Keep queue loss, host partials and Busy diagnosis
separate, and do not add packet counts to frame-drop counts.

## Objective

Latest clean baseline: [margin10/timing0, host shift0, five minutes at5fps](measurements/margin10-desktop-5fps-5m-30100-shift0-20261103.md).
IDs30100..31599 all received, decoded and presented (+1,500 each), zero frame
or queue drops, queue peak24/32 and empty final queue; all reported core
faults/drops/overflows/underruns zero. Receiver-side post-run camera samples
reported no flashing and stable placement. Preserve this configuration as a
comparison baseline; do not infer full-run optical timing or a causal shift fix.

Deliver one dedicated video, audio and controller mode, starting with a reliable
video-only Windows sender. The video target is 720x480 at 30 distinct presented
frames per second. Fit 16:9 source content into 720x405, centered with 37 black
rows above and 38 below. Treat 60 fps as a later measured target.

Use the receiver-agreed baseline JPEG/MSV1 profile for current testing. Changes
to capacity, transport, audio or negotiation require agreement with the receiver
agent and an update to the shared versioned specification. Never advertise JPEG
under an H.264 identifier.

## Baseline and development boundaries

- Active host baseline at audit: `gamebub/host`, commit `52152043`.
- Audited Sunshine study: `5ad52cff`; companion MoonBub study: `b616dae`.
- At those revisions, the host has 27 commits absent from the study and the
  study has 16 commits absent from the host. Recheck revisions before porting.
- Preserve the active host's Desktop Duplication, capture recovery, pacing,
  feedback and telemetry fixes. Do not replace it with the study sender.
- Use isolated candidate builds and worktrees. Preserve local changes and the
  installed Sunshine instance; do not replace or restart its service.
- Current test endpoint is `192.168.0.157:5533`, accepting host `192.168.0.47`.
  Verify both addresses and receiver configuration before each physical run.
- Keep video-only operation available throughout development.

The study's capacity and scaler experiments are not an integrated Sunshine
streaming mode. Receiver simulations are not physical playback measurements.

## 1. Reconcile the branches and fix JPEG retry

Owner: Windows host developer.

- [x] Create a candidate branch from the current host baseline and record its SHA.
- [x] Selectively port the JPEG capacity guard and optional single quality retry.
- [x] Fix the initial-oversize case: the current encoder rejects JPEGs over the
  262,144-byte protocol maximum before the retry can run. Keep intermediate
  allocations bounded, distinguish size rejection from codec/encode failure,
  and validate the final JPEG before packetization.
- [x] Preserve whole-frame rejection, bounded queue depth and stale-frame drops.
  Never truncate a JPEG to satisfy capacity.
- [x] Keep the retry optional and bounded to one attempt. Make its work subject
  to the frame deadline; expired results must emit no packets.
- [x] Decide and document how retry quality affects subsequent quality adaptation.
- [x] Log initial size/quality, retry size/quality, selected capacity, duration
  and final disposition with frame identity.

Required regression tests:

- [x] Exactly-at-capacity and over-capacity frames.
- [x] Initial JPEG above the protocol maximum, with a valid smaller retry.
- [x] Retry still oversized, encoder failure, invalid JPEG and minimum quality.
- [x] Disabled retry and invalid configuration values.
- [x] Deadline expiry before retry and after encoding; no expired payload sent.
- [x] Successful retry reaches loopback as a complete JPEG with matching CRC.
- [x] Existing pacing, feedback, recovery and capture tests remain passing.

Exit gate: passing regressions, strict final JPEG conformance, no oversized or
expired transmission, and documented quality-controller behavior.

## 2. Validate the host without hardware

Owner: Windows host developer.

- [x] Run the Python lab tests, including the pinned receiver parser integration.
  Configure the reference repository and Rust compiler explicitly; report skips
  and missing tools separately from passing checks.
- [x] Run lint and formatting checks on changed files; resolve the study's lint
  findings when carrying those files forward.
- [x] Run a ten-minute loopback soak using hash-pinned moving gameplay footage.
- [x] Exercise packet loss, duplicates, reordering, feedback silence and recovery
  in separate controlled impairment tests. Verify whole-frame failure and
  recovery on a newer frame rather than obsolete-frame retransmission.
- [x] Exercise a slow encoder, blocked socket and slow logger. Verify bounded
  memory/queues, stale-frame disposal, accurate failure counts and clean shutdown.
- [x] Preserve the JSONL frame log, final stdout summary, analyzer output, input
  hash, command, dependency versions and candidate commit.

Exit gate: an unimpaired soak has no invalid packets or incomplete frames, no
unexpected failure or logging loss, and all intentional impairments have
attributable outcomes. Report achieved throughput and skipped frames; a pass
does not imply physical 30 fps playback.

## 3. Benchmark Windows capture, scaling and encoding

Owner: Windows host developer.

- [ ] Use repeatable moving gameplay containing fine detail, text, particles,
  camera motion and scene changes. Retain deterministic fixtures for correctness.
- [ ] Compare the existing scaler and optimized area candidate at equal source,
  geometry, JPEG profile, quality and bitrate budget. Alternate comparison order.
- [ ] Measure acquisition, owned-buffer copy, scaling, JPEG encoding/validation,
  queue wait and packet send separately, including p50, p95 and maximum.
- [ ] Count distinct source images separately from repeated capture API returns.
- [ ] Exercise fullscreen/windowed transitions, resolution changes, capture
  timeout and device loss. Verify recovery and fixed output geometry.
- [ ] Establish buffer ownership before removing copies; test reuse and mutation
  while downstream workers are delayed.
- [ ] Review output visually for aliasing, text legibility, color and letterboxing.

Audit context: a short synthetic Windows benchmark measured scaler-only p95
43.32 ms for reference area and 12.68 ms for optimized area. These exclude
capture, JPEG encoding and transmission. The reference area implementation
already exceeds a 33.3 ms frame interval in that workload.

Exit gate: select a scaler using controlled Windows measurements and visual
acceptance. Demonstrate sustained 30 fps host output to loopback with bounded
frame age before claiming the host can supply the target rate. Pipelined stage
timings alone are not proof of sustained throughput.

## 4. Complete the 5 fps physical reliability comparison

Owners: Windows host developer and ESP32/FPGA developer.

- [ ] Confirm receiver firmware/FPGA hashes, 32-slot queue configuration,
  accepted source address, selected capture content and counter baseline.
- [x] Run five minutes at 720x480, 5 fps, quality 25 and a 2 Mbps cap. Pin minimum
  quality to 25 if fixed quality is intended; otherwise record every adaptation.
- [ ] Use a fresh frame-ID range and save sender logs and receiver traces for
  exactly that range. Account for restart/reset and unsigned-ID wrap.
- [x] Collect sent, skipped, suppressed, incomplete, accepted/rejected feedback
  and unmatched feedback counts. Feedback acceptance establishes ingress only.
- [ ] Collect receiver received, decoded, presented, dropped, packet queue-drop
  and queue high-water counters, plus QSPI/decode/presentation timings.
  Counters are confirmed for IDs 3617..5116: +1,485 received/decoded/presented,
  +15 dropped, zero application-queue packet drops, high-water 26/32. Per-frame
  stage timings and failure reasons remain pending.
- [ ] Correlate failures by frame ID and first missing offset with host packet
  timing and receiver queue/QSPI telemetry.
- [ ] Confirm a visible moving image through observation or camera recording.

Previous reported 32-slot result: 1,500 sent, 1,487 accepted feedback and 13
rejections. This is an improvement over the 16-slot result, but it is not a
zero-loss result or independent confirmation of 1,487 presentations.

Exit gate: every loss is accounted for and a confirmation run shows no
application-queue packet drops, no unexplained frame loss, bounded queue/age
and matched decode/presentation counts. If loss remains, investigate before
raising the rate; do not hide it by increasing the queue indefinitely.

## 5. Increase physical rate using measured gates

Owners: Windows host developer and ESP32/FPGA developer.

- [ ] Progress through 10, 15, 20 and 30 fps only as receiver measurements permit.
- [ ] Use five-minute exploratory runs, changing one setting at a time. Hold
  content and quality constant when comparing rates; document necessary bitrate
  changes and keep audio/control bandwidth reserved when those are introduced.
- [ ] Stop escalation on queue saturation, unexplained loss, increasing frame
  age, decode/presentation overruns or capture instability.
- [ ] Confirm the selected operating point with at least ten minutes of moving
  gameplay, counting distinct presented frame IDs and presentation intervals.
- [ ] Measure end-to-end latency optically or with validated clock correlation.
  Never label host capture-to-send age as glass-to-glass latency.

Exit gate for the 30 fps claim: physical 720x480 playback sustains 30 distinct
presentations per second over the confirmation run, with quality, bitrate,
latency, losses and duration reported. Report any shortfall rather than rounding
an encoding benchmark or nominal sender setting into a playback claim.

## 6. Build a native Windows sender candidate

Owner: Windows host developer; can proceed alongside receiver investigation
after host correctness and benchmark gates.

- [ ] Add a separate opt-in target using owned Desktop Duplication buffers,
  selected scaling, validated baseline JPEG and the agreed MSV1 transport.
- [ ] Keep the Python sender as a comparison/reference implementation.
- [ ] Migrate adapter tests into the required GoogleTest support using
  `tests/tests_common.h`, appropriate relative paths and include groups.
- [ ] Add ownership, pitch, geometry, overflow, device-loss and shutdown tests.
  Verify encoded JPEG syntax and packet bytes, not encoder settings alone.
- [ ] Add/update Doxygen; target 100% changed-source coverage. Run required
  formatting and inspect its diff for unrelated changes.
- [ ] Build with MSYS2/UCRT64 in a `cmake-build-*` directory. Prefix Windows
  build/test commands with
  `C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c`.
- [ ] Follow repository locked dependency setup and formatting instructions in
  `AGENTS.md`; run native tests from the build directory's `tests/test_sunshine`.
- [ ] Repeat loopback and physical comparisons against the Python sender using
  equal inputs/settings. Select the native candidate only with measured benefit.

Exit gate: reproducible Windows build, equivalent protocol behavior, bounded
resources/recovery, and documented performance without changing the installed
service.

## 7. Integrate the dedicated Sunshine mode, audio and controller

Owners: Windows host developer and receiver developer.

- [ ] Agree versioned experimental capability/negotiation and explicit rejection
  for unsupported combinations. Retain the stock Moonlight path and codec IDs.
- [ ] Add a dedicated session that uses the validated capture/JPEG/MSV1 path.
  Preserve pairing, application launch and input handling where practical.
- [ ] If using a fixed-peer/no-password development mode, make its selection and
  scope explicit; it must not silently alter stock-client pairing behavior.
- [ ] Agree audio format, packet layout, clock relationship, buffering and
  resynchronization. Keep audio optional and test its interaction with video load.
- [ ] Map agreed Game Bub button snapshots to one Windows virtual controller.
  Validate the supported driver/backend, chords, releases, stale input,
  disconnect neutralization and reconnect without stuck buttons.
- [ ] Test stock-client advertisement, pairing, launch, video/audio/input and
  experimental capability acceptance/rejection using a separate candidate.

Exit gate: repeatable dedicated-mode operation and stock-client compatibility
evidence, with video-only testing still available.

## Shared protocol and receiver dependencies

- [ ] Maintain the [versioned protocol](protocol/0.5.0-draft.md) with receiver
  agreement: codec capabilities, dimensions, IDs/timestamps, chunk layout,
  integrity, frame capacity, backpressure and recovery.
- [ ] Keep the current JPEG profile: baseline 8-bit YCbCr 4:2:0, agreed standard
  Huffman tables and no restart markers. Validate actual bitstreams.
- [ ] Treat 48 KiB capacity as an experimental memory option until agreed and
  tested across representative content; preserve the current protocol maximum
  unless both implementations explicitly change their contract.
- [ ] Require target FPGA fit/timing and real staged-byte-to-decoder validation.
  The latest SDRAM contention model still feeds the decoder from BRAM.
- [ ] If H.264 is selected later, replace the codec work with verification of
  the exact profile, entropy coding, references, slices and B-frame restrictions.

## Evidence to retain for every measured run

| Category | Required record |
| --- | --- |
| Identity | Host/receiver/FPGA commits, protocol version, run ID, frame-ID range |
| Environment | Windows, CPU/GPU, capture GPU/display, dependencies, Wi-Fi configuration |
| Input | Source/hash, motion scenario, source dimensions and capture backend |
| Settings | Output dimensions, target FPS, quality range, cap, queue/deadline limits |
| Host | Complete/incomplete sends, skips/suppression, recoveries, CPU/memory, log failures |
| Receiver | Received/decoded/presented/dropped IDs, queue drops/high-water, stage timings |
| Output | Achieved FPS, quality distribution, JPEG and MSV1 bitrate with overhead scope |
| Timing | Duration, frame-age percentiles, presentation intervals, latency method |
| Artifacts | Exact commands, JSONL, final summary, analyzer report, receiver trace/video |

Label results as unit/component, encoding benchmark, localhost streaming,
physical ingress, decoded output or verified presented playback. Do not promote
evidence from one category into another.

## Related documents

- [Optimization and validation backlog](OPTIMIZATION-PLAN.md)
- [Sunshine integration map](SUNSHINE-INTEGRATION.md)
- [Receiver handoff](HANDOFF.md)
- [Host laboratory setup and commands](README.md)
