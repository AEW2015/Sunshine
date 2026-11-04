# V19 overlap: matched five-minute moving-video test

The operator confirmed v19 overlap active and continuous receiver recording.
The test kept the existing receiver application/session and sender settings:
192.168.0.47:55534 to 192.168.0.157:5533, repeated prerecorded Xonotic,
720x480 canvas, 5 fps, quality fixed at 25, 2 Mbps MSV1 cap, 200 ms age
deadline, 262,144-byte JPEG guard and retry disabled. Sender source code was
unchanged. The installed Sunshine service was not replaced or restarted.

| Measurement | Result |
| --- | --- |
| America/Denver host window | 2026-11-03 09:27:52.163 to 09:32:52.488 MST |
| UTC host window | 2026-11-03 16:27:52.163 to 16:32:52.488 |
| Sender duration including shutdown/grace | 300.210 seconds |
| Requested / actual frame range | 6718..8217 / 6718..8217 |
| Scheduled / submitted / encoded / completely sent | 1,500 / 1,500 / 1,500 / 1,500 |
| Skipped / suppressed / incomplete sends | 0 / 0 / 0 |
| Matched accepted / rejected ACKs | 1,500 / 0 |
| Heartbeats / pending ACKs / feedback timeouts | 1,153 / 0 / 0 |
| Starting received / decoded / presented / dropped | 99 / 99 / 99 / 1 |
| Final received / dropped feedback | 1,599 / 1 |
| Known-baseline received / dropped delta | +1,500 / 0 |
| Final independently reported received / decoded / presented | 1,599 / 1,599 / 1,599 |
| Independent received / decoded / presented run delta | +1,500 / +1,500 / +1,500 |
| Host sent / receiver-counter-confirmed presented FPS | 4.997 / 4.997 |
| Application-queue packet drops / high-water / final occupancy | 0 / 25 of 32 / 0 |
| Overlap / final core status | Active / 0x01 idle-ready |
| Faults / FIFO overflow / transport overflow / scanout underruns | 0 / 0 / 0 / 0 |
| JPEG / MSV1 bitrate | 0.783 / 0.814 Mbps; excludes UDP/IP/Wi-Fi |
| JPEG / MSV1 bytes | 29,375,608 / 30,553,448 |
| Host post-retrieval-to-send age ms p50 / p95 / maximum | 100.363 / 130.865 / 173.289 |
| Host packet gap ms minimum / p50 / p95 / maximum | 4.295 / 4.983 / 5.195 / 5.810 |
| Packet timing frames / datagrams | 1,500 / 29,446 |
| Logger records / lost records / I/O errors | 8,656 / 0 / none |

The first matched ACK was for frame 6718. The startup feedback-silence issue
from the short serialized control did not recur. The automatic receiver-delta
total is 1,499 because its first ACK establishes a baseline after the first
completion; the independently supplied 99-frame baseline gives +1,500.

Source hash/provenance is in [xonotic-source.json](xonotic-source.json). The
1024x600 recording is fitted to 691x405 within the black 720x480 canvas without
distortion. It is repeated prerecorded footage, not live desktop capture or
five minutes of unique content. Quality 25 is an encoder setting, not a
perceptual score. Byte totals match the earlier serialized five-minute runs.

The operator's independent final snapshot confirms all 1,500 requested frames
were received, decoded and presented with zero new frame or application-queue
packet drops. The single cumulative drop remains earlier frame 6624. Overlap
was active and the core ended idle/ready, with zero reported faults, FIFO or
transport overflows, or scanout underruns. A game image was visible in a camera
check near the end; continuous motion throughout the run was not optically
monitored. This passes the five-minute 5 fps milestone using receiver counters.

Host send age is not glass-to-glass latency, and presentation intervals were
not measured independently. The comparison with v9 serialized changes both
FPGA revision and mode and cannot isolate their effects. Keep the current
receiver application and 32-slot queue for the next short, separately requested
10 fps exploration. Preserve the same quality, bitrate cap and deadline for
the initial comparison; count host replacements/skips as well as receiver drops.
Admission-wait firmware remains a separate fallback if Busy returns.

## Saved evidence

Under `tools/gamebub/artifacts`, prefix
`handheld-v19-overlap-5fps-5m-6718-20261103`:

- `.jsonl`: complete sender and packet timing log.
- `-summary.json`: final counts and logger integrity metadata.
- `-provenance.json`: baseline, settings, source/module hashes and UTC/monotonic anchors.
- `-packets.csv`: all 29,446 offsets, payload lengths and monotonic send timestamps.
- `-packet-report.json`: contiguous frame range, packet-gap statistics and final feedback.
- `-analysis.json`: standard log analyzer output.
- `-receiver-final.json`: independent final counters, queue/core state and visual limits.

All requested IDs, complete send counts, final received/dropped feedback and
packet offset continuity were checked. CSV UTC estimates use a host wall-clock
anchor and do not synchronize clocks with the receiver. No subsequent stream
was started by this test.
