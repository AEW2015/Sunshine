# V19 twenty-second moving-video control

The operator reported v19 loaded and the continuous receiver recorder active.
The operator subsequently confirmed serialized mode:
`overlap_request_active=(false, false)`.
The source and sender settings match the earlier tests: prerecorded Xonotic,
720x480 canvas, 5 fps, fixed quality 25, 2 Mbps MSV1 cap, 200 ms age deadline,
262,144-byte guard and retry disabled. Sender source code was unchanged.

| Item | Result |
| --- | --- |
| Source / destination | 192.168.0.47:55534 / 192.168.0.157:5533 |
| Host UTC window | 2026-11-03 16:10:13.873 to 16:10:34.183 |
| America/Denver window | 2026-11-03 09:10:13.873 to 09:10:34.183 MST |
| Sender duration | 20.195 seconds, including shutdown/grace |
| Scheduled / submitted / encoded | 100 / 100 / 100 |
| Requested IDs | 6617..6716 |
| Complete / partial / wholly unsent | 98 / 1 / 1 |
| Skipped slots | 0 |
| Feedback-silence suppression events | 2: one partial abort and one unsent frame |
| Matched accepted / rejected ACKs | 91 / 0 |
| Heartbeats / unmatched / abandoned pending entries | 70 / 3 / 8 |
| Pending feedback at close | 0 |
| Receiver cumulative received / dropped feedback | 98 / 1, from zero baseline |
| Independently confirmed decoded / presented | 98 / 98 |
| Application-queue packet drops / high-water | 0 / 24 of 32 slots |
| Actual JPEG / MSV1 bitrate | 0.840 / 0.857 Mbps; scope described below |
| Packet timing frames / datagrams | 99 / 2,080 |
| Logger drops / I/O errors | 0 / none |

The JPEG rate counts all encoded images, including the partial and wholly
unsent frames. MSV1 rate counts bytes actually sent and excludes UDP/IP/Wi-Fi.
Ingress feedback alone does not establish decode or presentation. The independent
receiver snapshot confirms all 98 complete ingress frames were decoded and
presented, with zero application-queue packet drops and high-water 24/32.

## Startup feedback silence

Frames 6617..6623 completed host transmission before a matched ACK was recorded.
Feedback silence expired while frame 6624 was in flight: six full 1,024-byte
payload chunks (offsets 0..5120; 6,384 MSV1 bytes) were sent from its 22,248-byte
JPEG, then the host stopped that frame. Frame 6626 was suppressed before any
packet send. Probe frame 6625 restored feedback; it was the first matched ACK,
reporting eight received and one dropped.

The cumulative receiver total accounts for seven early completions without
matched host ACKs plus 91 matched completions: 98 received. Eight pending
entries were abandoned by the feedback gate, so zero pending at close does not
mean every submitted frame was acknowledged. The run has one known partial
host frame and is not an unimpaired decoder-throughput test.

The retained receiver trace for 6624 records six packets / 6,144 JPEG bytes,
`gap_valid=false`, no text failure-reason line, and trace termination 200.098 ms
after the last packet. The run's error counter is zero. The operator reconstructed
incomplete-frame supersession by the next start-of-frame from this trace and
the receiver code path; the 500 ms receiver timeout does not fit that interval.
Supersession is consistent with the host's partial send, but it is not an explicit
recorded reason string. The reason early ACKs were not matched remains unknown.

## Subsequent v19 overlap fixture

After the operator enabled v19 overlap and confirmed continuous recording, the
host sent one known-good `frame-00000000-420-r0.jpg` as ID 6717 from
192.168.0.47:55534 to 192.168.0.157:5533. At a 0.5 Mbps cap and 3,000 ms send
deadline, all 71,675 JPEG bytes / 74,475 MSV1 bytes completed in 70 datagrams.
A matching MSF1 status-0 ACK arrived with frame ID 6717 and capture timestamp
1793722983087437 us. Its cumulative counters were 99 received / 1 dropped,
against the supplied 98 / 1 baseline. The subsequent five-minute test request
supplied 99 received/decoded/presented and one dropped as its baseline,
independently confirming the fixture's decode and presentation. Core-status
details were not supplied. No five-minute overlap stream was started by the
fixture test itself; the separately authorized comparison uses IDs 6718..8217.

Fixture artifacts: `artifacts/handheld-v19-overlap-fixture-6717-20261103-result.json`
and `artifacts/handheld-v19-overlap-fixture-6717-20261103-packets.json`.

## Saved evidence

Under `tools/gamebub/artifacts`, prefix
`handheld-v19-5fps-control-6617-20261103`:

- `.jsonl`: sender events and packet timestamps.
- `-summary.json`: final counts and logger integrity.
- `-provenance.json`: baseline, settings, source/module hashes, UTC/monotonic anchors.
- `-packets.csv`: all 2,080 sent packet offsets and timestamps, including partial 6624.
- `-packet-report.json`: packet-gap statistics and final cumulative feedback.
- `-analysis.json`: standard analyzer output.

No installed Sunshine service was replaced or restarted.
