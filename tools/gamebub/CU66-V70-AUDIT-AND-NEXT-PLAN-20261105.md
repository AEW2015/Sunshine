# CU66 v70 audit and next development plan

Date: 2026-11-05. This is a source/evidence audit and proposed next phase,
not implementation, installation or permission to start a hardware sender.

MoonBub baseline: [`fcc02c58d46f96a26790ce02826a0bf937c2478b`](https://github.com/AEW2015/moonbub/tree/fcc02c58d46f96a26790ce02826a0bf937c2478b),
`study/gamebub-cu66-integration-v70-20261105`.
Windows baseline: `AEW2015/Sunshine`, `gamebub/windows-jpeg-retry-20261103`,
`5c53b3e2`. Existing CP23 tools and deployed JPEG/AV remain preserved.

## Audit verdict

V70 is a substantial functional integration prototype with an explicitly failed
clean-cadence gate. It is not ready for CU66 network gameplay or a 30 fps board
claim. The inspected handoff distinguishes these scopes correctly. We found no
confirmed functional code defect in this review; the blocking findings below
are compatibility, measurement and deployment gaps, not hidden passes.

Three parallel read-only reviews checked profile/state compatibility, memory
results and evidence scope. Source and retained results were inspected; no
simulation, synthesis, sanitizer campaign or physical test was rerun. Published
integrity-audit totals are not represented as a fresh independent verification
of every file hash.

One concrete documentation correction: the handoff's native HUD endpoint row
says "457 histories" per run. `software-control/results.json` records 457 HUD
frames per run, from the campaign's four histories. Change that label to
"457 HUD frames"; this does not invalidate the functional results. The audit
checked all 13 declared result-summary JSON hashes against committed files,
including the 457-frame and 28-negative cohorts, and separately checked the
target-build status and its retained preflight evidence.

| Finding | Evidence / consequence | Next action |
| --- | --- | --- |
| Windows custom backend is incompatible | CU66/GU66 has different headers, a different profile and canonical planar-u8 tags. Our CP23 backend uses older framing/tag semantics. | Add a separate CU66 conformance backend; retain CP23 tests. Do not rename packets or reuse its recovery profile. |
| Correctness evidence exceeds system-performance evidence | 457 retained frames across four histories qualify the packet/base path; the actual-command system tests two chronological frames per painter. | Preserve both cohorts and add a fixed-arrival system campaign. Leaf or transactional-memory passes do not close that gate. |
| Current memory/presentation schedule misses the budget | P-frame strip transaction is 22,984,583 memory clocks: 229.846 ms at the model's 10 ns period, about 6.9 times 33.333 ms. HUD CPU/live ingress are excluded. | Measure per-client service and line deadlines, then change memory service. This is not decode-only latency or achieved FPGA timing. |
| Strip locality helps but does not solve cadence | P-frame ACT commands fall 52.777%; total clocks fall 7.372%. Runs include different amounts/phases of LCD traffic. | Compare fixed windows and normalized clean/missed-line rates. Do not call this a 52.8% throughput gain. |
| Real-time and hardware gates remain open | Both schedules underrun; HUD CPU runs outside simulated time; exact-part synthesis/route/CDC and live ESP32/QSPI integration are unavailable in the retained qualification. | Run target feasibility early and separately instrument actual processor/control/transport costs. |
| Publication/recovery semantics need a new host contract | Irreversible commit, idempotent lost-ACK reconciliation, physical drain and presentation leases differ from ingress ACKs and JPEG frame independence. | Agree explicit events/ownership before adding a custom socket or dependent-frame dropping. |

The 512-cycle watchdog in owner tests is an intentional negative-test override.
The receiver's default is 64,000,000 precommit transaction cycles, excluding
COMMIT_ACK/DRAIN. It is not an inactivity timer and does not contradict the
multi-million-cycle system results. Derive its hardware configuration from the
actual clock and bounded service/recovery policy; shortening it cannot establish
30 fps or authorize early buffer release.

## Freeze these facts before implementation

The normative [fixture contract](https://github.com/AEW2015/moonbub/blob/fcc02c58d46f96a26790ce02826a0bf937c2478b/docs/cu66-v69/fixture-contract.md)
and frozen protocol sources govern CU66, not this summary:

- Profile `16c998527276c7c5249e96c75931494b`; CU66/GU66 headers are 76/60
  bytes. Preserve exact field layout, CRC coverage and original payload bytes.
- Canonical tag is SHA256 of little-endian width/height followed by planar
  Y/Cb/Cr uint8 bytes, truncated to 16 bytes. Require samples in 0..255 before
  conversion. This is not the old signed16 domain.
- Retained native capability is fixed epoch 25, 720x480 YUV420, AB38 dispatch
  5/6 and zero base motion, with the documented HU/HX and HUD payload subset.
  Reject otherwise-valid unsupported motion/dispatch/profile inputs explicitly.
- Research epoch 25, the owner's 64-bit generation and a future network session
  are different identities. Specify their mapping without repurposing fields.
- HC70/HR70 is internal processor HUD control framing, with a 32-byte header
  and header+payload CRC. It is not HC22, AV v1, or an assigned PC UDP endpoint.
  Its payload limit is not automatically the complete CU66 packet limit.
- Keep coded/active geometry, exact color/chroma rounding, HUD rectangles and
  prototype portrait/border mapping pinned. Do not inherit legacy panel-placement
  tweaks merely because both paths use a 720x480 coded canvas.

Jointly confirm that CU66 is the next custom experiment before superseding the
earlier CP23 fixture roadmap. Neither choice changes deployed JPEG support.

## Ordered development phase

| Gate / owner | Work and deliverable | Exit evidence |
| --- | --- | --- |
| G0 — joint freeze; FPGA tool owner | Pin codec/source/fixture/capability manifests and initial key+dependent-P pair. Check exact `xc7a100tcsg324-1` availability, board clocks, memory map and preliminary resource/RAM-port feasibility immediately. | Matching manifests; target preflight reports available or unavailable honestly. No substitute-part Fmax/fit claim. |
| G1 — Windows conformance, parallel with G2 | Build the pinned portable `cu66::Decoder` separately under UCRT64. Add explicitly named CU66 adapters/tests; replay chronological histories, unsupported inputs and failure-preserving state. Inventory a constrained producer before implementing an encoder. | All 457 frames, 28 negatives, exact canonical/HUD/display outputs, key recovery and immutable returned-state checks pass on Windows. Record compiler, hashes, memory and timing scope. |
| G2 — FPGA measurement baseline | Add per-reader request/response wait, queue age, row/cache hits/misses, commands/turnarounds, refresh and LCD service-deadline counters. Add the missing packet-complete/validated-ready timestamp chain and coherent snapshots. | Reproducible fixed arrivals/windows/seeds; complete clean and missed lines, unfinished tails, accepted/committed/presented IDs, bounded traces with explicit overwrites. Charge diagnostics traffic. |
| G3 — FPGA memory/scanout | First compare a streaming BL8 LCD path with bounded arbitration against the exact-output control. Next compare reader-specific/associative cache variants. Then add burst-capable strip/HUD writes. Change one design variable per comparison. | Exact rasters/tags/guards remain; bounded LCD service, normalized underruns and actual command/cycle benefits improve. Aliasing invalidation, partial bursts, stalls and abort-at-accepted-beat tests pass. |
| G4 — joint state and scheduling | Add safe provisional decode/conversion/write overlap without publishing partial state. Measure and then implement the actual ESP32 HUD/control/QSPI partition. | Atomic global commit survives late HUD/SHA failures, lost ACKs, delayed readers and abort/drain. Target CPU time, peak live memory and real transfer/service costs are included. |
| G5 — Windows producer and local emulator | Produce only the frozen supported CU66 capability from original source captures. Agree network framing/session/bounds/credits/recovery, then implement bounded reassembly and stateful sender behavior locally. | Exact source-bound packets and state histories match independent oracles. Fragmentation/loss/reordering/duplicates/stale identities/timeouts/oversize/STOP/restart tests preserve ownership and reference correctness. No deployed endpoint is inferred. |
| G6 — FPGA/board local bring-up | Complete exact-part synthesis, routing, timing, resource/RAM-port and CDC/reset/I/O checks. Publish an approved image, compatible app/control driver, local loader and rollback identity. | Readback/memory guards, patterns, one real key+dependent-P and negative/recovery fixtures pass on the actual board with independent presentation evidence. |
| G7 — joint network ladder | Only after explicit endpoint readiness, send one agreed fixture at a conservative measured rate/deadline, then a causal sequence and controlled moving content. | Source route, peer/port, profile, unused IDs, recording through STOP, queue/core/drain and actual clean presentation outcomes reconcile before each increase. |
| G8 — release measurement | First qualify 30 unique complete game-frame presentations/s, then optimize validated decoding under 10 ms while retaining that throughput. | Gates and accounting below pass with declared windows and achieved clocks. Neither is established by a mean native CPU decode time. |

G1/G2 and target-tool preparation can proceed in parallel. G5's offline codec
work can overlap FPGA work after G0; its carriage-dependent implementation waits
for the contract. Keep a separate conformance executable/build directory and
tests until the receiver path passes. Sunshine video integration follows the
standalone endpoint; preserve stock client negotiation and pairing behavior.
Never advertise CU66 as JPEG or H.264, or send it to legacy UDP 5533/5534.

Direct transposed-YUV scanout is a conditional architecture branch after the
measured baseline. The proposed 69.56 MB/s versus 122.91 MB/s useful traffic is
accounting at the declared panel/game cadence, excluding command/overfetch/cache
overhead. Prototype and compare it with identical pixel/HUD/tag/deadline tests;
do not combine it with every cache/burst change and lose attribution. Extra
inverse DSP lanes follow measured critical-path evidence.

## Required tests and state rules

- Reference the last globally accepted canonical/HUD state, not the last sent
  packet or last displayed buffer. A JPEG-style arbitrary stale compressed-frame
  drop can break CU66 P dependencies. Drop source work before state mutation,
  or rebuild/rekey under the agreed recovery rules; account for every discarded
  attempt and all work paid. Do not silently rewrite an outstanding retry.
- Distinguish packet ingress, semantic acceptance, validated storage, irreversible
  global commit, processor reconciliation, presentation and allocation release.
  Only the agreed event advances host state. A transport ACK is not decoder
  readiness; validated-ready telemetry does not authorize early publication.
- Before commit, abort preserves accepted state and drains accepted operations.
  After commit, lost processor ACK cannot roll back state; retry idempotently
  and stop new dependent work. A liveness timeout records unresolved ownership
  and invokes agreed recovery, never frees a potentially live bank.
- Exercise stale generation/address/request-sequence replies, wrong tags,
  corrupt qmap/hidden coefficients, rejected HUD, lost COMMIT ACK, delayed
  presentation ACK, cache aliasing and reset in both clock domains. Include
  row/bank/burst boundaries, partial writes, stalled response consumption,
  guards, refresh and concurrent readers. A diagnostic clear is not reset.
- Snapshot diagnostics coherently across generation/frame/stage and multiword
  counters. An eight-entry, coalescing ring is not a lossless trace. Preserve
  first failure and dedicated totals even when records overwrite.
- Use existing Sunshine `tests_common.h`, test include groups and doxygen for
  added native source; target full changed-source coverage. Record unavailable
  sanitizer/tool gates separately from genuine passes. Build/test with the
  required MSYS2 UCRT64 prefix and separate `cmake-build-*` directories.

## Measurement and hardware acceptance

Freeze allowed backlog/frame age, warm-up, observation/drain windows and the
panel-quantized deadline policy before a run. The modeled panel is about
65.0755 Hz, so 30 game fps does not require every panel gap to equal 33.333 ms.
No unexpected normal-load black replacement lines or unexplained outcomes may
be hidden behind accepted-frame or descriptor counts.

Retain capture, encode, packet-complete, admission, validated-ready, RGB-ready,
commit, presentation and first/last correct-visible timestamps with session,
generation and frame identity. Measure queues and processor transfer time.
Relate device clocks through a qualified method or optical markers; never
subtract unrelated host/ESP32/FPGA clocks directly. Interface capture proves
observation at that point, not RF delivery. Cover START, STOP and actual drain,
and report capture/logger/trace drops and camera gaps.

For 30 fps, retain the 1,800-distinct-source-frame campaign and a ten-minute
physical run, with source/attempted/accepted/committed/presented IDs and all
recovery outcomes. Prepare hash-bound chronological native-CFR footage; the
retained 457 frames and old looped Xonotic soaks do not satisfy the distinct-source
gate. Prefer a full ten-minute source capture; label any repeated-content stress
test separately. Start video-only; add audio/controller load only in later
controlled passes, recording AV session and Wi-Fi power-state side effects.

The later under-10-ms interval begins at complete immutable packet staging and
ends at integrity-validated YUV/HUD storage and required write drain, including
post-staging queues and actual HUD processor service/transfer. Report p50/p95/
p99/max; the predefined valid campaign's observed maximum must be strictly
below 10 ms. This is not a universal WCET proof. RGB composition, vblank/scanout
and capture-to-visible latency remain separate measured system costs. Charge
failed/late/rejected attempts and do not alter scope to improve the statistic.

## Prompt for MoonBub's next phase

> Please use v70 commit `fcc02c58d46f96a26790ce02826a0bf937c2478b` as the
> correctness baseline and retain the frozen CU66 capability. First confirm
> exact-part tool availability and pin the key+P fixture, memory map, profile,
> control ABI and source hashes. Publish per-client memory/cache/command/service
> and LCD-deadline measurements in fixed arrival/observation windows before
> choosing cache/burst changes. Compare bounded BL8 LCD service first, then
> cache and writer variants separately, preserving exact pixels/tags and
> abort/drain/commit/presentation ownership. Include actual ESP32 HUD/control
> service and memory feasibility before hardware performance claims.
>
> Windows will prepare a separate CU66 oracle/producer path and stateful local
> emulator, preserving CP23 and JPEG/AV. Please provide the normative complete
> packet bounds, supported dispatch/motion/HUD modes, generation/epoch mapping,
> real admission/credits, commit/reconciliation/presentation/release events,
> reset and STOP recovery. HC70 internal framing does not assign our network
> endpoint. No sender or flash is authorized by this plan. Return source-bound
> results and open gates; first qualify 30 unique clean displayed fps, then the
> fixed complete-packet-to-validated-storage interval under 10 ms.

## Evidence reviewed

All MoonBub paths below are relative to the pinned commit above:

- `docs/cu66-v70/{hardware-handoff,plan,diagnostics,reproduction,verification-matrix}.md`.
- `docs/cu66-v70/evidence-audit.json` and `docs/cu66-v69/fixture-contract.md`.
- `experiments/cu66-native-v69/README.md` and selected decoder/control source.
- `fpga/experiments/cu66-v70/system/{comparison,logical-traffic}.json` and
  selected memory/display/receiver/control source reviewed by the agents.
- `fpga/experiments/cu66-v70/build/status.json`: exact-part implementation
  unavailable in the retained run; no target synthesis/route/CDC/physical pass.
- Current Windows `native/{body_decoder,composed_encoder,composed_transaction,
  transport_ownership,recovery_host}.h` and standalone sender/launcher behavior.

This plan does not change any installed Sunshine service, firmware, source
payload format, codec negotiation or runtime endpoint. It schedules no run.
