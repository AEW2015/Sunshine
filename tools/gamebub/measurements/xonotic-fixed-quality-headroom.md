# Fixed-quality localhost pacing headroom comparison

Two sequential 15-minute stages used the pinned Xonotic clip described in
[xonotic-source.json](xonotic-source.json), the pinned localhost MoonBub Python
reference, 27,000 target slots at 30 fps, a 200 ms host age bound, and fixed
baseline 4:2:0 JPEG quality 75. The tested sender was the latest committed
version at the run's start (including bounded in-flight feedback grace). The
clip is repeated; the output is scaled without distortion into 720x480. Other
host activity was not controlled. This is a single fixed-order comparison,
not evidence of physical Wi-Fi capacity or a causal performance difference.

| MSV1 cap | Reference complete | Full-duration FPS | Mean MSV1 Mbps | Skipped slots | JPEG replacements | Host timestamp-to-send median / p95 / max |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20 Mbps | 26,888 | 29.865 | 9.844 | 0 | 112 | 37.83 / 55.75 / 106.17 ms |
| 30 Mbps | 26,878 | 29.854 | 9.841 | 3 | 119 | 37.98 / 55.50 / 149.95 ms |

Each duration was approximately 900.305 seconds including final feedback
grace. Both stages were marked healthy; reference invalid datagrams and reply
errors, incomplete sends, and logger dropped records were zero. Quality was 75
on every encode. The nearest-rank percentiles cover all completed sends. Host
timestamps are assigned after source retrieval and do not measure capture wait
or display latency. MSV1 rates exclude UDP/IP/Wi-Fi overhead, audio and input.
The reference feedback drop field tracks invalid datagrams and is not a
physical dropped-frame counter.

The higher cap did not improve the measured FPS in this one comparison; load,
run order, the repeated clip and scheduling could affect the result. Do not
infer that 30 Mbps is suitable for the handheld. Logs and result records remain
in ignored `artifacts/fixed-q75-pacing-headroom/`. Reproduce with a new output
directory using the [rate sweep instructions](../README.md) and `--rates 20,30
--frames 27000 --fps 30 --quality 75 --min-quality 75 --max-age-ms 200`.
