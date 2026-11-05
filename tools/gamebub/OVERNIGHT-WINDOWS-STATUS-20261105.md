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
  Hybrid tail selection is explicit through `--pacing-spin-us` (0–1000,
  default 600); nondefault values require hybrid mode. The launcher also binds
  video to its configured source IPv4 address and logs actual socket endpoints.
- Final sender-thread CPU accounting and saved-source PTS/repetition/loop
  telemetry, so fresh transport frame IDs are not mistaken for distinct source
  timestamps. These measurements do not establish distinct visual content.
- Native CP23 exact outstanding-ACK binding and a coupled packet/frame ownership
  helper, with no invented reset, physical drain or reference-publication claim.
- Finite saved-RGB sequence input for native profiling: bounded per-frame
  loading, hashes, source IDs/PTS and explicit resampling versus native-decoded
  modes; paid output fingerprints support cached/uncached comparison.

## Validation evidence

- Native: **160 GameBub tests across 20 suites passed**, including pending-ACK,
  sequence and ownership tests. The original full **20 encoder golden cases**
  still match, including ten mandatory cases and thirteen policy attempts.
- Last full Python run: **529 tests, five optional skips**, with native CLI,
  body/encoder, wire/reset and HD22 fixture integrations enabled. Three later
  cleanup regressions passed in the focused **90-test** sender/launcher/pipeline
  run. Final morning validation will rerun after remaining source changes.
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
| Same settings, 30-minute concurrent-load stability run | 35,533 / 36,000 | 467 | 0 |
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
production default. Parameterized selection passed the focused sender and
launcher tests; a longer localhost stability soak is active. Its concurrent
native compilation load will be reported separately from quiet comparisons.

## Custom-codec finding

[Real moving-frame native profiling](measurements/native-saved-sequence-20261105.md)
used 60 distinct decoded Xonotic frames. Both variants accepted twenty and
rejected forty at the existing AR03 component cap. All selected packet SHA
values and acceptance decisions matched. Cached admission median was about
39 ms, above the 33.33 ms budget even before decoding. Cold/warm file loading
confounds whole-wall comparisons. This is the older mandatory-patch AR03
component, **not a complete CP23/HC22/HD22 encoder or hardware result**.

The [native independent-refresh encoder](measurements/cp23-independent-encoder-20261105.md)
now matches all twelve static instances and four additional pinned source/cap
oracles, using patch-free AR03 keys and four-LEGACY HC22 regions. The 60-source
all-key study accepted 34 and cap-rejected 26; median encode plus independent
validation was about 48 ms. It does not meet a 33.33 ms frame budget. The old
stateful AR03 study and this all-independent-key study have different semantics.
Full predictive/HD22 state and live custom streaming remain unimplemented.
No CP25 selection, custom network endpoint, decoder image or physical 30 fps
qualification has been introduced.

## Remaining overnight work

1. Validate the explicit small-tail choice over longer local CPU/memory/queue
   tests and input/audio simulation; retain unchanged defaults.
2. Preserve native independent-refresh conformance; add optional substage
   profiling before choosing an optimization within its measured build cost.
3. Validate the 400 us setting over a longer native-source local run and finish
   the synthetic production-audio load test. Keep real audio/hardware gates separate.
4. Rerun complete regression/format/coverage checks, push the candidate and
   publish a short morning test recipe and remaining hardware gates.

The morning JPEG comparison should use one fixed receiver build and the same
new launcher for both control/candidate, changing only the selected wait.
Confirm a fresh baseline, unused IDs and recording coverage before transmitting.
The previous midnight camera window does not cover a morning run.

The [30-minute report](measurements/localhost-30m-soak-20261105.md) includes
sampled memory, CPU, queue/ACK/log reconciliation and concurrent-load limits.
The [JPEG size/quality study](measurements/jpeg-quality-20261105.md) keeps the
1024×600 source's actual 691×405 scaled content distinct from the 720×405
viewport and full 720×480 canvas. Neither study establishes FPGA playback.
