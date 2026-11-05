# Coordinated Windows / MoonBub overnight development phase

Prepared late 2026-11-04, America/Denver; work may continue into November 5.
**Start this phase after the next agreed test is completed and reconciled.**
This document coordinates development; it does not start a sender, schedule an
unattended run or establish readiness for a firmware/FPGA installation.

## Outcome for the next handoff

Produce a lower-CPU Windows pacing candidate, a source-bound diagnosis or
explicit unknowns for the two v30 failures, and concrete progress toward the
first complete CP23 custom-codec fixture. Publish tested commits, exact assets,
reproduction commands and a short readiness decision for each hardware path.
Verified 30 fps remains the goal, not an overnight completion promise.

## Starting evidence and fixed baseline

- Windows dev branch: `AEW2015/Sunshine`,
  `gamebub/windows-jpeg-retry-20261103`; pacing study commit `7a6c3d81`.
- Last operator-confirmed receiver: v30, build50, overlap, 32 queue slots.
  JPEG/MSV1 on UDP 5533; AV v1 input/audio session on UDP 5534; source
  192.168.0.47 and receiver 192.168.0.157. Reconfirm addresses for a later run.
- [v30 hardware control](measurements/v30-xonotic-20fps-4mbps-30s-20261104.md):
  600 encoded, 525 complete sends, 75 replacements; 523 accepted, decoded and
  presented, two Sequence failures, zero queue drops, queue peak 15/32.
  Core faults/overflows/underruns/transport overflows zero. STOP restored power
  saving. Camera coverage confirmed changing scenes; subsecond stutter unknown.
- [Independent localhost pacing study](measurements/host-pacing-study-20261104/README.md):
  unchanged sender 526 complete / 74 replacements; lab spin-tail candidate
  592 complete / eight replacements. Median within-frame gap improved from
  2.984 to 2.158 ms. Plain-sleep median overshoot approximately 0.81 ms; socket
  send approximately 0.02 ms. Candidate process used 14.828 CPU-seconds in
  30.424 wall seconds, approximately half of one logical core. It is not deployed.
- Custom first-fixture profile remains **CP23 / HC22 / HD22**. CP25 is not
  selected. Windows has offline encoder/decoder checks, static independent-
  refresh assets and partial reset/control replay. A complete compatible
  custom FPGA decoder/local loader and live custom endpoints are not yet
  evidenced. AKD1's earlier KEY diagnostic does not establish CP23 support.

Keep the original Sunshine checkout, installed service, working JPEG/AV path
and build50 unchanged during software work. Develop and build candidates
separately. Do not send custom data through JPEG ports or an H.264 identifier.

## Gate 0: close the next test before branching the investigation

Record the actual sender wait implementation and hashes, source start offset,
app/FPGA identity, trace epoch, baseline counters, settings, start/end clocks,
frame range, capture/encode/replace/partial/skip/ACK counts, and final receiver
decode/presentation/queue/core counters. Preserve packet and receiver traces.
Record camera coverage gaps and STOP/power-save restoration independently.

Do not silently apply the lab spin-tail wait in a supposedly unchanged control.
If it is the selected experiment, identify it and its CPU cost explicitly.
The last stated camera window ends around 23:47 Denver on November 4; that
does not authorize or cover a later overnight test. Verify new coverage before
any subsequent physical transmission.

If the next run introduces a new failure, keep that evidence separate from
v30 IDs 2,013,421 and 2,013,422. Agree one common baseline commit and record
the next unused frame-ID range; do not reuse IDs merely because a session reset.

## Parallel work packages

### Windows W1: precise pacing with lower CPU

1. Preserve the unchanged and lab-candidate measurements as reference results.
   Inspect the actual Python/Windows waiting path. Evaluate a precise blocking
   wait and/or a smaller bounded spin tail, with a validated fallback. Avoid
   an unmeasured global timer-resolution change.
2. Keep wire data, rate accounting, queue bounds, quality, maximum frame age,
   feedback expiry and no-catch-up behavior unchanged. Make experimental
   selection explicit; retain the existing default while qualifying it.
3. Measure intended deadline, actual wake, socket-send duration, packet gaps,
   encoding/capture time, replacements, process and pacing-thread CPU, memory
   and cleanup. Separate full-packet intervals from short-tail frame boundaries.
4. Compare baseline and candidate in an alternating order on localhost using
   the same first 600 Xonotic slots and unchanged receiver reference. Repeat
   to establish variability; do not benchmark concurrent variants against
   each other. Then run a five-minute local candidate soak if the short tests pass.
5. Test early wake, oversleep, cancellation, socket failure, feedback timeout,
   lease expiry and shutdown. Concurrent input-only AV needs a local test;
   audio is a later separately labeled load test, not an implicit addition.

Exit: a tested optional candidate with no stale-send/deadline/liveness regression,
approximately 20 fps delivery on the selected local clip, bounded queues, and
measured CPU suitable for the dedicated host. Provisional pacing-thread budget:
average no more than 10% of one logical core; report total process CPU separately.
If that budget cannot be met, report the tradeoff and keep the candidate in
the lab. Local transport results do not establish hardware playback.

### MoonBub M1: correlate the two retained v30 failures

Use [the published exact host packet records](measurements/v30-requested-packet-times-20261104.json)
and the retained 125.834 ms Sequence window, with its known 2,376 trace-record
losses, zero phase losses and no failure-table overflow.

- **2,013,421:** same active frame, expected 4,096, observed 5,120. Follow
  offsets 3,072, 4,096 and 5,120 from socket reception through enqueue,
  dequeue and assembly. Identify where 4,096 is last positively observed.
- **2,013,422:** offset 1,024 with no active assembly. Determine whether SOF
  offset zero was observed, admitted, rejected or absent. Include cleanup/reset
  state and queue occupancy between the two frames.
- Match frame ID, capture timestamp and offset. Never subtract host and
  receiver monotonic clocks directly. Successful host sends do not prove RF
  departure or socket reception. Keep missing evidence explicitly unknown.
- If the existing window cannot locate the transition, design a compact bounded
  history that triggers on Sequence/no-active-assembly as well as queue overflow.
  Keep incoming/active frame identity, expected/observed offset and dropped-trace
  counters. Avoid restoring the previous high-volume per-phase logging behavior.

Exit: either a source-bound root-cause account and one tested fix, or a narrow
instrumentation candidate explaining what the next test can distinguish.
Do not enlarge the queue or change FPGA timing without evidence for that change.

### Joint C0: freeze the first custom fixture's exact contract

Exchange selected source commits before coding incompatible interfaces. Keep
CP23/HC22/HD22 as the selected first-fixture profile. Explicitly identify the
static key/full-LEGACY-HUD subset versus the eventual stateful/predictive path.

Agree envelope bounds, canvas/viewport rounding, frame/epoch IDs, timestamps,
codec capabilities, CRC coverage, tags/hashes, chunk layout, maximum frame size,
credits, publication/release rules, cancellation and recovery. Existing offline
RS24/control models are starting evidence, not deployed endpoints. No new custom
UDP port is assumed: assign carriage and port jointly before a network test.

Distinguish transport completion, decoder completion, presentation, reference
publication and memory release. Unknown outcomes retain ownership until the
agreed recovery proves release safe. Do not invent an ACK-of-FINISHED packet.
AV v1's independently sequenced input remains a separate contract.

Exit: one versioned shared profile and fixture manifest, with implemented,
modeled and proposed fields identified and matching golden vectors on both ends.

### Windows C1: custom-codec state and sustained native benchmarks

Start while C0 is coordinated; keep interface-dependent changes behind its gate.

- Retain all encoder and reconstruction goldens. Package the selected CP23
  first-frame packet, expected JA23, RGB565 image hash and source manifest.
  Existing assets are under `tools/gamebub/fixtures/v24-independent-refresh*`.
- List missing full HC22/HD22 state, reference/HUD banks and reset/ownership
  behavior explicitly. Port bounded transitions against agreed complete-state
  transcripts, including real drain/write/publication events where applicable.
- Test lost/corrupt/duplicate/stale controls, repeated BUSY, lost completion,
  reboot epochs, late owners and reference publication. Byte syntax alone does
  not close ownership conformance.
- Benchmark native capture/scaling/encode on saved moving footage. Count all
  candidate attempts and work later discarded, not only the winning encode.
  Record frame sizes, quality, per-stage tails, CPU, memory and queue ages.
  Optimize only a measured bottleneck while preserving exact output/goldens.
- Implement custom network sending only against the jointly frozen carriage
  and a corresponding receiver implementation. Do not unilaterally choose a
  codec/packet revision to make a host-only benchmark look integrated.

Exit: independently reproducible software conformance and a native performance
report. Clearly separate implementation completed from endpoint/hardware gates.

### MoonBub / FPGA C2: first complete local custom fixture

Inventory the selected profile's parser, entropy decode, reconstruction,
base/HUD banks, tags, patches, publication/release and scanout. Mark each as
implemented/simulated/synthesized/routed/installed; include a source-bound
manifest rather than treating an earlier component image as the full decoder.

Prioritize a **complete one-frame independent-refresh path** before broadening
the codec. Use the existing exact CP23 fixture or agree a narrower component
envelope explicitly. Provide a local loader, expected reconstructed words/hash,
presentation event and eventual release evidence. A functional first frame does
not need to meet 30 fps, but partial component tests must keep their narrower label.

Run simulation for malformed/truncated packets, capacity/CRC errors, fresh epochs
and legal presentation/release ordering. Report timing closure, memory service
and resource constraints separately. If a complete image is not buildable by
handoff, publish the missing stages and next actionable simulation; do not
substitute a new unverified codec profile or an unrelated bitstream.

Exit: either a complete source-bound decoder/loader candidate ready for a
coordinated local fixture check, or a precise list of unfinished stages. No
uncoordinated overnight flash or replacement of the installed working image.

## Suggested six-hour development window after Gate 0

These are work budgets and checkpoints, not promised completion times.

| Relative time | Windows | MoonBub / FPGA | Exchange |
|---|---|---|---|
| 0–30 min | Archive test, pin baseline | Seal trace/counters | Selected profile, hashes, unresolved IDs |
| 30–120 min | W1 wait measurements/tests; C1 gap inventory | M1 correlation; C2 implementation inventory | First diagnosis, contract questions, complete-fixture scope |
| 2–4 h | Lower-CPU candidate and local conformance; native codec profiling | Targeted receiver tests; selected decoder simulation | Concrete patch/fixture commits and failed gates |
| 4–5 h | Local soak/recovery tests; review counterpart contract | Trace-budget checks; build/timing/fixture checks | Both sides reproduce agreed vectors |
| 5–6 h | Finish report and separate candidate build | Finish readiness manifest and decoder status | Morning handoff and one proposed next hardware test |

Use separate branches/checkouts for independent work and avoid two agents editing
the same protocol document without an agreed editor. Rebase/reconcile the shared
contract before integration. Publish concise evidence at checkpoints rather than
running multiple simultaneous hardware senders.

## Hardware sequence after overnight development

1. **JPEG pacing comparison:** if W1 passes, run a short matched clip test on
   one fixed receiver build, changing only the selected host wait. Confirm
   recording coverage, baseline counters, IDs and STOP behavior beforehand.
2. **JPEG soak:** proceed only if frame identities reconcile, failure reasons
   are captured and CPU/queue behavior is acceptable. Audio/input coexistence
   is a separate subsequent gate. This does not qualify the custom codec.
3. **Custom local fixture:** only when C0/C2 provide a complete matching decoder
   and loader, observe exact reconstruction, presentation and safe release.
4. **Custom network fixture:** only after both live endpoints agree, send one
   known frame, then a short low-rate sequence with recovery tests.
5. **Custom rate ladder:** increase measured presentation rate toward 30 only
   after bounded queue/reference ownership and recovery pass. Then perform
   the sustained moving-content qualification in the main development plan.

Do not select a bitrate from the FPS label alone. Measure encoded frame demand,
packet overhead and burst/queue service. Report resolution, actual delivered
frames, quality, bitrate, latency method, duration, drops and recording limits.

## Morning handoff format

- Source branch/commit, exact app/FPGA/build hashes and whether anything was installed.
- Completed implementation versus remaining modeled/untested work.
- Commands, tests passed/failed, fixture and clip hashes, raw evidence locations.
- Windows wait/CPU results; MoonBub failure identity analysis and trace coverage.
- Custom fixture readiness: local decoder, loader, live endpoint and throughput
  each stated separately as ready/not ready, with the blocking dependency.
- One recommended next test, its single intended variable, duration/settings,
  observations, unused ID range and required recording coverage.

## Prompt to send the MoonBub agent

> Please coordinate an overnight development phase with the Windows agent
> **after the next agreed test is reconciled**. Follow this plan and publish
> your selected commit, implementation inventory and readiness gates.
>
> Keep the working JPEG/AV path and build50 intact. First correlate v30 frames
> 2,013,421 and 2,013,422 using the retained Sequence window and published host
> packet records. Locate offset 4,096's last observed stage and the following
> frame's SOF/admission/reset history. Keep trace gaps unknown; do not subtract
> host/receiver clocks. If evidence is insufficient, implement compact bounded
> identity history with Sequence/no-active triggers and measured trace loss.
>
> In parallel, inventory and advance the **CP23/HC22/HD22 first complete local
> custom fixture**, retaining the agreed profile. Provide parser-to-presentation
> coverage, exact source/artifact hashes, local-loader plan, golden RGB565/JA23
> checks and unfinished stages. An older KEY component image is not a complete
> CP23 decoder. Coordinate contract changes and the eventual custom endpoint
> with Windows before implementation depends on them.
>
> Windows will work independently on lower-CPU precise pacing, local liveness/
> recovery tests and native custom-codec state/performance. Exchange evidence
> around two hours and provide the morning handoff after roughly six hours.
> No uncoordinated flash, new hardware sender or rate escalation. Report what
> is actually ready for local fixture, network fixture and 30 fps separately.
