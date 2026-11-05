# v27 20 fps request at 3 Mbps with input-only AV

Run UTC 2026-11-05 04:00:35.256–04:00:55.987
(2026-11-04 21:00:35–21:00:55 America/Denver). Video duration including
feedback drain: 20.454 seconds. Source 192.168.0.47; receiver
192.168.0.157:5533 video and :5534 AV. Last operator-confirmed installation:
v27/build50, overlap active, 32-slot queue. No hardware updates requested.

Settings matched the preceding 20 fps run except the bitrate cap increased
from 2 to 3 Mbps: desktop capture, 720×480 canvas, JPEG quality/minimum 25,
20 fps target, 200 ms maximum age, bilinear scaling, zero host shift.
Desktop content was not controlled or independently identified, so this is
not a frame-identical source comparison.

| Host result | Value |
|---|---:|
| Target IDs | 2,000,600–2,000,999 |
| Submitted / encoded | 400 / 400 |
| Complete sends / accepted ACKs | 398 / 398 |
| Encoded frames replaced before transmission | 2 |
| Partial sends / scheduler skips / rejected ACKs | 0 / 0 / 0 |
| Pending ACKs | 0 |
| Complete-send rate including drain | 19.459 fps |
| Encoded rate including drain | 19.557 fps |
| JPEG encoded bitrate, including replacements | 2.263 Mbps |
| MSV1 transmitted datagram bitrate | 2.342 Mbps |

Final feedback: 873 received / 2 dropped, compared with the previously confirmed
475 received / 2 dropped: 398 new accepted frames, no new reported drops.
The receiver operator subsequently confirmed final received, decoded and
presented totals of 873 each (+398 each), and dropped frames 2 (+0). All 398
complete sends therefore have matching ingress, decode and presentation counts.
Queue packet drops remained zero; cumulative high-water remained 23/32. Core
faults, overflows, underruns and transport overflows were all zero. No new
frame-drop records appeared; the last retained failure remained frame 2,000,084.

After STOP, the operator verified MIN_MODEM power saving restored, with zero
restoration errors. These are operator-reported device measurements, not direct
Windows register reads. The held image was visible afterward, but camera recording
began after STOP, so motion during the run and optical latency remain unverified.

Input-only AV reached ACTIVE before video, source port 49666, cookie
`a24785d6d3a6a4fb`. Audio and gamepad injection were off. There were 993 validated
post-handshake MSI1 packets, sequences 1–993 without intervening gaps; all masks
zero. Invalid/stale packets and input timeouts were zero. MSI1 states: 260 at
state 1 and 733 at state 5. After normal video exit, one STOP was successfully
sent with sequence 200. Cleanup errors and forced termination were zero.

The 400 slots reconcile as 398 complete sends plus two encoded replacements.
The receiver counted 398 presentations, approximately 19.9 presentations/s over
the nominal 20-second video interval. The host's 19.459 complete-send fps uses
the longer 20.454-second duration including feedback drain; these denominators
must not be treated as identical. This approaches the requested 20 fps over a
short interval, but does not establish sustained playback or 30 fps capability. Compared
with the prior run's 277 complete sends and 123 replacements at 2 Mbps, host
replacement was substantially reduced. No causal claim about power saving is
made; input-only AV was present in both runs.

Raw local evidence, including frame and packet timestamps:
`tools/gamebub/artifacts/v27-av-input-video-20fps-3mbps-2000600-20261104/`:
`video.jsonl`, `av.jsonl`, `video-summary.json`, `completion.json`,
`sender-analysis.json`, `av-analysis.json`, `manifest.json`, and exact `run.py`.
Both loggers reported zero dropped records or write errors. Production source,
receiver configuration and installed Sunshine were not modified by this run.
