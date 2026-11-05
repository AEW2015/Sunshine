# v29 saved-Xonotic five-minute hardware run

Run 2026-11-04 **22:23:48.678–22:28:49.562 America/Denver**
(UTC 2026-11-05 05:23:48.678–05:28:49.562), within the requested camera window.
Video duration including feedback drain: **300.394 s**. Host 192.168.0.47
targeted 192.168.0.157:5533 video and :5534 input-only AV. Receiver identity
and zero baseline were operator-reported: v29, trace epoch 2, build50,
overlap active, 32 slots; received/decoded/presented/dropped and queue drops/
high-water all zero. No receiver or installed Sunshine changes were made.

## Source and comparison boundary

Saved source: **Xonotic 0.8.2 gameplay**, `Xonotic-0-8-2-gameplay.webm`,
48,552,136 bytes; SHA-256 verified before streaming:
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
Source metadata, attribution and license: [xonotic-source.json](xonotic-source.json).
It is approximately 183 seconds of 1024×600/30 fps gameplay, looped from its
beginning to fill five minutes. Original aspect is preserved inside the
720×480 canvas; it is not stretched to 16:9. Prior documentation records a
691×405 active viewport for this source.

**The preceding v27 hardware soak captured an uncontrolled desktop. It did not
retain a saved moving clip.** The existing saved Xonotic asset was identified
in commentary before transmission and used here as a repeatable baseline.
This is not an identical-content comparison or an isolated measurement of the
v29 instrumentation's effect. No original desktop sequence can be recovered
from its packet metadata logs.

## Settings and host results

720×480, configured 20 fps, JPEG quality/minimum 25, 3 Mbps video cap,
200 ms maximum age, bilinear scaling, zero host shift. Existing sender,
encoder and pacing source hashes match the prior hardware run. An artifact-only
source adapter fed the existing tested `reference_loopback.loop_clip` iterator
into unchanged `stream_sender.run`; it did not change pacing, queue handling,
feedback, quality or protocol. Audio and gamepad injection remained off.

| Result | Count |
|---|---:|
| Target frame IDs | 2,007,000–2,012,999 |
| Submitted / encoded | 6,000 / 6,000 |
| Complete sends | 4,842 |
| Encoded replacements before transmission | 1,158 |
| Partial sends / scheduler skips | 0 / 0 |
| Matched accepted / rejected ACKs | 4,790 / 49 |
| Sends without matched feedback | 3 |
| Extra unmatched feedback events | 14 |
| Complete-send rate including drain | 16.119 fps |
| Encoded rate including drain | 19.974 fps |
| Encoded JPEG bitrate including replacements | 3.122 Mbps |
| Transmitted MSV1 datagram bitrate | 2.568 Mbps |

All 6,000 slots reconcile as 4,842 complete sends + 1,158 replacements.
All sends reconcile as 4,790 accepted ACKs + 49 rejected ACKs + 3 pending.
Pending send IDs: **2,008,251; 2,008,688; 2,009,284**.
Final feedback was **4,791 received / 51 dropped**. Those aggregate counts
numerically account for 4,842 outcomes, but do not identify which of the three
pending sends was accepted versus rejected. Do not treat pending feedback as
three additional frame losses. The receiver operator subsequently confirmed
the final results below. The three pending IDs remain individually unresolved;
collectively they account for one additional success and two drops beyond
matched ACKs.

| Receiver result | Final total |
|---|---:|
| Received / decoded / presented | 4,791 / 4,791 / 4,791 |
| Dropped frames | 51 |
| Application-queue packet drops | 0 |
| Queue high-water | 18/32 |
| Core completed / separate drop counter | 4,791 / 40 |
| Faults / overflows / underruns / transport overflows | 0 / 0 / 0 / 0 |

All 4,791 accepted frames are accounted for as decoded and presented. This is
approximately 15.9 presentations/s over five minutes; using the host's
300.394-second interval yields approximately 15.95/s. No reboot was observed.
These are operator-reported device measurements, not direct Windows reads.

Epoch 2 retained 32 detailed failure records: 23 same-frame forward-offset
gaps and nine no-active-assembly cases. No backward-offset cases were retained.
17 failures exceeded the detailed table capacity; the supplied classifications
do not explain all 51 drops. Do not assign the other failures or pending IDs a
reason from these aggregate counts.

Observed full consumer durations, including cleanup/recycling, were 2.609–9.905 ms.
Observed phase maxima were lock 2.583 ms, QSPI 3.530 ms, error abort 0.583 ms
and feedback 5.068 ms. The recorder lost **43,472 trace records**, including
22,713 phase transitions. These are telemetry losses, not measured network
packet losses. The maxima are incomplete observations, not upper bounds on
stalls. No queue-overflow trigger fired; the final 96 ring entries contain
late maintenance rather than failure-time history.

Queue saturation was not measured in this run: queue drops were zero and
high-water was 18/32. This differs from the v27 desktop soak but cannot be
attributed to v29 alone because the video content changed. Same-frame gaps do
not locate loss between host send calls, the network stack and the receiver.

All encodes used quality 25. The JPEG demand exceeded the cap before MSV1
overhead; this run did not deliver all 20 target frames per second. Bitrates
exclude UDP/IP/Wi-Fi overhead. Camera timestamps covered command start through
STOP, with zero read failures and a maximum sample gap of 117 ms. The receiver
agent's sampled review confirmed changing game scenes throughout coverage and
identified no sustained freeze. Subsecond stutter remains unquantified; this is
not a frame-by-frame optical presentation count or an optical latency measurement.

## AV and cleanup

AV source port 49770, cookie `8c3c01f774848153`. HELLO/OFFER/START reached
ACTIVE before video. The host validated 14,468 post-handshake MSI1 packets,
sequences 1–14,472 with four intervening missing sequence IDs. Invalid/stale
packets and 500 ms input timeouts were zero; all button masks were zero.
States: 9,106 at state 5 and 5,362 at state 1. Audio blocks sent: zero.
After video exited normally, one STOP was successfully sent, control sequence
2,887. Cleanup errors and forced termination were zero. The receiver operator
verified power saving restored to MIN_MODEM after STOP, with zero entry or
restoration errors.

Both loggers closed with zero dropped records and no write errors. Full local
frame/packet timing evidence:
`tools/gamebub/artifacts/v29-av-input-xonotic-20fps-3mbps-2007000-20261104/`:
`video.jsonl`, `av.jsonl`, `video-summary.json`, `video-stderr.txt`,
`manifest.json`, `completion.json`, `sender-analysis.json`, `av-analysis.json`,
`frame-outcomes.json`, exact `run.py` and source adapter `clip_sender.py`.

Next: preserve a bounded packet-identity history on Sequence/no-active-assembly
failures as well as queue overflow. Reduce repetitive phase logging or export
compact aggregates so trace loss cannot erase the failure interval; keep lost-
event counters explicit. Correlate active/incoming frame IDs and offsets with
the saved host timings before selecting a pacing, receiver or FPGA change.
Build50 remains unchanged. JPEG demand also exceeds the configured cap, so
host replacements need separate treatment from receiver failures. This run
does not qualify sustained 20 fps playback.
