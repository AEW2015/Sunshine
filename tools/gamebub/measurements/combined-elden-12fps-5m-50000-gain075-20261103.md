# Five-minute 12 fps video, PC audio and Elden Ring controller test

The operator requested all three paths together and agreed to preserve receiver
counters. Ran the desktop MSV1 sender targeting12fps,720x480,q25,2Mbps, zero
host shift, plus one AV v1 session carrying PC speaker-loopback audio at gain0.75
and the operator-confirmed Elden Ring gamepad profile. Audio and controller used
the same cookie/socket; video remained on its separate5533 path. The installed
Sunshine service was not replaced or restarted.

**Result: the combined paths ran, but did not qualify stable12fps playback.**
The host completed10.807 video sends/s and audio rejection/underruns increased
substantially. The controller stayed live with no input timeout. Video is now
stopped and the regular controller-only session has been restored. No unlogged
change of bitrate, quality, gain, firmware or mapping was made during the test.

## Configuration and provenance

Golden packet vectors and the exact2020-byte PCM oracle passed before launch.
Video used the existing tested Desktop Duplication capture/letterbox/JPEG path,
source192.168.0.47:55534 to192.168.0.157:5533,200ms frame-age deadline,
fixed q25 and262,144-byte guard. The12fps×300s schedule assigned IDs50000..53599.
Primary-desktop acquisition can include repeated or non-game images; moving
gameplay and optical continuity await the operator report.

AV used192.168.0.47:64957 to192.168.0.157:5534, cookie`ed422c4cdf7fa9d1`,
the pinned reference session transport at`fba79ac2`, the validated product-rounded
Windows encoder,48,293Hz stereo512-byte/505-frame blocks and QPC timing. The
four-block encoded audio queue and80ms stale threshold were retained. The
Elden Ring profile mapped D-pad→left stick, A→RB, B→left-stick click, X→LT and
Y→Xbox A. No MSF1 feedback drove virtual input.

The2Mbps cap applied to video MSV1 bytes; audio/control were additional traffic,
approximately0.43Mbps for nominal audio before UDP/IP/Wi-Fi overhead. This was
not a shared aggregate2Mbps scheduler or a stock Moonlight/Sunshine session.
Reference files and current video/audio/controller module hashes are preserved.
Independent receiver starting-stage counters were not supplied in the host log.

| Host window, America/Denver | Time on2026-11-03 MST |
| --- | --- |
| AV process | 19:44:47.908–19:49:48.219 |
| Video process | 19:44:49.257–19:49:50.001 |

UTC windows are2026-11-04T02:44:47.908–02:49:48.219 and
02:44:49.257–02:49:50.001 respectively. Active AV duration was300.040s and
video summary duration300.737s. The nearly simultaneous processes overlap for
approximately299s; no exact five-minute all-stage optical observation is claimed.

## Video outcomes

| Measurement | Result |
| --- | --- |
| Target slots / submitted and encoded | 3,600 /3,516 |
| Complete / partial / zero-byte sends | 3,250 /91 /46 |
| Skipped schedule slots / stale encoded replacements | 84 /129 |
| Accepted / rejected / pending matched ACKs | 3,241 /8 /1 |
| Final cumulative received / dropped feedback | 3,241 /100 |
| Complete host sends / accepted ACKs per full duration | 10.807 /10.777 per second |
| Encoded JPEG / sent MSV1 bitrate | 1.592 /1.546Mbps |
| Packet timing frames / datagrams | 3,341 /56,152 |
| Packet gap ms p50 /p95 /max | 4.981 /5.413 /24.498 |
| Logger records /lost /I/O error | 18,764 /0 /none |

Accounting:3,600 target slots =84 skipped +3,516 encoded;3,516 encoded =3,250
complete +91 partial +46 zero-byte +129 replaced. Complete sends reconcile as
3,241 accepted +8 rejected +1 pending. All8 rejected ACKs refer to complete sends;
the full-send pending ID is50543. Matched rejected IDs are50031,50342,50544,
51051,51082,51104,52991,53310. Their receiver reasons remain pending.

The137 incomplete send results are deadline-limited; exact internal deadline
guard selection is not logged. Received-plus-dropped feedback numerically totals
3,341, equal to all nonzero sends, but that does not identify the disposition
of50543 or the reasons for individual partial frames. The host counter tracker
excludes the first accepted frame when establishing its feedback baseline.
Decode/presentation and receiver queue metrics require independent receiver data;
these send/ingress rates are not displayed or distinct-game-frame FPS.

## Audio and input outcomes

| Measurement | Result |
| --- | --- |
| Encoded /sent audio blocks | 28,331 /28,262 |
| Host queue drops /stale drops /unsent at close | 65 /0 /4 |
| Capture errors /worker error | 0 /none |
| Captured source duration at48kHz | 296.26s |
| First /last sent audio sequence | 0 /28326 |
| Missing internal audio sequence values | 65, matching host queue drops |
| Last MSI1 accepted /rejected-unconfirmed blocks | 25,992 /2,254 |
| Sent blocks not in those final admission counters | 16 |
| MSI1 packets including handshake /sequence range | 14,026 /0..14025 |
| MSI1 gaps /invalid /stale /input timeouts | 0 /0 /0 /0 |
| KEEPALIVE count /STOP sequence | 2,831 /2833 |
| Audio host send gaps ms p50 /p95 /max | 10.429 /20.449 /58.103 |
| Audio preparation-to-send age ms p50 /p95 /max | 15.671 /29.899 /50.378 |

Exact audio accounting:28,331 encoded =28,262 sent +65 queue-dropped +4 unsent.
Every sent audio body validates and product-decodes to2020 bytes. Host byte/schema
validation and block independence do not prove receiver acceptance or sound.
Admission counters leave16 sent outcomes unresolved. Rejected/unconfirmed retains
the published ambiguity after I/O or commit failure; it is not necessarily
physical rejection. The receiver's per-sequence reasons were requested.

Final MSI1 state was3 (ACTIVE and negotiated AUDIO_ENABLED, snapshot-valid clear).
Its queued/played/underrun zero fields must therefore be ignored. Of14,025 loop
MSI1 records,10,756 had valid FPGA snapshots and3,269 did not. The first valid
snapshot showed6,036,993 lifetime played frames and45 underruns. The last valid
snapshot, sequence14020, showed19,152,499 played frames,1,812 underruns and862
queued PCM frames: increases of13,115,506 played frames and1,767 underruns.
Those are last-valid-snapshot deltas, not final post-STOP measurements.
The final input still arrived while snapshot-valid was clear; controller input
remained independent of video/admission status.

The restored input-only session later reported valid FPGA lifetime counters
19,162,594 played and1,812 underruns, with zero audio session counters. This
provides a later digital snapshot, but cannot recover the previous cookie's
final accepted/rejected count or replace the requested receiver recording.
No optical/acoustic quality or A/V synchronization result is inferred from
these counters. The large underrun rise prevents a continuity pass.

## Follow-up and current state

The operator was asked to supply final received/decoded/presented and queue
counters, audio post-STOP outcomes, first audio failure/QSPI reason and observed
freezes/gaps/control delay. Those reports remain pending. Do not attribute
failures specifically to Wi-Fi, QSPI, FPGA decode or host scheduling from these
counts alone. A matched5fps combined control and receiver timing/failure traces
would be the next measurement before increasing bitrate or changing the codec.

The pre-existing controller-only process was closed to avoid a competing AV
cookie, with its prior log retained. At test completion, the normal Elden Ring
controller console was restored for up to2h: source192.168.0.47:57614, cookie
`cd0be9feb028b3a2`, log`controller-20261104T025006072203Z.jsonl`. Audio/video are
off in that restored session. No third combined test was started.

## Evidence

AV/session files are under
`tools/gamebub/artifacts/combined-elden-12fps-5m-50000-gain075-20261103/`:
`combined-av.jsonl`, raw `packets.jsonl`, source manifest, exact-worker
`av-metadata.json`, `counter-summary.json`, `analysis.json`, `sent-blocks.ima`,
stdout/stderr and process records. Video files under `artifacts` have prefix
`combined-elden-video-12fps-5m-50000-20261103`: JSONL, summary, provenance,
packet CSV/report, analysis and outcome-ID details. The golden preflight is
`artifacts/combined-elden-before-golden-20261103.json`. Packet offsets/complete
JPEG lengths and AV payloads were checked offline after the run. Original logs
were not rewritten to substitute received/displayed or audible claims.
