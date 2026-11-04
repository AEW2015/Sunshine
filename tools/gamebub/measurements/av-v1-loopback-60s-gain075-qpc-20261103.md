# One-minute PC audio stream at gain0.75

Repeated the one-minute default-speaker loopback session at the operator's
requested gain0.75. The product-rounded encoder,48,293Hz stereo profile,
four-block host queue and QPC timing were retained. Video and virtual-gamepad
injection remained off; handheld volume/routing and Sunshine service were not
changed. This is a separate test; the default gain and earlier logs remain intact.
The golden-vector preflight passed immediately before starting.

| Measurement | Result |
| --- | --- |
| America/Denver process window | 2026-11-03 19:02:35.731–19:03:36.025 MST |
| UTC process window | 2026-11-04 02:02:35.731–02:03:36.025 |
| Requested / recorded active session | 60s /60.035s |
| Source / receiver | 192.168.0.47:56641 /192.168.0.157:5534 |
| Cookie | `50f7753168335cc7` |
| Encoded / sent blocks | 5,589 /5,571 |
| Queue drops / stale drops / unsent queued at close | 15 /0 /3 |
| Capture errors / worker errors | 0 /none |
| Captured48kHz stereo frames / source duration | 2,805,600 /58.45s |
| Raw source peak before gain / nonzero capture reads | 28,684 /5,845 |
| Partial resampled tail, not sent | 264 stereo frames |
| First / last sent audio sequence | 0 /5585 |
| Omitted internal audio sequence values | 15, matching queue drops |
| MSI1 packets / first and last sequence | 2,822 /0..2822 |
| MSI1 missing sequence count | 1 |
| Invalid / duplicate-stale packets / input timeouts | 0 /0 /0 |
| STOP sent / process result | Control572 /exit0 |

Exact host accounting:5,589 encoded =5,571 sent +15 queue-dropped +3 unsent at
close. Every sent block passes independent packet schema/CRC and product-rounded
decode validation. Source was the same default Realtek loopback endpoint at
48kHz, requested stereo from an eight-channel-capable device. The source content
is operator controlled and not identified by this measurement.

## Receiver status observed by Windows

| Counter | First valid MSI1 | Last valid MSI1 |
| --- | ---: | ---: |
| Accepted audio blocks, session | 0 | 5,540 |
| Rejected/unconfirmed audio blocks, session | 0 | 11 |
| Queued PCM frames | 0 | 656 |
| Played PCM frames, lifetime | 3,239,425 | 6,033,947 |
| Underruns, lifetime | 30 | 45 |

Played increased2,794,522 frames and underruns increased15. Final state7
confirms ACTIVE, negotiated AUDIO_ENABLED and valid FPGA snapshot, build
`0x4d424f50`. Admission counters account for5,551 outcomes,20 below5,571 sends;
final post-STOP receiver accounting is pending. Do not infer which20 were lost,
accepted or rejected from the last cached snapshot. Rejected/unconfirmed retains
its ambiguity after a receiver I/O/commit fault. STOP was sent; this contract has
no STOP acknowledgment.

### Post-STOP receiver confirmation

The operator supplied final counters:5,542 accepted blocks,11
rejected/unconfirmed, zero queued PCM frames and6,036,993 lifetime played frames.
The final played increase is2,797,568 frames; underruns remain45 lifetime,
an increase of15. These add two accepted blocks and3,046 played frames beyond
the last MSI1 snapshot. STOP completed, power saving was restored and reported
core/socket/malformed errors remained zero.

Final admission accounting leaves **18 sent blocks unexplained**:
5,571 sent minus5,542 accepted minus11 rejected/unconfirmed. The receiver reports
33 sequence gaps, while the host recorded15 internal omissions matching its
queue drops. The numerical difference is18, but it does not assign particular
missing IDs or prove Wi-Fi loss. Receiver per-sequence records are still needed
to attribute the18 unaccounted sends and the15 underruns. These counters have
different scopes and must not be added as independent losses.

High-resolution host send-gap milliseconds: min0.145, median10.796,
p95 20.120, max31.520. Preparation-to-send age: min0.081, median16.959,
p95 31.044, max46.877ms. These are host-side observations, not receiver arrival
or sound latency. The15 new underruns mean no clean-continuity pass is claimed.

The operator was asked whether0.75 was sufficiently loud and whether distortion,
clicks or gaps were heard, plus post-STOP counters. The operator confirmed that
gain0.75 allowed the webcam microphone to capture PC audio without microphone
clipping. Comfortable listening loudness, speaker distortion and individual
clicks remain unconfirmed; the15 underruns mean playback was not gap-free.
The Windows agent cannot hear the handheld. Different source content
and run conditions prevent attributing counter differences to gain alone.

Evidence under `tools/gamebub/artifacts/av-v1-loopback-60s-gain075-qpc-20261103/`:
reference sources and manifest, `loopback-gain075-60s.jsonl`, raw `packets.jsonl`,
`stdout.jsonl`, `stderr.txt`, exact-worker `run-metadata.json`, `analysis.json`
and `sent-blocks.ima`. Preflight:
`artifacts/av-v1-before-loopback-gain075-golden-20261103.json`.
The attributed final receiver and acoustic report is in `receiver-confirmation.json`.
The socket closed at completion and no further stream was started.
