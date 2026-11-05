# Host pacing and localhost video results — 2026-11-05

## Scope

These are localhost sender/receiver experiments on the Windows reference stack. The peer confirms datagrams and protocol feedback only; `end_to_end_verified` and `hardware_playback_verified` are false. The five-minute AV run contacted no hardware. None of these results demonstrates RF delivery, real-device decode, or displayed playback.

## Saved-clip ABBA run

The 30-second ABBA run compared `sleep`, `hybrid`, `hybrid`, `sleep` on the same saved clip, revision `75f8497b6ffefadd8c0403728b93ccfbbfa02f52` and reference SHA `01a083f4794c7ced7e73eece60eac9d32cdacf589c6bc72b6c91c72e945cc9e5`.

| Mode / order | Submitted | Receiver complete | Replaced | Sender-thread CPU | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| sleep / 0 | 600 | 526 | 74 | 0.141 s | 0 invalid datagrams, 0 reply errors |
| hybrid / 1 | 600 | 588 | 12 | 1.156 s | 0 invalid datagrams, 0 reply errors |
| hybrid / 2 | 600 | 587 | 13 | 1.203 s | 0 invalid datagrams, 0 reply errors |
| sleep / 3 | 600 | 526 | 74 | 0.281 s | 0 invalid datagrams, 0 reply errors |

Across this short saved-clip run, hybrid sent more complete frames and had fewer replaced frames, while consuming more sender-thread CPU. It is a localhost queue/feedback result, not a playback-quality result.

## Five-minute AV soak

The localhost hybrid soak ran for 300.32 seconds. It submitted and encoded 6,000 video frames; the peer completed 5,926, with 74 encoded replacements, 0 receiver drops, 0 invalid datagrams, and 0 reply errors. The sender reported 29,707 log records and no logging drops. The AV peer accepted 9,789 input packets; there were no invalid or stale input packets, timeouts, or cleanup errors. `STOP` was sent and observed by the peer. Audio injection was off and the run did not contact hardware.

Measured process CPU was 142.28 seconds, or 47.4% of one core over the run. Sender-thread CPU was 11.63 seconds (3.87% of elapsed time). The pacing wait reported 25.49 seconds of spin wall time, 0.42 seconds of spin thread CPU, and an 8.49% spin-wall fraction of elapsed time. Thread-time readings have coarse Windows accounting resolution, so treat the thread CPU percentage as approximate; the process-level figure is the more stable utilization measure here.

## Native 30 fps capacity snapshots

These separate 30-second localhost video runs used 900 unique native-decoded source frames at 30/1 fps, without resampling or looping. Added source timestamp telemetry recorded 900 samples and zero timestamp repeats. Both runs had zero invalid datagrams, reply errors, and reported receiver drops. At 6 Mbps, the peer completed 873 frames (27 encoded replacements); process CPU was 21.13 seconds (69.6% of elapsed time). At 8 Mbps, the peer completed 900 frames; process CPU was 27.63 seconds (91.1% of elapsed time). Both had 25 final quality and no hardware contact. These are capacity observations and do not establish that every frame was decoded or displayed by a target device.

## Wait-probe context and configuration

The clean localhost 80-frame probes compare sleep with precise wait and sleep with timer-period handling. They received all 80 frames in each case and showed similar median send gaps and deadline lateness for sleep versus precise wait. In the later 8-period tail sweep, sleep median gap/deadline lateness were 2.984/0.856 ms; a 600 μs spin tail measured 2.155/0.028 ms, while 800 μs and 900 μs tails used more thread CPU. These short probes do not qualify full-session tradeoffs. The separate probe files and their per-period summaries retain the exact observations.

The existing default remains `sleep`; the 600 μs hybrid tail is opt-in. The AV soak and native snapshots used the hybrid mode explicitly. This report does not recommend changing the default based on these localhost runs.

## Evidence files

- `artifacts/hybrid-fullclip-20261105/summary.json` and per-period summaries
- `artifacts/hybrid-av-soak-5m-20261105/result.json` and `session/video-summary.json`
- `artifacts/hybrid-native-30fps-20261105/summary.json`
- `artifacts/precise-wait-20261105/clean-native-abba-0036/summary.json`, `clean-period-abba-0037/summary.json`, and `clean-tails-0038/summary.json`
