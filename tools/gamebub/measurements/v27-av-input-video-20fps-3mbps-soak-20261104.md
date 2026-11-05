# v27 five-minute 20 fps request at 3 Mbps

UTC 2026-11-05 04:19:45.072–04:24:45.855 (2026-11-04 21:19:45–21:24:45
America/Denver). Host video duration including feedback drain: 300.442 s.
Source 192.168.0.47, destination 192.168.0.157:5533 (MSV1) and :5534 (AV v1).
Last operator-confirmed receiver: v27/build50, overlap active, 32-slot queue.
No source code, installed Sunshine service, firmware or FPGA changes were made.

Settings: 720×480 desktop canvas, configured 20 fps, JPEG quality/minimum 25,
3 Mbps video cap, 200 ms maximum age, bilinear scaling, zero host shift.
Input-only AV remained active through video; audio and gamepad injection were off.
The desktop content was not controlled or independently identified as a game.

| Host result | Value |
|---|---:|
| Target IDs | 2,001,000–2,006,999 |
| Submitted / encoded | 6,000 / 6,000 |
| Complete sends | 5,360 |
| Replaced before transmission | 640 |
| Partial sends / scheduler skipped slots | 0 / 0 |
| Accepted / rejected matching ACKs | 5,329 / 29 |
| Sends without matched feedback | 2 |
| Extra unmatched feedback events | 3 |
| Complete-send rate including drain | 17.840 fps |
| Accepted-ACK rate over host duration | approximately 17.737 fps |
| JPEG encoded bitrate, including replacements | 2.641 Mbps |
| MSV1 transmitted datagram bitrate | 2.319 Mbps |

All 6,000 target slots reconcile as 5,360 complete sends and 640 encoded
replacements. The 5,360 sends reconcile as 5,329 accepted ACKs, 29 rejected
ACKs and two unresolved sends. Datagrams exclude UDP/IP/Wi-Fi overhead.
Quality remained 25; no pipeline error or partial-send event was recorded.

Final feedback was 6,202 received / 31 dropped, versus the preceding confirmed
873 received / 2 dropped: +5,329 accepted and +29 dropped. The receiver operator
subsequently confirmed final received, decoded and presented totals of 6,202
each (+5,329 each), and dropped frames 31 (+29). All accepted frames therefore
have matching decode and presentation counts.

Receiver queue packet drops were 45; high-water reached 32/32 and the queue was
empty afterward. First recorded queue drop: frame 2,004,708, offset 5,120.
Core completed was 6,202, with a separate core drop count of 27; faults,
overflows, underruns and transport overflows were zero. These are operator-
reported device measurements, not direct Windows register reads.

All 29 retained failure records explicitly report `Invalid/lost frame: Sequence`.
One is frame 2,001,110; the remaining 28 cluster over approximately 5.15 seconds
within IDs 2,004,706–2,004,810. Queue saturation is confirmed but does not
individually explain every failure. Backward offsets were also recorded and
their underlying cause remains unresolved. Busy admission was not reported.

| Frame | Receiver expected offset | Receiver observed offset |
|---|---:|---:|
| 2,001,110 | 18,432 | 19,456 |
| 2,004,706 | 9,216 | 10,240 |
| 2,004,708 | 4,096 | 8,192 |
| 2,004,748 | 5,120 | 14,336 |
| 2,004,773 | 16,384 | 1,024 |
| 2,004,807 | 14,336 | 6,144 |
| 2,004,810 | 10,240 | 11,264 |

For these seven frames, the host packet records contain both selected offsets
in strictly increasing send-call order. Selected packet gaps were approximately
2.9–3.9 ms. In particular, host frame 2,004,773 logged offset 1,024 before
16,384, and frame 2,004,807 logged 6,144 before 14,336. These are successful
post-send API-call timestamps, not NIC departure or RF timestamps; they do not
locate downstream loss/reordering or establish a receiver bug. Exact host times
and gaps are retained in local `receiver-reconciliation.json` and `video.jsonl`.

Rejected IDs: 2,001,110; 2,004,706; 2,004,708; 2,004,714; 2,004,716;
2,004,723; 2,004,725; 2,004,737; 2,004,748; 2,004,752; 2,004,753;
2,004,756; 2,004,757; 2,004,764; 2,004,765; 2,004,769; 2,004,773;
2,004,780; 2,004,781; 2,004,785; 2,004,786; 2,004,790; 2,004,796;
2,004,797; 2,004,802; 2,004,803; 2,004,807; 2,004,808; 2,004,810.
The two complete sends without matching feedback were 2,004,772 and 2,004,806.
These remain unknown outcomes; receiver counters alone do not identify them.

Input-only AV source port 58468, cookie `907a079930608ac9`: 14,433 validated
post-handshake MSI1 packets, sequences 1–14,433 without intervening gaps,
all button masks zero. Invalid/stale packets, input timeouts and audio sends
were zero. MSI1 states: 10,337 at state 5, 4,096 at state 1. Normal video exit
was followed by one successfully sent STOP, control sequence 2,879. Cleanup
errors and forced termination were zero. The receiver operator verified AV
inactive after STOP and power saving restored from NONE (0) to MIN_MODEM (1),
with zero entry or restoration errors. This does not isolate power saving as
a causal variable.

Both loggers reported zero dropped records or write errors. Raw local evidence:
`tools/gamebub/artifacts/v27-av-input-video-20fps-3mbps-soak-2001000-20261104/`,
including frame/packet `video.jsonl`, `av.jsonl`, `completion.json`,
`video-summary.json`, `sender-analysis.json`, `av-analysis.json`,
`frame-outcomes.json`, `receiver-reconciliation.json`, `manifest.json` and exact
orchestration `run.py`. Receiver evidence supplied by the operator is at
`C:/Users/lavat/codex/moonbub/evidence/hardware-v27-headroom-20261105T021917Z/continuation/run-2001000-20261104T212620/`,
files `failure-records.txt`, `result.json` and `reconciled-result.json`; those
remote-machine paths were not independently opened on Windows.

This did not sustain all 20 target frames per second: host replacement and
receiver-reported rejections appeared over the longer run. Camera samples
confirmed changing video/desktop content for the first 2m40s. Coverage ended
before the remainder, including the rejection cluster, so freezes there remain
unknown. No optical latency or uninterrupted full-run motion claim is made.

Before increasing rate, investigate receiver queue consumption stalls and
packet identity/order around the sequence failures, correlated with the host
timestamps. A larger queue alone does not establish sustained throughput.
Keep host replacements separate from receiver failures; the former also show
that this content did not sustain all 20 target frames per second under the
existing pacing and bitrate cap.
