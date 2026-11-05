# v27 AV input-only and MSV1 video coexistence

Run: 2026-11-04 20:39:36–20:39:57 America/Denver
(2026-11-05 03:39:36.484–03:39:57.236 UTC).

This tests input coexistence and the existing AV power-save scope. It is not
an isolated power-save comparison. Receiver installation is operator-reported
v27/build50, overlap active, 32 queue slots; no firmware changes were made.

Host 192.168.0.47 established input-only AV v1 to 192.168.0.157:5534 from
UDP source port 63963, cookie `0e322e55f2a36242`. HELLO/OFFER/START reached
ACTIVE before desktop video started. Audio and virtual-gamepad injection were
disabled. The independently sequenced MSI1 stream remained active until video
exited normally. Host then successfully sent one 48-byte STOP, sequence 200.
The receiver operator subsequently confirmed power-save transitions from
MIN_MODEM (1) to NONE (0) during AV and back to MIN_MODEM (1) after STOP,
with zero entry or restoration errors.

Video used the unchanged standalone sender: 720×480 canvas, 5 fps, JPEG quality
25 (minimum 25), 2 Mbps cap, 200 ms maximum age, bilinear desktop scaling,
zero host shift, UDP destination 5533 and ephemeral source port. Desktop content
was not independently identified or optically monitored by Windows.

| Host result | Count |
|---|---:|
| Frame range | 2,000,100–2,000,199 |
| Encoded / complete sends | 100 / 100 |
| Partial / skipped / suppressed / deadline failures | 0 / 0 / 0 / 0 |
| Matched accepted / rejected ACKs | 100 / 0 |
| Pending ACKs | 0 |
| Post-handshake validated MSI1 | 997 |
| MSI1 sequence range | 1–997, no intervening gaps |
| Invalid / stale / timed-out input | 0 / 0 / 0 |
| Audio blocks sent | 0 |

All logged input masks were zero: this proves input-session coexistence, not
physical button activity or gamepad injection. The handshake's initial MSI1
is excluded from the 997 post-handshake input count. MSI1 states were 1 for
60 packets and 5 for 937; snapshot validity is not continuously asserted.

Final video feedback: **198 received / 2 dropped**, versus the last independently
confirmed baseline of 98 received/decoded/presented and 2 dropped. The receiver
operator subsequently confirmed the following final counters:

| Receiver result | Final total | Run increase |
|---|---:|---:|
| Received | 198 | 100 |
| Decoded | 198 | 100 |
| Presented | 198 | 100 |
| Dropped frames | 2 | 0 |

Packet queue drops were zero, cumulative high-water remained 23/32, and the
queue was empty afterward. FPGA faults, overflows, underruns and transport
overflows were all zero, with 198 completed frames. The retained Sequence
error belongs to the preceding run. These are operator-reported device
measurements; Windows did not independently read the receiver registers.

This passes the 100-frame input/video coexistence check at configured 5 fps.
All 100 accepted frames are accounted for as decoded and presented. It does
not establish optical latency, uninterrupted motion, sustained 30 fps, or
power saving as the cause of the improvement over the previous video-only run.

Video duration including feedback drain was 20.475 s. JPEG payload averaged
0.5603 Mbps; MSV1 datagrams averaged 0.5827 Mbps, excluding UDP/IP/Wi-Fi overhead.
Quality stayed 25. Host sent rate over that duration was 4.884 fps; configured
capture cadence was 5 fps. These are not optical presentation measurements.

Both logs closed with zero dropped records or write errors. Video child exited
0 without forced termination; AV cleanup reported no errors. Installed Sunshine
was not restarted or replaced.

Local raw evidence: `tools/gamebub/artifacts/v27-av-input-video-5fps-2000100-20261104/`:
`manifest.json`, `completion.json`, `av.jsonl`, `av-analysis.json`,
`video.jsonl` (packet timestamps), `video-summary.json`, `video-stderr.txt`,
`sender-analysis.json`, and the exact artifact-only orchestration `run.py`.
No production source code or wire format changed for this experiment.
