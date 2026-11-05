# Short 6 Mbps pacing headroom probes — 2026-11-05

These were two 30-second localhost AV runs from the same native 30 fps saved clip, with a 6 Mbps video cap and synthetic audio. They differ in configured hybrid spin tail (400 vs 600 µs). Each sent 900 source samples with zero repeated source timestamps. This is one run per setting, not a randomized experiment or sustained qualification.

| Hybrid spin tail | Sent / accepted | Encoded replacements | Measured send rate | App wire rate | Sender process CPU | Sender thread CPU |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 400 µs | 827 / 827 | 73 | 27.25 fps | 4.43 Mbps | 17.39 s | 1.19 s |
| 600 µs | 871 / 871 | 29 | 28.70 fps | 4.72 Mbps | 19.48 s | 2.95 s |

Both encoded about 4.728 Mbps, below the configured 6 Mbps cap. The 600 µs run sent 44 more frames and had 44 fewer encoded replacements. These replacements occurred in the sender pipeline before send; they are not receiver packet drops. The localhost reference reported zero receiver-dropped frames in both runs. The evidence is too short and unrandomized to attribute the difference to spin-tail setting or predict sustained behavior.

Within each sent frame, I computed intervals between adjacent packet timing records only when both UDP payloads were the full 1,024 bytes. Frame boundaries and intervals adjacent to the final short packet are excluded. The samples are post-send event timestamps, not direct measurements of socket or wire transmission duration.

| Hybrid spin tail | Full/full intervals | Median | P95 | P99 | Maximum |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 400 µs | 14,550 | 1.852 ms | 2.151 ms | 2.481 ms | 5.566 ms |
| 600 µs | 15,492 | 1.468 ms | 1.929 ms | 2.314 ms | 3.817 ms |

Audio accounting matched in both runs: 400 µs published/sent 2,930/2,927 blocks with three queued at close; 600 µs published/sent 2,928/2,926 with two queued. Neither had stale drops, queue evictions, peer sequence gaps, or dropped log events.

The separate 30-minute native 8 Mbps / 400 µs localhost AV run remains the longer local target and reported zero invalid datagrams. This supports that local test configuration only; it does not establish receiver decode, physical presentation, playback, or hardware qualification.

Source summaries and packet timing records are retained under `tools/gamebub/artifacts/overnight-long-soak-20261105/headroom-6mbps-30s` and `.../headroom-6mbps-600us-30s`. See [pacing-headroom-6mbps-20261105.json](pacing-headroom-6mbps-20261105.json) for raw values and scope limits.
