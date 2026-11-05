# Localhost native-CFR 30 fps video and synthetic AV, 30 minutes

Run: `artifacts/overnight-long-soak-20261105/audio-video-native-30fps-30m-0358`. The companion [JSON](localhost-av-native-30fps-30m-20261105.json) contains the summary SHA-256, hashes, and compacted memory statistics. The run used native clip selection at nominal 30 fps, Q25, an 8 Mbps video cap, hybrid pacing with a 400-microsecond tail, synthetic audio and independently sequenced AV input against localhost peers. Gamepad injection was off. It was operationally complete according to the run summary.

## Video and log coverage

The sender submitted and encoded 54,000 frames, sent 53,998, and received matching localhost reference completions and ingress feedback for all sent frames. Two encoded frames were replaced. There were zero partial frames, source timestamp repeats, skipped slots, pending feedback, invalid datagrams, or reply errors. Send rate over the video sender's 1,800.31838-second lifetime including its drain was 29.99358 fps. Over the complete harness lifetime, 1,800.78732 seconds including AV teardown, it was 29.98577 fps. Application wire traffic was 1,095,723,389 bytes, about 4.869 Mbps over the video sender's duration under the 8 Mbps cap. The saved clip loops; source timestamps do not establish 54,000 unique scenes.

Per-packet timing was explicitly off. The video and AV logs reported 41,507,604 and 31,122,232 bytes, respectively, below the 67,108,864-byte per-file limit, with zero dropped events. Full per-packet timing and full-packet gap distributions are therefore unavailable for this run.

## Synthetic audio accounting

The synthetic 48 kHz source captured 86,428,320 frames, equivalent to 1,800.59 seconds of modeled source samples. It published 172,189 encoded blocks: 172,184 sent, 3 evicted from the bounded publisher queue, and 2 queued at close. There were no stale drops, PCM drops, or capture errors. The localhost peer received all 172,184 sends.

Three sequence numbers were absent at the peer: 5,142, 12,903, and 145,573. They reconcile with the three counted publisher queue evictions and the sender's sequence-allocation-before-eviction behavior. The artifacts do not identify why the queue filled, so no cause is attributed. STOP was sent and observed; AV input reported 58,565 packets, zero invalid packets, stale packets, or timeouts, and no cleanup errors.

The synthetic callback log recorded 180,060 callbacks, a maximum callback gap of 16.4277 ms, two late intervals, and zero missed schedule periods. The precise waiter made 180,059 native calls, with no fallback, runtime failures, or spin. These report the synthetic source and wait instrumentation, not WASAPI capture or physical playback.

## Sampled memory and CPU

The harness recorded 61 grouped memory samples at 30-second intervals. The startup sample was excluded below; there were 60 warm samples and zero post-exit child samples. These sampled values are observations, not memory bounds. Working set and private bytes are reported separately for the harness and its owned video sender:

| Process | Working set min / p50 / p95 / max | Private bytes min / p50 / p95 / max | Warm CPU one-core interval p50 / p95 / max |
|---|---:|---:|---:|
| Harness | 43,032,576 / 43,524,096 / 43,532,288 / 43,532,288 | 37,552,128 / 37,961,728 / 37,961,728 / 37,961,728 | 22.104% / 23.540% / 26.341% |
| Video sender | 49,577,984 / 56,739,840 / 58,345,677 / 58,826,752 | 43,180,032 / 49,827,840 / 51,707,085 / 53,055,488 | 58.379% / 65.609% / 67.683% |

Harness-process CPU was 399.516 seconds and includes synthetic audio encoding plus local reference and AV peer work. Video-sender process CPU was 1,054.625 seconds; sender-thread CPU was 102.156 seconds. These scopes differ. UV formatting and native compilation/testing overlapped the run, so these CPU figures are stress observations, not a clean comparative benchmark.

## Scope

This was a localhost wire/reference exercise, not HIL. It does not verify RF delivery, QSPI or FPGA playback, receiver presentation, DAC buffering, physical audio, clock drift, or acoustic output. Source and harness snapshots, exact child arguments, and source hashes are retained in the run artifact and summarized in the JSON.
