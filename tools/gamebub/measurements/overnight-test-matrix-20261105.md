# Overnight pacing candidate: morning test matrix

This matrix prepares the next localhost qualification pass for the optional
lower-CPU pacing candidate described in
[`OVERNIGHT-COORDINATED-PLAN-20261104.md`](../OVERNIGHT-COORDINATED-PLAN-20261104.md).
It records test proposals and repository evidence; **no tests or benchmarks
were run while preparing this note**. A passing local run does not establish
hardware playback.

## Before media starts

- Confirm the receiver is freshly available and record its build, app/FPGA
  identity, address, selected endpoint, queue configuration, and baseline
  counters. Reconfirm the physical camera coverage window for this run.
- Use build50 and the established JPEG/MSV1 plus AV v1 endpoints. Keep the
  receiver and protocol settings fixed across the comparison.
- Select one host-side wait implementation as the sole variable. Identify the
  source revision/hash and whether this is baseline or candidate before launch;
  do not silently substitute the lab spin-tail candidate into the baseline.
- Start the packet capture before AV or video media begins. Keep the capture
  alive until the session's STOP has been observed, then close and flush it.
  Use a separate safety timeout and record whether it fired. The prior
  50-second capture ended before the final roughly nine seconds of video and
  STOP because its lifetime was not tied to the session
  ([baseline report](v30-pcap-baseline-2013600-20261105.md#coverage-failure)).
- Record the unused frame-ID range, run clocks, source clip and slot range,
  sender/wait hashes, trace epoch, initial counters, and capture file path.

## Test matrix

| Pass | Setup and checks | Record / acceptance evidence |
|---|---|---|
| Baseline | One localhost sender run using the unchanged host wait and the selected first 600 Xonotic slots. | Intended deadlines, actual wakes, socket-send duration, full-packet and frame-boundary gaps, capture/encode/replacement/partial/skip/ACK counts, process and pacing-thread CPU, memory, queue bounds, and cleanup. |
| Candidate | Repeat with only the host wait changed; same clip, slots, sender settings, receiver reference, and capture lifecycle. | Same fields as baseline; report total process CPU separately from pacing-thread CPU. Check no stale send, catch-up burst, missed deadline, feedback expiry, queue growth, or cleanup regression. |
| Repeatability | Alternate baseline and candidate in nonconcurrent runs, preserving each run's artifacts. | Compare distributions and run-to-run variability; do not compare concurrent variants. |
| AV/input liveness | Run concurrent localhost input-only AV while video is active; exercise normal input lease, absent/late input, and video-health failure. | Input packets and lease state, video health outcome, STOP, neutral controller state, socket/backend/audio cleanup, thread completion, and bounded AV receive/keepalive cadence. Audio load is a separately labeled later pass. |
| Wait boundaries | Deterministic unit coverage for early wake, oversleep, cancellation/shutdown, socket failure, feedback timeout, and lease expiry. | No post-deadline spin; original liveness/expiry checks still run; cancellation exits promptly; exceptions propagate and cleanup completes. |
| Local soak | Only after short comparisons pass, run the selected candidate for five minutes on localhost. | Bounded queues and memory, stable pacing/CPU, no liveness or cleanup regression, and retained logs/capture. This remains a local result. |

Record receiver decode/presentation and queue/core counters where available;
host sends or interface capture do not prove RF delivery or physical display.
Keep capture/encode/replace/partial/skip/ACK and STOP/power-save restoration as
separate outcomes.

## Existing local regression commands

Use the existing `tools/gamebub/.venv`; do not run `uv sync` or alter its
optional extras for this matrix. From `tools/gamebub`, run the focused AV/video
suite after the implementation is ready:

```powershell
& .\.venv\Scripts\python.exe -m unittest -v test_stream_sender test_live_session test_live_session_loopback test_av_session
```

Run the pacing-candidate tests from their directory with the same lab
interpreter:

```powershell
& ..\..\.venv\Scripts\python.exe -m unittest -v test_candidate
```

The broader AV launcher regression command documented in
[`SESSION-LAUNCHER.md`](../SESSION-LAUNCHER.md#testing) includes
`test_live_audio`, `test_session_launcher`, and the localhost loopback suite.
Commands above are recommendations only; this note does not claim they passed.

## Read-only audit findings

- [`test_live_session_loopback.py`](../test_live_session_loopback.py#L152) uses
  real localhost AV datagrams and checks audio on/off, input packets, and
  controller release, but does not run a video sender concurrently.
- [`live_session.py`](../live_session.py#L63) accepts an optional video-health
  callback and invokes it each AV-loop iteration
  ([loop](../live_session.py#L103)). A combined test can use this seam to
  verify concurrent input-only liveness and cleanup when video health fails.
- [`test_stream_sender.py`](../test_stream_sender.py#L1128) exercises silent
  localhost video-peer feedback suppression/recovery independently; it does
  not cover AV input during pacing waits.
- [`stream_sender.py`](../stream_sender.py#L485) bounds the guarded sleep into
  50 ms slices. The current laboratory candidate test only checks that a wait
  over 50 ms delegates to the existing guarded sleeper
  ([candidate test](host-pacing-study-20261104/test_candidate.py#L24)).
  Candidate integration should verify liveness checks across waits and prompt
  cancellation while preserving no-catch-up behavior.
- The prior capture coverage issue is documented in the
  [v30 partial-capture report](v30-pcap-baseline-2013600-20261105.md#coverage-failure):
  capture did not span the media session through STOP. Root-owned orchestration
  should own capture start/stop with the AV session lifecycle and report the
  safety-timeout outcome separately.
