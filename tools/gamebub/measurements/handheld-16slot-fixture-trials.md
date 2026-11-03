# Sixteen-slot receiver fixture trials

These are physical receiver ingress tests with the same 71,675-byte,
720x480 baseline 4:2:0 fixture used in
[handheld fixture bring-up](handheld-fixture-bringup.md). Each complete frame
is 74,475 MSV1 bytes, excluding UDP/IP/Wi-Fi overhead. The sender used a
fixed source port, new frame IDs, 3-second per-frame deadline, and 3-second
feedback timeout. Each run launched a separate one-frame sender for each ID;
this is not a continuous stream, game-footage test, 30 fps test, or latency
measurement. Sender timestamps describe completed socket sends, not arrival.

| Receiver configuration and rate | Frame IDs | Sent complete | Receiver feedback: received / dropped | Evidence |
| --- | --- | ---: | ---: | --- |
| 16 slots, 0.5 / 0.7 / 1.0 Mbps | 25–27 | 3 | 3 / 0 | User reported all three passed. |
| 16 slots, 1.0 Mbps | 28–47 | 20 | 19 / 1 | Feedback identifies frame 38 as dropped. |
| 16 slots, consumer priority 6, 1.0 Mbps | 48–67 | 20 | 20 / 0 | Producer priority 5; feedback status 0 for each. |
| 16 slots, consumer priority 5, 1.0 Mbps | 68–87 | 20 | 20 / 0 | Feedback counters increased from 20 / 0 to 40 / 0. |
| Receiver ready after QSPI benchmark, 0.7 Mbps | 88 | 1 | 1 / 0 | Operator confirmed decode and display and reported stage timing below. |

The later 20-frame runs each contained 1,400 sent datagrams. For IDs 28–47,
median host inter-datagram gap was 8.971 ms, p95 9.338 ms, and max 10.999 ms;
for IDs 48–67, 8.971 / 9.354 / 9.944 ms; and for IDs 68–87,
8.968 / 9.255 / 9.943 ms. Each frame's first-to-last datagram span averaged
about 0.620 seconds. First-to-last send spans for the three whole runs were
22.457, 21.968, and 22.443 seconds, respectively, including gaps between
individual sender processes. Gap p95 is the sorted zero-based element at
`floor(0.95 * (N - 1))`. Packet records are local ignored artifacts; they do not
contain frame pixels.

For frame 38 the receiver reported expected offset 61,440 and observed 63,488.
The host recorded offsets 61,440 and 62,464 as sent, with 8.956 and 8.941 ms
between each and its preceding datagram; this does not establish their delivery
to the ESP32 or the stage responsible for the reported gap. On 20 samples per
condition, the 20/20 priority-6 and 20/20 priority-5 feedback results do not
establish that either priority is more reliable. The feedback counts are ingress
observations; apart from the user's statements that frames 25–27 passed and
frame 88 was displayed, these records do not independently establish decode or display. Receiver logs and
independent display counters remain necessary.

The receiver operator subsequently reported that frame 88 was received,
decoded, and displayed without a drop. For its 71,675-byte JPEG, the FPGA
reported 47.50 ms decode/drain and 8.56 ms waiting for presentation; 70 QSPI
payload writes took 9.03 ms total, excluding register reads and network wait.
At 30 fps the frame interval is 33.33 ms; this single fixture's reported
stage time exceeds that interval, but further sustained and overlapping-stage
measurements are needed to establish the throughput limit for moving content.

In a separate 40 MHz QSPI sink test with Wi-Fi disconnected, the receiver
operator reported 100 repetitions per transfer size, matching FPGA byte counts
and CRCs, and no transport overflow. Reported median / min–max rates were
3.225 / 3.207–3.229 MB/s for 256-byte writes, 8.687 / 8.653–8.695 MB/s for
1,024-byte writes, and 15.061 / 14.983–15.073 MB/s for 4,096-byte writes.
The operator reported 300 MiB total; the size of each repetition was not
specified here. These isolated sink measurements do not include concurrent Wi-Fi,
full application overhead or video decoding; they are not end-to-end throughput.
