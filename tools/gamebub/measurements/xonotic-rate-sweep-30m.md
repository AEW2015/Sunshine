# Thirty-minute localhost bitrate stages

On November 3, 2026, the standalone host replayed the same pinned Xonotic
recording described in [xonotic-source.json](xonotic-source.json), looping it
as necessary, through the pinned MoonBub Python reassembler on localhost.
Each stage used 54,000 target slots at 30 fps, a 200 ms host age deadline,
JPEG quality range 20..75 and one listed MSV1 cap. The source is 1024x600,
scaled without distortion within the 720x480 canvas. The four 30-minute
stages ran sequentially in ascending cap order. Other host tests, development
and normal activity ran concurrently; these are not isolated comparisons.
The sender code was loaded from commit `5eac7a18` at sweep startup, before
later feedback-policy and sweep-health changes. The clip repeats; this is not
unique gameplay for the full duration.

| MSV1 cap | Complete reference frames | Complete FPS | Mean MSV1 Mbps | Skipped slots | Waiting JPEG replacements | Incomplete sends | Most common quality |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2 Mbps | 21,613 | 12.00 | 1.701 | 12 | 32,372 | 3 | 20 (53,978 encodes) |
| 5 Mbps | 48,335 | 26.85 | 3.823 | 3 | 5,662 | 0 | 20 (53,127 encodes) |
| 10 Mbps | 52,671 | 29.26 | 6.323 | 4 | 1,325 | 0 | 40 (6,216 encodes; adaptive range varied) |
| 20 Mbps | 53,806 | 29.89 | 9.851 | 1 | 193 | 0 | 75 (all 53,999 encodes) |

Each stage lasted approximately 1,800.3–1,800.5 seconds including final
feedback grace. Every stage reported zero invalid datagrams, reference reply
errors, and dropped log records. The reference feedback's drop field is its
invalid-datagram count; it is not a physical dropped-frame count and does not
count every abandoned incomplete frame. The physical device was not involved.
Mean traffic is MSV1 bytes over full duration; it excludes UDP/IP/Wi-Fi
overhead, audio and input. A cap is not measured radio throughput.

For complete sends, host-assigned timestamp-to-final-send median/p95/max was
112.40/143.02/195.13 ms at 2 Mbps, 57.99/82.00/133.25 ms at 5 Mbps,
44.71/69.72/141.44 ms at 10 Mbps, and 37.91/55.47/107.31 ms at 20 Mbps.
These nearest-rank quantiles covered every complete send in each stage. Host
timestamps are assigned after source retrieval, so they exclude earlier source
and capture wait; they are not glass-to-glass latency.

Logs and stage summaries remain under the ignored local
`artifacts/rate-sweep-30m-stages/` directory. Reproduce with a new output path
and the [rate sweep instructions](../README.md); use `--rates 2,5,10,20
--frames 54000 --fps 30 --quality 75 --min-quality 20 --max-age-ms 200`.
Different load, source motion, encoder versions or network conditions can
produce different results. No ESP32, QSPI, FPGA, display, audio, or Wi-Fi
performance was verified by this experiment.
