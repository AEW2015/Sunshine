# Handheld MSV1 fixture bring-up

On November 2, 2026, the Windows standalone fixture sender sent the deterministic
720x480 baseline 4:2:0 JPEG `frame-00000000-420-r0.jpg` (71,675 JPEG bytes;
SHA-256 `b327b1c2e2af7988e66f2ae570534a91c4526bbb53739ee5809f51e123228fb6`)
to the physical handheld's Test MJPEG receiver. Each complete attempted frame
contained 74,475 MSV1 datagram bytes, including chunk headers but excluding
UDP/IP/Wi-Fi overhead. The receiver was restarted between the first 0.3 Mbps
success and the 1 Mbps test. Later tests used one fixed sender source port and
incrementing frame IDs within the same receiver session.

| Configured MSV1 rate | Frame ID | Matching feedback status | Cumulative received / dropped |
| ---: | ---: | --- | ---: |
| 20 Mbps | 1 | dropped | 0 / 1 |
| 0.3 Mbps | 1 | status 0 | 1 / 1 |
| 1 Mbps | 1 | dropped | 1 / 2 |
| 0.3 Mbps | 2 | status 0 | 2 / 2 |
| 0.5 Mbps | 3 | status 0 | 3 / 2 |
| 0.7 Mbps | 4 | dropped | 3 / 3 |
| 0.5 Mbps | 5 | status 0 | 4 / 3 |
| 0.5 Mbps | 6 | status 0 | 5 / 3 |
| 0.5 Mbps | 7 | status 0 | 6 / 3 |
| 0.5 Mbps | 8 | status 0 | 7 / 3 |
| 0.7 Mbps | 9 | dropped | 7 / 4 |

The operator independently reported cumulative handheld counters of 1
received/1 decoded/1 displayed/1 dropped after the first 0.3 Mbps success,
2/2/2/2 after the second, and 3/3/3/3 after the 0.5 and 0.7 Mbps trials. The
camera showed the expected color bars and patterned lower half. Thus the first
three successful frames, including the first 0.5 Mbps frame, were physically
decoded and displayed. After IDs 5–7 the operator reported cumulative counters
of **6 received, 6 decoded, 6 displayed, and 3 dropped**, confirming those three
frames too. After IDs 8 and 9, the operator reported cumulative counters of
**7 received, 7 decoded, 7 displayed, and 4 dropped**; this confirms ID 8 was
displayed and ID 9 dropped. MSF1 status 0 can also be a heartbeat; matching
feedback alone is not proof of display.

The host recorded actual send times for all 70 datagrams of IDs 8 and 9.
At 0.5 Mbps, inter-datagram gaps were minimum 17.004 ms, median 17.266 ms,
p95 17.987 ms and maximum 18.146 ms. At 0.7 Mbps they were minimum 12.080 ms,
median 12.885 ms, p95 13.161 ms and maximum 13.236 ms. These are sender-side
`perf_counter` timestamps taken after socket sends; they cannot show Wi-Fi
delivery timing, receiver queueing or the location of a missing chunk. The
individual logs remain in ignored local artifacts and contain no frame pixels.

After the 0.7 Mbps trial the operator reported status text
`Invalid/lost frame: Sequence` and 79 errors. Error count is separate from
the dropped-frame count; one failed frame can produce subsequent errors. This
does not identify whether loss/reordering occurred on Wi-Fi, in the UDP receive
queue, or elsewhere in the ESP32/QSPI path. These are isolated samples, not a
measured stable maximum rate, 30 fps stream, moving gameplay, or latency test.
The receiver serial log was not captured for the ID 9 failure, so the first
expected and observed chunk offsets for that specific frame are unknown.

The receiver agent later reported two diagnostic windows with no new dropped
frame and final cumulative counters of 16 received, 16 decoded, 16 displayed,
and 4 dropped. The FPGA fault, overflow, underrun and transport-overflow
counters were zero in those windows. A zero credits snapshot does not establish
the minimum credits available during a frame. In a **separate earlier 1 Mbps
test**, the agent reported the first gap as expected offset 7168, observed 8192;
that event cannot be attributed to the ID 9 failure above. The receiver logs
remain on the other machine and were not independently inspected here.

The receiver team should capture the first sequence error for a frame, expected
and observed frame IDs/offsets, socket-drop or queue counters, per-chunk QSPI
time/credits, and decode/display timing. Maintain the current conservative
rate until both sides agree on how to probe and report backpressure.
