# Overnight Windows results — 2026-11-05

The requested development window began around **00:08 America/Denver** and
runs through approximately **06:08**. The software checks below are complete;
use the [morning handoff](MOONBUB-MORNING-HANDOFF-20261105.md) for physical gates.
Hardware traffic remains stopped; the installed
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

- Native: **173 GameBub tests across 24 suites passed**, including pending-ACK,
  sequence and ownership tests. The original full **20 encoder golden cases**
  still match, including ten mandatory cases and thirteen policy attempts.
- Last full Python run: **548 tests passed, zero skips**, with native CLI,
  body/encoder, wire/reset and HD22 fixture integrations enabled. Its CLI fixture
  executable was the immutable sequence-validated snapshot to avoid a concurrent
  link. The final pass also enabled the five optional pinned-receiver checks,
  including the Rust parser. Latest native budgeted-key and sequence checks passed separately.
- Explicit `--clip-selection native` requires matching nominal source/sender
  rates and checked rational CFR cadence. It avoids the legacy sampler's
  repeated source frames at rounded PTS boundaries. Legacy selection remains
  the default for matched controls; desktop capture is unaffected.
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
| Native source, 30 fps / 8 Mbps / Q25, 400 us + input-only AV, ten minutes | 17,997 / 18,000 | 3 | 0 |
| Native source, same video settings + full-rate synthetic audio, five minutes | 8,999 / 9,000 | 1 | 0 |
| Same native video/audio settings, 30 minutes | 53,998 / 54,000 | 2 | 0 |
| Final trace-enabled native video/audio repeat, 30 minutes | 53,996 / 54,000 | 3, plus one skipped slot | 0 |

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

The ten-minute native run measured 29.98 sent fps and about 5.7% sender-thread
CPU. The production-launcher native five-minute video/audio run had zero repeated
source timestamps. Its audio peer decoded all 28,743 sent blocks, with three
queued at STOP and no gaps, stale drops or queue evictions. These use synthetic
PCM and software peers, with no DAC, receiver-buffer or hardware playback claim.
The earlier legacy-sampler combined run is explicitly disqualified as unique
30 fps motion evidence because it repeated 3,000 source timestamps in 9,000 slots.

The [30-minute combined study](measurements/localhost-av-native-30fps-30m-20261105.md)
measured 29.994 sent fps. All 172,184 sent audio blocks decoded locally; three
publisher evictions and two queued blocks account for the remaining five of
172,189 published blocks. The cause of those queue stalls remains unknown.
Bounded eviction metadata was added afterward. Its
[controlled 121 ms stall test](measurements/audio-eviction-trace-validation-20261105.md)
matched all eight evicted sequence IDs to peer gaps; its unfaulted five-minute
check had no audio gaps. The trace retains no PCM and changes no queue policy.

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
Optional [budgeted key preparation](measurements/cp23-budgeted-key-20261105.md)
preserves all candidate sizes and exact winners, while skipping reconstruction
and tags only for proven nonfits. Quiet paired means fell about 29.8%, from
45.5 to 31.95 ms including independent validation. Accepted-only means remained
about 35 ms, and 26/60 frames still exceeded the cap. This is not a complete
30 fps custom streaming result. The default strategy remains selected.
The [same-process study](measurements/cp23-same-process-sequence-20261105.md)
checked 7,200 rows across four runs of 1,800 independent fixtures. Output hashes,
admission and source retirement all matched. Inclusive wall time improved about
27.3%; observed live OS peak working sets were around 32 MB, including bounded
metadata. These are component measurements, not stateful streaming or hardware.
No CP25 selection, custom network endpoint, decoder image or physical 30 fps
qualification has been introduced.

## Final repeat and morning gates

The [final trace-enabled repeat](measurements/localhost-av-trace-native-30fps-30m-20261105.md)
reconciled all 53,996 sent video frames and 172,185 sent synthetic-audio blocks.
The sole peer audio gap matches trace eviction 161678; two blocks remained
queued. No cause for the full queue is claimed. Video rate was 29.99252 fps
over its own lifetime and 29.98469 over complete harness lifetime. Packet timing
was off to preserve finite logs. Logs stayed below their limits; sampled memory
and CPU scopes, one skipped slot and cleanup are reported explicitly.
The [validation index](measurements/windows-validation-20261105.md) contains
reproduction commands and final zero-skip regression results. No hardware
sender is active in this work.

The morning JPEG comparison should use one fixed receiver build and the same
new launcher for both control/candidate, changing only the selected wait.
Confirm a fresh baseline, unused IDs and recording coverage before transmitting.
The previous midnight camera window does not cover a morning run.

The [30-minute report](measurements/localhost-30m-soak-20261105.md) includes
sampled memory, CPU, queue/ACK/log reconciliation and concurrent-load limits.
The [JPEG size/quality study](measurements/jpeg-quality-20261105.md) keeps the
1024×600 source's actual 691×405 scaled content distinct from the 720×405
viewport and full 720×480 canvas. Neither study establishes FPGA playback.

The required `uv run --locked lb-update-clang-format` completed successfully
after a temporary process-only traversal filter excluded ignored lab artifacts
and the nested venv. All 276 source inputs were preserved and checked; it made
zero content changes. A second pass covered 277 inputs after the sequence
helper, also with zero changes. The installed service remains running and was
not replaced. The [test environment](measurements/windows-test-environment-20261105.json)
records the queried OS, CPU, compiler and multimedia library versions.
