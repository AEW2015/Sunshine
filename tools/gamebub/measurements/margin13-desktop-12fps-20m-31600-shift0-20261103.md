# Margin13: twenty-minute 12 fps desktop run, zero host shift

The requested live primary-desktop capture ran from 192.168.0.47:55534 to
192.168.0.157:5533 using video-only MSV1, 720x480 baseline JPEG, fixed quality25,
a 2 Mbps sender cap, 200 ms frame-age deadline and zero host shift. The operator
reported margin13, timing preset0, overlap/32 queue slots and active receiver
and camera recording. No receiver settings or installed Sunshine service were
changed. The game/content was operator controlled; this was not process-specific
capture or independently verified continuous gameplay.

| Measurement | Result |
| --- | --- |
| America/Denver host window | 2026-11-03 16:09:13.819 to 16:29:14.320 MST |
| UTC host window | 2026-11-03 23:09:13.819 to 23:29:14.320 |
| Sender duration, including startup/grace | 1200.496 seconds |
| Target frame IDs / scheduled slots | 31600..45999 / 14,400 |
| Submitted / encoded | 14,400 / 14,400 |
| Complete / partial / zero-byte sends | 14,055 / 94 / 4 |
| Stale encoded frames replaced / skipped capture slots | 247 / 0 |
| Feedback suppression / timeout events | 0 / 0 |
| Matched accepted / rejected ACKs | 13,837 / 197 |
| Complete sends without matched feedback at close | 21 |
| Heartbeats / unmatched feedback | 6,610 / 102 |
| Final received / dropped feedback | 15,437 / 293 |
| User-supplied starting received / dropped | 1,600 / 0 |
| Received / dropped counter delta from supplied baseline | +13,837 / +293 |
| Complete host send rate | 11.708 fps |
| Accepted counter delta per full host duration | 11.526 frames/s |
| Encoded JPEG / sent MSV1 bitrate | 1.455 / 1.477 Mbps |
| Encoded JPEG / sent MSV1 bytes | 218,329,470 / 221,672,527 |
| Packet timing frames / datagrams | 14,149 / 215,240 |
| Host packet gap ms min / p50 / p95 / max | 4.310 / 4.978 / 5.279 / 23.756 |
| Encode ms p50 / p95 / max | 3.085 / 4.360 / 22.409 |
| Complete host timestamp-to-send age ms p50 / p95 / max | 88.180 / 167.133 / 199.733 |
| Complete encoded queue age ms p50 / p95 / max | 0.213 / 57.531 / 87.688 |
| Logger records / lost records / I/O errors, final stdout | 77,415 / 0 / none |

All 197 matched rejections were for complete host sends. None of the partial
sends had a matched accepted or rejected ACK. The 21 pending IDs were also
complete host sends. Thus complete sends reconcile as 13,837 accepted + 197
rejected + 21 pending = 14,055. Encoded frames reconcile as 14,055 complete +
94 partial + 4 zero-byte + 247 replacements = 14,400.

The receiver's 13,837 new completions plus 293 new drops account for 14,130
outcomes, versus 14,149 nonzero host sends. Without receiver frame identities,
the 19-outcome difference cannot be assigned to specific pending or partial
frames. In particular, the 293 drops exceed 197 matched rejections plus 94
partials by two; numerical proximity is not proof of individual dispositions.
All outcome ID lists and packet records are retained for correlation.

There were no recorded capture errors or feedback timeout/suppression events.
The 98 incomplete send results are deadline-limited outcomes in the unchanged
sender, including 94 partial and four zero-byte refusals. The logger does not
identify which preflight/pre-wait/post-wait deadline guard fired per frame;
exact guard timing remains unknown. Zero-byte IDs are 37166,41965,44199,44211.
No adaptive quality change or JPEG retry was used.

The analyzer's counter tracker reports 13,836 received since its first feedback
baseline; that baseline is established after the first completion. Use the
operator's 1,600 baseline and the final 15,437 for the full-run +13,837 delta.
The JSONL summary omits final logger metadata, so the standalone analyzer marks
logging integrity unknown. The separate final stdout summary supplies logger
metadata: zero lost records, no I/O error and 77,415 written records, matching
the parsed JSONL count. Neither artifact was rewritten to hide that distinction.

## Receiver and interpretation limits

The operator subsequently supplied final receiver results. Starting decoded and
presented counters were both 5,310, with zero queue drops and a session queue
peak of24/32. Final decoded and presented totals were both19,147: increases of
13,837 each, matching accepted ingress and host accepted ACK totals. This
verifies receiver-reported decode/presentation accounting for every accepted
frame, averaging11.526 presentations/s over the full host window. It does not
establish distinct optical images or regular frame intervals.

| Independent receiver measurement | Final / run result |
| --- | --- |
| Received / decoded / presented | 15,437 / 19,147 / 19,147 |
| Received / decoded / presented increases | 13,837 / 13,837 / 13,837 |
| Dropped frames | 293 |
| Queue packet drops / peak / final occupancy | 505 / 32 of32 / 0 |
| First queue drop | Frame31985, offset7168 |
| Core faults / overflow / underruns / transport overflow | 0 / 0 / 0 / 0 |
| Separate core drop counter | 154 |
| Retained Busy / Sequence / unknown drop reasons | 126 / 71 / 96 |
| Application error counter | 2,338 |
| Final status | `Invalid/lost frame: Sequence` |

Queue saturation and Busy admission failures are now directly reported for
this run. Sequence failures alone do not prove network loss or queue overflow,
and the queue drop total does not assign a cause to each failed frame. The
197 retained failure IDs numerically match the197 host rejected ACKs; per-ID
comparison still requires the remote records. The96 drops without retained
reasons must not be assigned to the94 host partial sends from counts alone.
The154 core drops,505 packet drops and2,338 application errors have different
scopes and must not be added to293 frame drops.

Receiver-side camera samples reportedly show changing scenes across the
recorded portion. Coverage was partial, so brief freezes cannot be ruled out.
The host did not independently inspect these remote files or camera footage.
Operator-reported evidence is on the other machine under
`C:/Users/lavat/codex/moonbub/evidence/plan-receiver-runs/v20-build49-margin13-12fps-31600-45999-20261103/README.md`;
the interim snapshot is under
`v20-margin13-12fps-interim-20261103T233237Z/README.md` in the same parent.

Next, join retained failure IDs to the host outcome and packet-time records,
keeping Busy, Sequence and unknown dispositions separate. Inspect queue-drop
offsets alongside sender spacing before changing pacing or bitrate. A bounded
admission-wait experiment remains a separate receiver change; larger queues
alone cannot establish a fix for sustained consumer or decode service limits.

The host capture timestamp is assigned after acquisition. Its age excludes
acquisition time and does not measure game-to-photon latency. Packet timestamps
follow host socket sends; wall-clock estimates use a host monotonic/UTC anchor,
not synchronized receiver clocks. Achieved bitrate excludes UDP/IP/Wi-Fi bytes.
Unchanged desktop images may repeat. This run does not establish loss-free
12 fps playback or 30 fps support.

Artifacts under `tools/gamebub/artifacts`, prefix
`handheld-margin13-desktop-12fps-20m-31600-shift0-20261103`: `.jsonl`,
`-summary.json`, `-provenance.json` (including source hashes), `-packets.csv`,
`-packet-report.json`, `-analysis.json`, `-outcome-details.json` and
`-receiver-final.json` (operator-reported counters, not a local device query).
Export checked contiguous offsets and full JPEG lengths for complete sends.
No next stream was started.
