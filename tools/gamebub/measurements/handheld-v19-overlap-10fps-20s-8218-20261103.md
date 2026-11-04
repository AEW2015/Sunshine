# V19 overlap: twenty-second 10 fps exploration

The operator confirmed receiver tracing active. The sender retained the prior
session settings: 192.168.0.47:55534 to 192.168.0.157:5533, prerecorded Xonotic,
720x480 canvas, fixed quality 25, 2 Mbps MSV1 cap, 200 ms frame-age deadline,
262,144-byte JPEG guard and retry disabled. Only target rate and run length
changed. Sender source code was unchanged; the installed service was untouched.
The last confirmed baseline was 1,599 received/decoded/presented and one dropped.

| Measurement | Result |
| --- | --- |
| America/Denver host window | 2026-11-03 10:37:35.509 to 10:37:55.915 MST |
| UTC host window | 2026-11-03 17:37:35.509 to 17:37:55.915 |
| Sender duration including shutdown/grace | 20.290 seconds |
| Scheduled / submitted / encoded | 200 / 200 / 200 |
| Frame-ID range | 8218..8417 |
| Complete / partial / zero-byte sends | 161 / 28 / 11 |
| Skipped slots / feedback-silence suppression | 0 / 0 |
| Matched accepted / rejected ACKs | 161 / 0 |
| Heartbeats / unmatched feedback / pending ACKs | 79 / 1 / 0 |
| Final received / dropped feedback | 1,760 / 29 |
| Known-baseline received / dropped delta | +161 / +28 |
| Independently confirmed final decoded / presented | 1,760 / 1,760 (+161 each) |
| Queue packet drops / final occupancy | 0 / 0 |
| Session queue high-water | 25/32, unchanged; no run-specific peak recorded |
| Receiver errors / reported Busy / core faults / overflow / underruns | 0 / none / 0 / 0 / 0 |
| Encoded / completely sent FPS | 9.857 / 7.935 |
| Encoded JPEG / actually sent MSV1 bitrate | 1.671 / 1.597 Mbps |
| Packet-timing frames / datagrams | 189 / 3,881 |
| Host packet gap ms minimum / p50 / p95 / maximum | 4.319 / 4.984 / 5.203 / 7.582 |
| Logger lost records / I/O errors | 0 / none |

All 200 frame IDs have send-disposition records: 161 complete, 28 partial and
11 with zero bytes. There were no skipped capture slots, raw/encoded replacements
or feedback timeout events. The 39 unsuccessful sends came from the paced
send deadline checks, not reported socket errors. Eleven could not fit the
remaining age budget at preflight; 28 began but stopped at a subsequent
packet-pacing deadline check before completing the frame.
First zero-byte rejection: 8236. First partial frame: 8240.

Partial IDs:
`8240, 8244, 8254, 8259, 8264, 8265, 8270, 8271, 8272, 8273, 8274, 8275, 8276, 8277, 8278, 8279, 8280, 8281, 8282, 8283, 8284, 8285, 8286, 8288, 8327, 8338, 8339, 8340`.

Zero-byte IDs:
`8236, 8241, 8245, 8250, 8255, 8260, 8266, 8289, 8322, 8328, 8332`.

The receiver's +28 dropped counter matches the number of partial sends, but
individual receiver reasons were not retained. The operator independently
confirmed all 161 accepted frames were decoded and presented. There were zero
queue packet drops, receiver errors, core faults, overflows or underruns, and
overlap remained active. No Busy diagnostics were recorded. Incomplete-frame
supersession versus receiver timeout cannot be distinguished from these counters;
do not classify the drops as Busy or network loss. The automatic
sender completed-frame delta is 160 because its first ACK establishes a
baseline after the first completion; the known pre-run baseline yields +161.

JPEG bitrate includes all 200 encoded frames, including unsent bytes; MSV1
bitrate counts bytes actually sent, including partial frames, and excludes
UDP/IP/Wi-Fi overhead. These values are not a paired encoder/link throughput
comparison. Recorded packet submission gaps do not establish receiver arrival
timing. Host send age is not game-to-photon latency. Quality 25 is an encoder
setting, not a perceptual score. Source provenance remains
[xonotic-source.json](xonotic-source.json); this is prerecorded, not live capture.

The unchanged 200 ms deadline/2 Mbps configuration did not sustain complete
10 fps delivery. Inspect host queue age, pacing and actual frame-size bursts
alongside receiver reasons before selecting a further test. Do not change
multiple settings or extend the deadline silently.

The subsequent [all-frame timing comparison](10fps-partial-frame-timing-comparison-20261103.md)
includes all 28 partials, common-source 5/10 fps samples, the retained receiver
timing for 8340, and separately measured offline source and sleep profiles.

## Frame 8240 host termination and next start-of-frame

| Detail | Recorded value |
| --- | ---: |
| Complete encoded JPEG size | 25,576 bytes |
| Payload bytes / MSV1 bytes sent | 23,552 / 24,472 |
| Complete datagrams sent | 23 |
| Last sent chunk offset / payload length | 22,528 / 1,024 |
| Last sent byte index, inclusive | 23,551 |
| First unsent offset / remaining JPEG bytes | 23,552 / 2,024 |
| First / last packet host monotonic seconds | 1222540.2541927 / 1222540.3629829 |
| Encoded queue age when send began | 68.5662 ms |
| Frame age in the final send record | 192.0941 ms |
| Configured age deadline | 200 ms |
| Frame 8241 bytes sent | 0, refused by preflight |
| Next frame on the wire | 8242 |
| Frame 8242 first-packet host monotonic seconds | 1222540.3844253 |
| Last 8240 packet to first 8242 packet gap | 21.4424 ms |

The host returned incomplete at a per-packet pacing deadline guard: the next
paced packet could not be admitted within the original age budget. It did not
receive a recorded Busy rejection or report a socket error. The guard can stop
before age reaches 200 ms because it reserves the next packet's scheduled wait
and serialization duration. The log does not record which of the pre-wait or
post-wait guards fired or its exact check timestamp; that distinction cannot be
recovered retrospectively.

The next numerical ID, 8241, emitted no packets. The next actual SOF was 8242,
21.4424 ms after the last host packet for 8240. These are host submission times,
not receiver arrival times; they are consistent with incomplete-frame
supersession but do not establish the receiver's unrecorded drop reason. Keep
admission-wait firmware separate: the demonstrated issue is incomplete host
delivery under the unchanged pacing/deadline settings, with no recorded Busy.

## Saved evidence

Under `tools/gamebub/artifacts`, prefix
`handheld-v19-overlap-10fps-20s-8218-20261103`:

- `.jsonl`: complete frame/send/packet logs.
- `-summary.json`: final counts and logger integrity.
- `-provenance.json`: clock anchors, baseline, settings and source/module hashes.
- `-packets.csv`: all 3,881 sent packet offsets and timestamps, including partial frames.
- `-packet-report.json`: per-frame timing and final cumulative feedback.
- `-send-disposition.json`: complete, partial and zero-byte frame identities/details.
- `-analysis.json`: standard analyzer output.
- `-frame-8240-detail.json`: termination analysis, last offset and next-SOF timing.
- `-receiver-final.json`: independent stage counters, queue/core state and limitations.

CSV UTC estimates use a host clock anchor, not receiver synchronization.
