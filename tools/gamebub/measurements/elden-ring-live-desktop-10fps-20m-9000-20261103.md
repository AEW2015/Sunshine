# Twenty-minute desktop stream including user-driven Elden Ring

The operator requested screen capture and drove Elden Ring, then selected a
10 fps target. This superseded a briefly started recorded-Xonotic soak, whose
partial log was preserved separately. This run captures the live primary
Windows desktop through the existing FFmpeg Desktop Duplication backend, not a
game-specific window. App switches are included. No other live game was tested.

## Host and feedback results

| Measurement | Result |
| --- | --- |
| America/Denver host window | 2026-11-03 11:13:43.385 to 11:33:43.918 MST |
| UTC host window | 2026-11-03 18:13:43.385 to 18:33:43.918 |
| Sender duration including startup/grace | 1,200.527 seconds |
| Source / receiver | 192.168.0.47:55534 / 192.168.0.157:5533 |
| Canvas / target / fixed JPEG quality | 720x480 / 10 fps / 25 |
| MSV1 cap / age deadline | 2 Mbps / 200 ms, unchanged |
| JPEG byte guard / retry | 262,144 bytes / disabled |
| Nominal frame IDs / scheduled slots | 9000..20999 / 12,000 |
| Submitted / encoded | 11,965 / 11,965 |
| Complete / partial / zero-byte sends | 11,943 / 20 / 2 |
| Skipped slots / feedback suppression | 35 / 0 |
| Matched accepted / rejected MSF1 responses | 11,893 / 50 |
| Heartbeats / unmatched responses / pending | 5,355 / 32 / 0 |
| Capture errors / successful reopen sequences | 3 / 2 (two errors then recovery, one later error then recovery) |
| Complete host send rate | 9.948 fps |
| Independently counted presentation rate over host duration | 9.906 fps |
| Receiver baseline received / decoded / presented / dropped | 2,019 / 2,019 / 2,019 / 30 |
| Receiver final received / decoded / presented / dropped | 13,912 / 13,912 / 13,912 / 100 |
| Independent received / decoded / presented run delta | +11,893 / +11,893 / +11,893 |
| Receiver run drops / recorded distinct Busy rejections | 70 / 50 |
| Queue packet drops / session high-water / final occupancy | 0 / 29 of 32 / 0 |
| Core faults / FIFO overflow / transport overflow / underruns | 0 / 0 / 0 / 0 |
| Encoded JPEG / sent MSV1 bitrate | 1.155 / 1.201 Mbps, excluding UDP/IP/Wi-Fi |
| Encoded JPEG / sent MSV1 bytes | 173,286,501 / 180,230,368 |
| JPEG size bytes p50 / p95 / maximum | 14,618 / 15,890 / 24,635 |
| Successful encode/validation ms p50 / p95 / maximum | 2.732 / 3.862 / 15.518 |
| Complete host post-retrieval-to-send age ms p50 / p95 / maximum | 83.920 / 92.294 / 198.339 |
| Host packet gap ms minimum / p50 / p95 / maximum | 4.305 / 4.978 / 5.170 / 11.337 |
| Packet timing frames / datagrams | 11,963 / 176,129 |
| Logger records / lost records / I/O errors | 65,151 / 0 / none |

All nominal slots are accounted for: 35 skipped, 11,943 complete, 20 partial
and two zero-byte refusals total 12,000. No raw/encoded replacements were reported.
The 20 partials and two zero-byte refusals occur near the end; send-deadline
checks ended them without reported socket errors or feedback-silence shutdown.

Partial IDs:
`20846, 20848, 20851, 20942, 20943, 20944, 20945, 20946, 20947, 20948, 20949, 20950, 20951, 20956, 20957, 20958, 20959, 20960, 20961, 20962`.
Zero-byte IDs: `20952, 20963`.

Final cumulative receiver feedback was **13,912 received / 100 dropped**.
The operator subsequently confirmed a pre-run baseline of 2,019
received/decoded/presented and 30 dropped, and final totals of 13,912 for each
successful stage and 100 dropped. All 11,893 received frames were decoded and
presented. The first matched response, ID 9000, reported 2,020 / 30; the sender's
automatic delta therefore excludes one initial completion and reports +11,892.
Use the independent baseline for the full-run +11,893 increase, not both totals.

The 50 rejected responses correspond to complete host sends. The receiver
capture contains 50 distinct Busy rejections, agreeing with that count.
Specifically, IDs 9724 and 20793 have explicit `FPGA overlap start: Policy(Busy)`
at offset 0, expected `None`, decision status `0x02` (decode/drain). Other Busy
IDs were not individually supplied in the chat, so the two examples are the
explicit cross-checked identities here.

The remaining 20 dropped-frame increase numerically matches the 20 host partial
sends. Their individual receiver reasons are not established; ID 20846's reason,
bytes and timing were not retained. Do not label these as Busy, timeout,
supersession or network loss without corresponding receiver evidence.

No queue packet drops, core faults, FIFO/transport overflows or underruns were
reported. Queue occupancy ended at zero, but session high-water was 29/32.
This supports treating Busy admission and host deadline partials as separate
work, with little observed queue headroom available for an admission wait.
Cumulative presentation counts do not provide per-frame optical timing.

Quality remained 25 for every encode. JPEG bitrate counts all encoded images,
including unsent portions; MSV1 bitrate counts actual datagram submission.
Neither is network goodput or display throughput. Desktop Duplication can
repeat unchanged images, so 9.948 complete sends/s is not proof of distinct
gameplay or physical presentations at that rate. Host age excludes acquisition
delay and is not game-to-photon latency. Audio and controller streaming were
not exercised; the operator drove the game on Windows.

## Games and visible updates

Elden Ring was the live game exercised. Earlier diagnostics used prerecorded
Xonotic; that clip is not the source of this twenty-minute desktop run.

During this run the operator reported that the handheld was "updating just
fine" and observed some drops with lots of movement. That is qualitative
observation, not continuous optical monitoring or synchronized per-frame timing.

A separate read-only sampler collected foreground process identity every 15
seconds, beginning partway through the run. Of 73 samples, 33 identified
`eldenring.exe`, 39 `Code.exe`, and one `chrome.exe`. These snapshots do not
measure exact gameplay durations or identify every captured frame. The run
therefore includes desktop/app-switch intervals and is not twenty uninterrupted
minutes of Elden Ring gameplay.

The same sampler recorded private bytes from 77,230,080 to 83,906,560; first/last
were 79,912,960 / 79,753,216 over 1,080.061 sampled seconds. Sender CPU time
increased by 282.484 seconds in that interval, about 26.2% of one logical core.
This covers the sender process only, excludes game/GPU resource usage and
startup, and does not prove absence of longer-term leaks.

## Right-shift observation

The operator reported the handheld output shifted right. A separate snapshot
using the same capture backend found a 1280x720 source fitted to 720x405 at
canvas x=0, y=37, with 0/0 horizontal and 37/38 vertical black margins. The
nonblack bounding box was `(0,37)-(720,442)`; host canvas geometry is centered.

The receiver agent independently reported that RTL maps JPEG columns 0..719
to landscape panel columns 40..759, leaving 40 columns on each side of the
800x480 panel; all 480 JPEG rows are retained and coordinates transpose into
the native 480x800 scan order. An isolated LCD-plus-overlay edge check is in
progress. That verifies digital mapping only; physical panel-origin shift
remains possible and unverified. No host compensation or firmware change was
applied during the soak. Source snapshot PNG/geometry JSON are preserved.

## Evidence and next checks

Under `tools/gamebub/artifacts`, prefix
`handheld-elden-ring-desktop-10fps-20m-9000-20261103`:

- `.jsonl`: full sender/capture/feedback/packet events.
- `-summary.json`: final counts and logger integrity.
- `-provenance.json`: exact settings, host clock anchors and sender-module hashes.
- `-packets.csv`: all 176,129 offsets, payload lengths and host send timestamps.
- `-packet-report.json`: frame/packet records for the 50 rejected responses.
- `-analysis.json`: standard log analyzer output.
- `-metrics.json`: exact full-log quantiles, partial IDs and process sample summary.
- `-process-samples.jsonl`: memory/CPU and foreground samples.
- `-observations.jsonl`: operator update/centering observations and host geometry.
- `-receiver-final.json`: independent baseline/final stage counters, Busy examples and limits.

The CSV validates offset continuity and sent JPEG length for every complete
host send. Estimated packet UTC uses a host anchor, not receiver synchronization.
No production source code, installed Sunshine service, receiver application or
pacing/session policy was changed for this run. The sender stopped at its
planned slot limit; no subsequent stream was started.

Next compare previous commit, active-frame identity and READY-transition timing
around Busy examples 9724/20793. Evaluate any bounded admission wait as a separate
receiver candidate, measuring queue occupancy at the decision and while waiting;
29/32 session high-water does not establish safe wait headroom at each failure.
Keep host pacing/deadline work separate from that experiment. Finish physical
edge/centering checks independently. The twenty-minute run establishes sustained
counter-verified presentations with occasional losses, not loss-free 10 fps or
physical 30 fps. Do not attribute all drops to motion, Busy or the network.
