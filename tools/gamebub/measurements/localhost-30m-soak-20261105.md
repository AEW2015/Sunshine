# Localhost 30-minute video/input stress run — 2026-11-05

This finite localhost stress run completed with the harness summary marked
`complete=true`. It ran from **09:00:29.410 UTC** to **09:30:30.275 UTC**
(02:00:29–02:30:30 Denver). A native build overlapped until about 02:22 Denver,
and Python regression activity overlapped for about 19 minutes. Treat CPU,
memory, and throughput as operational stress observations, not a clean
performance benchmark.

## Reconciled result

The run submitted and encoded 36,000 slots from a looped saved Xonotic clip at
20 fps, 4 Mbps cap, Q25, input-only AV, hybrid wait with a 600 μs tail. The
sender completed 35,533 frame sends; the localhost reference completed and
acknowledged all 35,533, with zero pending feedback. The remaining 467 slots
were encoded replacements. Scheduler skips were zero; receiver drops, invalid
datagrams, reply errors, and reported send errors were zero. No partial-send
errors appeared in the sender log. Replacements are sender queue behavior, not
receiver loss.

The 35,533 completed frames over the sender's **1,800.311-second duration
including feedback drain** equal 19.737 frames/s, against the nominal 20 fps
slot rate. Application wire bytes totaled 718,416,491 (3.192 Mbps from bytes
and duration); encoded JPEG bytes totaled 702,690,445 (3.123 Mbps). These rates
exclude UDP/IP and radio overhead. The result does not establish RF delivery,
MoonBub decode, or physical presentation.

The saved source supplied 36,000 native samples with zero reported repeated
source timestamps. It was looped and was not resampled. The host received
58,705 valid input packets; invalid/stale input packets and input timeouts were
zero. STOP was sent and observed, with no AV cleanup errors. Audio, gamepad
injection, and capture were disabled.

## CPU and sampled memory

Windows `GetProcessMemoryInfo` sampled working set and private bytes about every
30 seconds. The 62 sample records include startup and final samples. The warmed
distributions below use samples at elapsed time ≥60 seconds, report nearest-rank
p50/p95, and exclude the final post-exit video-sender handle sample. Values are
sampled observations, not peak or hard memory bounds.

| Process | Warm samples | Working set min / p50 / p95 / max | Private bytes min / p50 / p95 / max | First-to-last warm change (working / private) |
| --- | ---: | --- | --- | --- |
| Launcher and loopback peers | 59 | 38.60 / 41.36 / 43.75 / 43.82 MiB | 33.82 / 36.36 / 38.59 / 38.59 MiB | +5.22 / +4.62 MiB |
| Video sender | 58 | 50.17 / 53.57 / 55.21 / 56.26 MiB | 44.23 / 46.89 / 48.45 / 49.71 MiB | +3.76 / +2.52 MiB |

The first launcher sample was before warm-up; the first sender sample was taken
at spawn. Neither is a memory bound. The launcher process includes the finite
run's loopback peer, which retains control packets for the session duration;
this does not establish steady-state heap behavior. The exited sender's final
sample is not treated as resident memory.

Video-sender process CPU was **904.45 s** (50.24% of one core over the measured
duration); sender-thread CPU was **64.28 s** (3.57% of elapsed time). The
launcher/peer process accumulated **32.81 CPU-seconds** by its final sample
(about 1.82% of one core over the run). Build/test overlap limits performance
comparisons from these numbers.

## Logging and provenance

Video JSONL was 50,060,542 bytes and AV JSONL was 13,785,471 bytes; each remained
under the separate 64 MiB file limit, with zero reported logger drops. The
machine-readable [summary](localhost-30m-soak-20261105.json) retains memory
distributions, CPU accounting, configuration, clip and source hashes. Full
controller/session/video/AV artifacts remain in the ignored
`artifacts/overnight-long-soak-20261105/runs/stress-20fps-30m-0203/` directory.

This is a localhost sender/reference stress result. It does not demonstrate
hardware playback or end-to-end video/audio quality.
