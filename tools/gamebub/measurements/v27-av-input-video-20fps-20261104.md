# v27 20 fps request with input-only AV

Run: 2026-11-04 20:56:50–20:57:11 America/Denver;
UTC 2026-11-05 03:56:50.504–03:57:11.367. Video duration including feedback
drain: 20.498 seconds. Source 192.168.0.47 to 192.168.0.157, MSV1 UDP 5533
and AV v1 UDP 5534. Last operator-confirmed receiver: v27/build50, overlap,
32-slot queue. No receiver changes were requested.

Settings: desktop capture, 720×480 canvas, configured 20 fps, JPEG quality 25
(minimum 25), 2 Mbps cap, 200 ms maximum age, bilinear scaling, zero host shift.
Input-only AV reached ACTIVE before video; audio and gamepad injection stayed
off. AV STOP was successfully sent after video exited normally.

| Host result | Value |
|---|---:|
| Target frame IDs | 2,000,200–2,000,599 |
| Submitted / encoded | 400 / 400 |
| Complete sends / accepted ACKs | 277 / 277 |
| Encoded frames replaced before sending | 123 |
| Partial sends / rejected ACKs / pending ACKs | 0 / 0 / 0 |
| Scheduler skipped slots | 0 |
| Encoded fps, including drain | 19.514 |
| Complete-send fps, including drain | 13.514 |
| Encoded JPEG bitrate, including replaced frames | 2.325 Mbps |
| Transmitted MSV1 datagram bitrate | 1.674 Mbps |

The configured rate was not achieved on the network. The bounded sender
replaced queued encoded frames while paced transmission was slower than
encoding. Encoded JPEG demand already exceeds the 2 Mbps cap before packet
overhead. The transmitted bitrate includes MSV1 headers but excludes UDP/IP
and Wi-Fi overhead. No higher bitrate or lower quality was tried in this run.

Final feedback was 475 received / 2 dropped, versus the preceding confirmed
198 received / 2 dropped: 277 accepted and zero newly reported drops.
The receiver operator subsequently confirmed final received, decoded and
presented totals of 475 each (+277 each), and dropped frames 2 (+0). All 277
complete sends therefore have matching ingress, decode and presentation counts.
The last presented frame was 2,000,599. Queue packet drops remained zero;
cumulative high-water remained 23/32. Core completed count was 475 with zero
faults, overflows, underruns or transport overflows. There were no new failure
records; the retained Sequence failure still belongs to frame 2,000,084.

The receiver operator also verified power saving restored from NONE to MIN_MODEM
after AV STOP, with zero restoration errors. These are operator-reported device
measurements, not direct Windows register reads.

The 400 target slots reconcile as 277 complete sends plus 123 encoded frames
replaced before transmission. Partial sends, scheduler skips, feedback-gated
suppression, deadline failures and rejected ACKs were zero. The 123 replacements
must be counted separately from those zero outcomes.

277 receiver presentations over approximately 20 seconds is about 13.9 fps;
the host's 13.514 complete-send fps includes its 20.498-second feedback-drain
interval. Neither figure establishes 20 fps playback or optical latency.
The camera showed the image afterward, but recording began after the run, so
visible motion during the run is unverified. Desktop/game identity was not
independently verified by Windows.

AV source port 50727, cookie `a5cde75edbd3352c`: 1,004 post-handshake validated
MSI1 packets, sequences 1–1004 without intervening gaps, all masks zero.
Invalid/stale packets and input timeouts were zero; audio blocks sent were zero.
MSI1 state counts: 144 at state 1, 860 at state 5. One STOP was sent with control
sequence 202; no cleanup errors or forced video termination occurred.

Packet and frame logs are saved locally under
`tools/gamebub/artifacts/v27-av-input-video-20fps-2000200-20261104/`, including
`video.jsonl`, `av.jsonl`, `video-summary.json`, `completion.json`,
`sender-analysis.json`, `av-analysis.json`, `manifest.json`, and exact `run.py`.
Both loggers reported zero dropped records and no write errors.

This is a short input/video coexistence stress test, not an isolated power-save
comparison or a sustained 20/30 fps playback qualification. Installed Sunshine
was not restarted or replaced, and production source code was unchanged.
