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
- Start the packet capture before AV or video media begins. Keep the owned
  capture alive through STOP, let its bounded safety autostop finish naturally,
  then verify the actual STOP packet in the finalized capture. Record the
  autostop and any forced cleanup separately; finalization can take about two
  minutes after media ends. The prior
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
optional extras for this matrix. From the repository root, run the focused AV/video
suite after the implementation is ready:

```powershell
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && .venv/Scripts/python.exe -m unittest -v test_stream_sender test_live_session test_live_session_loopback test_av_session'
```

Run the pacing-candidate tests from their directory with the same lab
interpreter:

```powershell
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c '../../.venv/Scripts/python.exe -m unittest -v test_candidate'
```

The broader AV launcher regression command documented in
[`SESSION-LAUNCHER.md`](../SESSION-LAUNCHER.md#testing) includes
`test_live_audio`, `test_session_launcher`, and the localhost loopback suite.
Commands above are recommendations only; this note does not claim they passed.

## Morning hardware sequence

The morning sequence starts with the existing build50 JPEG/MSV1 and AV v1
endpoint. It requires no firmware flash or custom endpoint. Confirm that the
receiver is freshly available; record its actual app/build/FPGA identity,
address, queue settings, baseline counters, explicit host bind address, and
camera coverage through STOP. If those readiness facts cannot be confirmed,
do not start media. Use the same saved Xonotic clip at offset zero for both
passes (SHA-256
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`). Keep
capture on the same interface and retain it through STOP and natural safety
autostop/finalization.

1. Run a 30-second 20 fps, 4 Mbps, Q25 legacy-sampler control with input-only
   AV. Keep physical PC audio capture and virtual gamepad injection off. Use
   the unchanged `sleep` wait and 600 microsecond default spin setting. Reserve IDs
   2,014,200 to 2,014,799 only after confirming they are fresh and unused.
2. Repeat those settings with the same clip, offset, capture interface, legacy
   sampler, input-only AV and 600 microsecond tail; change only the host wait to
   `hybrid`. Reserve IDs 2,014,800 to 2,015,399 after a separate fresh-ID check.
3. Before extending the run, reconcile send, feedback and receiver counters;
   verify the actual STOP datagram in each finalized capture. Retain capture
   interface/point/drop counts, packet gaps, host CPU, receiver queue/core
   counters, and camera coverage limitations.
4. After the short pair passes, run a five-minute comparison at the same 20 fps
   and 4 Mbps settings. Keep the legacy sampler for this first hardware control
   comparison. Stop escalation on queue saturation, identity mismatch, capture
   coverage failure, or cleanup errors.
5. Treat a later 30 fps capacity probe as a distinct source-policy step. The
   native sampler may be selected only for a matching nominal 30 fps CFR source
   whose rational PTS cadence passes validation. Record that policy change; it
   is not like-for-like with the preceding 20 fps legacy-sampler control.

Change one diagnostic variable at a time: frame rate, video bitrate cap, or
wait/tail setting. The 400 microsecond tail has been exercised in localhost 30 fps,
8 Mbps video plus synthetic full-rate audio runs; this is not hardware proof
and does not qualify it for the initial 20 fps comparison. Do not change frame
rate, bitrate and pacing tail together.

The following PowerShell examples show the current wrapper flags; they are
examples only and were not executed. First list the local dumpcap interfaces,
then set `$CaptureInterface` to the exact selected interface name from that
output. Do not reuse another machine's interface number. Set the receiver and
bind variables to the values confirmed during readiness. The two output
directories are distinct and must not already exist.

```powershell
$Clip = 'C:/ai/sunshine-gamebub/tools/gamebub/artifacts/media/Xonotic-0-8-2-gameplay.webm'
$Receiver = '<receiver IPv4 from readiness check>'
$BindAddress = '<host source IPv4 from readiness check>'
& 'C:\Program Files\Wireshark\dumpcap.exe' -D
$CaptureInterface = '<exact interface name selected from dumpcap -D>'
$SessionLauncher = 'C:/ai/sunshine-gamebub/tools/gamebub/start_gamebub_session.ps1'
$OutputRoot = 'C:/ai/sunshine-gamebub/tools/gamebub/artifacts/morning-20261105'

# 20 fps, 4 Mbps, Q25 legacy control; default sleep wait.
& $SessionLauncher -Receiver $Receiver -BindAddress $BindAddress `
    -Video -Clip $Clip -LoopClip -ClipSelection legacy -AvInput `
    -Seconds 30 -FPS 20 -Quality 25 -Mbps 4 -PacingWait sleep -PacingSpinUs 600 `
    -CaptureInterface $CaptureInterface -StartFrameId 2014200 `
    -Output (Join-Path $OutputRoot '20fps-4mbps-legacy-sleep')

# Matched candidate; only the host wait changes.
& $SessionLauncher -Receiver $Receiver -BindAddress $BindAddress `
    -Video -Clip $Clip -LoopClip -ClipSelection legacy -AvInput `
    -Seconds 30 -FPS 20 -Quality 25 -Mbps 4 -PacingWait hybrid -PacingSpinUs 600 `
    -CaptureInterface $CaptureInterface -StartFrameId 2014800 `
    -Output (Join-Path $OutputRoot '20fps-4mbps-legacy-hybrid600')
```

Allow capture's bounded natural tail after STOP; finalization may take roughly
two minutes. The launcher records `media_end_utc` separately from final
`end_utc` and verifies the actual STOP packet in the finalized capture. The
latest localhost results are tracked in
[`overnight-host-pacing-20261105.md`](overnight-host-pacing-20261105.md).
Custom CP23 testing stays gated on a matching complete decoder and loader;
JPEG success does not clear that gate.

## Initial read-only audit

These observations describe the starting implementation. The overnight work
added concurrent AV/video tests, wait-boundary coverage and owned capture
through STOP; see the [current checkpoint](../OVERNIGHT-WINDOWS-STATUS-20261105.md).

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
