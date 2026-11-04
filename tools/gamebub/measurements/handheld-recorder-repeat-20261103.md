# Moving-video repeat with continuous receiver recording

The receiver operator enabled a continuous one-hour serial recorder before
this five-minute repeat. Sender source code and pacing were unchanged. The
installed Sunshine service was not replaced or restarted. This is standalone,
video-only MSV1, not integrated Sunshine gameplay.

| Item | Recorded result |
| --- | --- |
| Host / receiver | 192.168.0.47:55534 / 192.168.0.157:5533 |
| Host window, America/Denver | 2026-11-03 08:45:30.276 to 08:50:30.616 MST |
| Same window, UTC | 2026-11-03 15:45:30.276 to 15:50:30.616 UTC |
| Sender duration | 300.225 seconds including shutdown/grace |
| Target / canvas / quality | 5 fps / 720x480 / fixed JPEG quality 25 |
| MSV1 cap / JPEG guard / retry | 2 Mbps / 262,144 bytes / disabled |
| Frame IDs / complete sends | 5117..6616 / 1,500 |
| Skipped / suppressed / pending feedback | 0 / 0 / 0 |
| Accepted / rejected feedback | 1,488 / 12 (0.8% rejected) |
| Heartbeats / unmatched feedback | 1,358 / 18 |
| Received / dropped baseline | 4,294 / 297 |
| Final received / dropped feedback | 5,782 / 309 |
| Known-baseline delta | +1,488 received / +12 dropped |
| Sender / receiver-counter-confirmed presented FPS | 4.996 / 4.956 |
| Final received / decoded / presented | 5,782 / 5,782 / 5,782 |
| Decoded / presented delta | +1,488 / +1,488 |
| Application-queue packet drops / high-water | 0 / 26 of 32 slots |
| JPEG / MSV1 bitrate | 0.783 / 0.814 Mbps, excluding UDP/IP/Wi-Fi overhead |
| Packet timing records | 1,500 frames / 29,446 datagrams |
| Host packet gap ms min / p50 / p95 / max | 4.297 / 4.982 / 5.194 / 6.791 |
| Logger records / lost records / I/O errors | 8,861 / 0 / none |

Source is the same repeated prerecorded Xonotic gameplay in
[xonotic-source.json](xonotic-source.json), SHA-256
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
Its 1024x600 image fits to 691x405 within the black 720x480 canvas without
distortion. This is not live capture. Quality 25 is an encoder setting, not a
perceptual score. The final operator snapshot confirms 1,488 received, decoded
and presented frames and 12 dropped frames, accounting for all 1,500 outcomes.
The last completed frame was 6616. Presented FPS uses the host run duration,
not measured panel presentation intervals or game-to-photon latency.

The automatic sender counter-delta total is 1,487, excluding its initial
baseline completion; the independent pre-run baseline yields +1,488. Do not
sum these totals. Host completion and ingress feedback do not prove display.

Rejected-feedback IDs:
`5361, 5673, 5675, 5678, 5680, 5682, 5684, 5747, 6302, 6307, 6613, 6615`.

## Confirmed Busy admission failure: frame 5361

The operator preserved rejection at offset 0, expected offset `None`, reason
`Decoder unavailable: Busy`. FPGA status at `0xE0000010` was `0x00000002`:
decoding active, READY clear. Counters read afterward were 4,538 accepted,
4,537 decoded and 4,537 presented.

| Receiver event | Receiver clock, microseconds |
| --- | ---: |
| Previous commit confirmed | 6,357,612,918 |
| Frame 5361 dequeued | 6,357,615,566 |
| Admission attempt began | 6,357,616,430 |

Admission began **3.512 ms after previous commit confirmation**. The FPGA active
frame ID was not recorded. Frame 5360 is a likely owner from sequence and the
one-frame counter difference, not an established owner. Decode completion and
READY-transition timestamps were not recorded.

Host frame 5361 contained 19,949 JPEG bytes and 20 datagrams. It completed with
host frame age 104.701 ms, estimated host send UTC
15:46:19.207650..15:46:19.303093, and maximum within-frame send gap 5.322 ms.
Frame 5360's last host send preceded frame 5361's first host send by 108.115 ms.
That does not establish receiver idle time. Host and receiver clocks have
different origins; do not subtract them. Delivery, queueing and consumer timing
have not yet been separated.

## Final classification of all twelve rejections

The continuously recorded receiver trace identifies every listed rejected ID
as offset-0 admission failure, expected offset `None`, reason
`Decoder unavailable: Busy`. There were no recorded missing-chunk gaps among
these failures and no application-queue packet drops during the run.

| Frame | Decision status | State | Milliseconds since prior commit confirmation |
| --- | --- | --- | ---: |
| 5361 | 0x02 | Decoding | 3.512 |
| 5673 | 0x10 | Pending presentation | 14.172 |
| 5675 | 0x02 | Decoding | 1.350 |
| 5678 | 0x02 | Decoding | 1.369 |
| 5680 | 0x02 | Decoding | 2.042 |
| 5682 | 0x02 | Decoding | 2.813 |
| 5684 | 0x02 | Decoding | 1.345 |
| 5747 | 0x02 | Decoding | 3.473 |
| 6302 | 0x02 | Decoding | 2.858 |
| 6307 | 0x02 | Decoding | 1.949 |
| 6613 | 0x02 | Decoding | 1.360 |
| 6615 | 0x02 | Decoding | 1.347 |

These observations explain the admission decisions for this run. They do not
establish prior-frame completion/READY times, locate the delivery/consumer
timing difference, prove the network loss-free generally, or explain historical
unrecorded failures.

Keep the physical rate at 5 fps. The next receiver candidate should evaluate
a bounded wait for READY before starting a frame, constrained by an agreed
frame-age budget. Preserve bounded receive queues, stale-frame disposal and
whole-frame recovery; measure queue high-water and packet drops while waiting.
Test decoding-active and pending-presentation states separately, including
never-ready timeout and reset/recovery. Capture active-frame identity and
commit/decode/presentation/READY timestamps.

If host-side readiness credit is needed, agree its versioned semantics with
the receiver before using it. An ingress ACK is not decoder-ready credit.
Do not infer readiness from MSF1's current advisory free-byte field or retune
Wi-Fi pacing on the assumption that these twelve failures were missing packets.
Repeat the same source/settings after the admission change before raising FPS.

## Evidence files

Under `tools/gamebub/artifacts`, prefix
`handheld-xonotic-5fps-5m-recorder-repeat-20261103`:

- `.jsonl`: complete sender frame and packet log.
- `-summary.json`: final sender counts and logger integrity.
- `-provenance.json`: start/end UTC and monotonic anchors, module/source hashes,
  baseline and exact settings.
- `-packets.csv`: every offset, length, monotonic send timestamp, within-frame
  gap and estimated host UTC.
- `-packet-report.json`: rejected IDs and matching frame/packet records.
- `-analysis.json`: standard log analyzer output.
- `-receiver-observations.jsonl`: operator-supplied frame 5361 evidence.

CSV offsets were checked for continuity and complete JPEG length for each host
send. Packet UTC estimates use one host wall/monotonic anchor; they are not
synchronized receiver timestamps or latency measurements. Serial capture files
remain on the receiver machine.
