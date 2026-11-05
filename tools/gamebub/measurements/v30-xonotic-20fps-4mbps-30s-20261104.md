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
The receiver operator subsequently confirmed **523 received, decoded and
presented**, two dropped frames and zero application-queue packet drops.
Core status, queue high-water, trace-loss, full failure classification, camera
motion and power-save restoration await confirmation. These are operator-
reported device counters, not direct Windows register reads. Bitrates exclude
UDP/IP/Wi-Fi overhead.

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

### Selected failure-window packets

Capture timestamps (host Unix microseconds): frame **2,013,421**:
`1793859711151542`; frame **2,013,422**: `1793859711202169`.
Capture timestamp difference: 50.627 ms. Both frames were completely sent and
had matching rejected ACKs. Receiver's first failure expected offset 4,096 and
observed 5,120 in frame 2,013,421; its Sequence window is retained remotely.

| Frame | Offset | Host post-send monotonic seconds | Gap from preceding datagram |
|---|---:|---:|---:|
| 2,013,421 | 2,048 | 1354793.5106073 | 2.9794 ms |
| 2,013,421 | 3,072 | 1354793.5134483 | 2.8410 ms |
| 2,013,421 | 4,096 | 1354793.5164743 | 3.0260 ms |
| 2,013,421 | 5,120 | 1354793.5196654 | 3.1911 ms |
| 2,013,421 | 6,144 | 1354793.5224386 | 2.7732 ms |
| 2,013,422 | 0 | 1354793.5550626 | 6.6852 ms |
| 2,013,422 | 1,024 | 1354793.5574626 | 2.4000 ms |

All selected datagrams contained 1,024 payload bytes. The gap for frame
2,013,422 offset zero is measured from frame 2,013,421's final offset 15,360,
whose 239-byte payload was logged at `1354793.5483774`. The host logged a
successful offset-4,096 send before offset 5,120, with a 3.1911 ms gap. This
does not locate loss or reordering after the send API returns, and host and
receiver monotonic clocks cannot be subtracted directly.

Machine-readable exact selections plus **all packet timestamps for both frames**:
[v30-requested-packet-times-20261104.json](v30-requested-packet-times-20261104.json).

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
