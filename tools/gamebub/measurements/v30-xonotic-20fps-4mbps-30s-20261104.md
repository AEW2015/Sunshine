# v30 Xonotic 30-second control at 20 fps / 4 Mbps / Q25

Run **2026-11-04 23:21:29.573–23:22:00.490 America/Denver**
(UTC 2026-11-05 06:21:29.573–06:22:00.490). Host video duration including
feedback drain: 30.361 s. Source 192.168.0.47, destination 192.168.0.157:5533
video and :5534 AV. Start and STOP were within the supplied camera window.
Receiver readiness was operator-reported: v30, trace epoch 2 armed,
build50/overlap/32 slots unchanged, zero video/core baseline counters.

## Source and settings

Saved clip `Xonotic-0-8-2-gameplay.webm`, 48,552,136 bytes, SHA-256:
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
The file hash was checked before transmission. It started at **offset zero**,
using the same source adapter and beginning of the clip as the v29 run.
The loop-capable iterator did not reach the approximately 183-second clip end
within this 30-second test. Attribution/license: [xonotic-source.json](xonotic-source.json).

Settings: 720×480 canvas, original clip proportions retained, configured
20 fps, JPEG quality/minimum 25, 4 Mbps MSV1 cap, 200 ms maximum age,
bilinear scaling and zero host shift. Input-only AV remained active through
video; audio and virtual-gamepad injection were off. Streaming, encoding,
pacing, feedback and protocol source hashes are unchanged from v29.
Only artifact settings changed for the requested rate cap, duration, IDs,
receiver identity and start deadline. Firmware and bitrate both differ from
v29, and this is a shorter source interval, so do not attribute differences
to a single cause from the aggregate run totals.

## Host outcome

| Result | Count |
|---|---:|
| Target IDs | 2,013,000–2,013,599 |
| Submitted / encoded | 600 / 600 |
| Complete sends | 525 |
| Replaced before transmission | 75 |
| Partial sends / scheduler skips | 0 / 0 |
| Matched accepted / rejected ACKs | 523 / 2 |
| Pending feedback | 0 |
| Extra unmatched feedback events | 1 |
| Complete-send rate including drain | 17.292 fps |
| Encoded rate including drain | 19.762 fps |
| Encoded JPEG bitrate, including replacements | 3.151 Mbps |
| Transmitted MSV1 datagram bitrate | 2.797 Mbps |

Reconciliation: 600 = 525 complete sends + 75 encoded replacements;
525 = 523 accepted ACKs + two rejected ACKs. Rejected IDs:
**2,013,421 and 2,013,422**. Final receiver feedback: **523 received / 2 dropped**.
Receiver decode/presentation, queue/core, trace-loss, failure reasons, camera
motion and power-save restoration await operator confirmation. ACKs establish
ingress outcome only. Bitrates exclude UDP/IP/Wi-Fi overhead.

## Actual packet gaps

There were 10,230 logged successful datagram sends. The timestamps below are
host **post-send API-call timestamps**, not NIC/RF departure or receiver arrival.
Statistics use exact nearest-rank quantiles of retained samples.

| Gap class | Samples | Minimum | Median | p95 | p99 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Within frame | 9,705 | 2.163 ms | 2.984 ms | 3.215 ms | 3.772 ms | 17.874 ms |
| Tail to next SOF | 524 | 0.240 ms | 1.962 ms | 10.433 ms | 13.596 ms | 16.376 ms |
| All adjacent sends | 10,229 | 0.240 ms | 2.981 ms | 3.237 ms | 4.180 ms | 17.874 ms |

No gap was negative. All 133 sub-millisecond gaps were at frame boundaries;
none were within a frame. A short final payload has a shorter paced interval,
so a sub-millisecond boundary alone does not establish an unpaced burst.
The first and last post-send times span 29.998 s.

A full 1,064-byte MSV1 datagram has a nominal interval of **2.128 ms at 4 Mbps**.
The observed within-frame median of 2.984 ms is materially longer. This makes
host pacing/wait granularity worth measuring separately; it does not establish
a Windows scheduler root cause or a Wi-Fi capacity limit. The largest gap,
17.874 ms, was within frame 2,013,237 between offsets 11,264 and 12,288.
No pacing behavior was modified during this run.

## AV and logs

AV source port 60299, cookie `f9179c2cab7a7ce9`; HELLO was sent twice before
one START reached ACTIVE. Host validated 1,478 post-handshake MSI1 packets,
sequences 1–1,478 without intervening gaps, all masks zero. Invalid/stale
packets, input timeouts and audio sends were zero. States: 513 at state 1,
965 at state 5. One STOP was successfully sent, sequence 297, after video
exited 0. Cleanup errors and forced termination were zero.

Both loggers reported zero dropped records and no write errors. Full local
frame/packet evidence and exact artifact adapters:
`tools/gamebub/artifacts/v30-av-input-xonotic-20fps-4mbps-2013000-20261104/`:
`video.jsonl`, `av.jsonl`, `video-summary.json`, `manifest.json`,
`completion.json`, `sender-analysis.json`, `av-analysis.json`,
`frame-outcomes.json`, `packet-gap-analysis.json`, `run.py`, `clip_sender.py`
and `packet_gaps.py`. Production source and installed Sunshine were unchanged.

The test did not deliver all 20 target frames per second. Obtain v30's retained
failure identity/phase history before selecting a receiver fix; investigate
host pacing independently before raising the cap or configured FPS again.
