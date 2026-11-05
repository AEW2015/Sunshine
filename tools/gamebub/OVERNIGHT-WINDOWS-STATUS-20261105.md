# Overnight Windows checkpoint — 2026-11-05

The requested development window began around **00:08 America/Denver** and
runs through approximately **06:08**. This is an in-progress checkpoint, not
the final morning handoff. Hardware traffic remains stopped; the installed
Sunshine service and receiver configuration were not changed.

## Implemented and validated

- Explicit input-only AV in the finite launcher, with optional saved-clip
  looping, source SHA, absolute paths and start-offset provenance. Video starts
  after ACTIVE; STOP follows actual video completion and final feedback/log
  drain, within a bounded grace. No audio/injection is implied by input-only mode.
- Owned dumpcap lifecycle: active before AV/media, health-checked through STOP,
  conservative finite finalization, native/drop statistics, and exact STOP
  verification in the finalized capture. Incomplete capture remains explicit.
- Optional precise blocking and bounded hybrid pacing; unchanged ordinary-sleep
  default. Fallback and CPU/spin/resource counters are visible. Scoped timer-period
  experiments showed no gain and are not selected by production launcher modes.
- Final sender-thread CPU accounting and saved-source PTS/repetition/loop
  telemetry, so fresh transport frame IDs are not mistaken for distinct source
  timestamps. These measurements do not establish distinct visual content.
- Native CP23 exact outstanding-ACK binding and a coupled packet/frame ownership
  helper, with no invented reset, physical drain or reference-publication claim.
- Finite saved-RGB sequence input for native profiling: bounded per-frame
  loading, hashes, source IDs/PTS and explicit resampling versus native-decoded
  modes; paid output fingerprints support cached/uncached comparison.

## Validation evidence

- Native: **154 GameBub tests across 19 suites passed**, including pending-ACK,
  sequence and ownership tests. The original full **20 encoder golden cases**
  still match, including ten mandatory cases and thirteen policy attempts.
- Last full Python run: **525 tests, five optional skips**, with native CLI,
  body/encoder, wire/reset and HD22 fixture integrations enabled. The later
  source-PTS telemetry change passed the focused **59-test sender suite**.
  Final morning validation will rerun the full suite after remaining changes.
- New waiter/timer-period helpers: 100% focused statement/branch coverage;
  capture-owner helper: 100% focused statement/branch coverage. Native line
  coverage and its compiler/exception branch limits are reported separately.
- Real localhost launcher + capture: 20/20 frames accepted, 54 MSI1 snapshots,
  STOP independently received and captured, 446 captured packets, zero capture
  drops, natural exit and no forced cleanup. Capture's conservative safety
  finalization kept it alive about two minutes after media STOP; times are
  reported separately.

## Host pacing results

All results below are **localhost transport**, not Wi-Fi/FPGA/display results.
Use [the pacing report](measurements/overnight-host-pacing-20261105.md) and
[capture validation](measurements/capture-owner-validation-20261105.md) for
method, raw artifact locations, scope and CPU-accounting limitations.

| Workload | Complete / target | Replaced | Local ingress errors |
|---|---:|---:|---:|
| 20 fps / 4 Mbps / Q25, sleep, 30 s controls | 526 / 600 in each | 74 in each | 0 |
| Same, 600 us hybrid, 30 s | 588 and 587 / 600 | 12 and 13 | 0 |
| Same hybrid + input-only AV, five minutes | 5,926 / 6,000 | 74 | 0 |
| Native decoded source, 30 fps / 6 Mbps / Q25, 30 s | 873 / 900 | 27 | 0 |
| Native decoded source, 30 fps / 8 Mbps / Q25, 600 us tail | 900 / 900 | 0 | 0 |

The five-minute run measured 19.73 sent fps including drain, zero input
timeouts/pending ACKs/backend failures, and clean STOP. Measured sender-thread
CPU was 11.625 seconds over 300.320 seconds (about 3.9% of one logical core);
total video-process CPU was about 47%. CPU accounting and spin wall-time
caveats remain explicit. The first 30 fps/8 Mbps run used about 22% sender-thread
CPU, so delivery alone did not close the CPU tradeoff.

A subsequent **lab-only** 8 Mbps tail sweep accepted 900/900 in both 400 us
repeats, at roughly 5–6% measured sender-thread CPU. The 200 us repeats
accepted 884 and 883/900, replacing 16 and 17. This is not a silently changed
production default. Parameterized selection and longer validation are next.

## Custom-codec finding

[Real moving-frame native profiling](measurements/native-saved-sequence-20261105.md)
used 60 distinct decoded Xonotic frames. Both variants accepted twenty and
rejected forty at the existing AR03 component cap. All selected packet SHA
values and acceptance decisions matched. Cached admission median was about
39 ms, above the 33.33 ms budget even before decoding. Cold/warm file loading
confounds whole-wall comparisons. This is the older mandatory-patch AR03
component, **not a complete CP23/HC22/HD22 encoder or hardware result**.

The native team has identified a source-backed independent-refresh encoder
path for the selected CP23 profile, reusing patch-free AR03 key encoding and
separate four-LEGACY HC22 regions. That work is not claimed complete here.
No CP25 selection, custom network endpoint, decoder image or physical 30 fps
qualification has been introduced.

## Remaining overnight work

1. Expose the measured small-tail choice explicitly; retain unchanged defaults.
   Validate longer local CPU/memory/queue behavior and input/audio simulation.
2. Finish native independent-refresh encoder conformance against pinned model
   bytes, without relabeling partial coverage as stateful HD22 support.
3. Extend sustained native profiling only with exact hashes and all attempt
   costs; distinguish component throughput from full-path readiness.
4. Rerun complete regression/format/coverage checks, push the candidate and
   publish a short morning test recipe and remaining hardware gates.

The morning JPEG comparison should use one fixed receiver build and the same
new launcher for both control/candidate, changing only the selected wait.
Confirm a fresh baseline, unused IDs and recording coverage before transmitting.
The previous midnight camera window does not cover a morning run.
