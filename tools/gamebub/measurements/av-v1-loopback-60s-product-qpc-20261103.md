# One-minute Windows speaker-loopback AV session

Completed the requested60-second AV session from192.168.0.47 to
192.168.0.157:5534. Source was the default Windows speaker output, with gain0.25,
product-rounded stereo IMA ADPCM, no video sender and no virtual-gamepad
injection. The installed Sunshine service remained running and untouched.
No output-device selection, handheld volume/routing or display timing changed.

## Configuration

The published MoonBub AV session client at `fba79ac27e7130c80d1f668e3377a0f35b0e8ae7`
was extracted to an isolated artifact directory. A wrapper substitutes a WASAPI
loopback worker using the validated Windows `AudioEncoder`, which resamples to
48,293Hz and uses full-product IMA predictor updates. The capture endpoint was
`Speakers (Realtek(R) Audio) [Loopback]`, device28,48kHz. It advertises eight
channels; the stream explicitly requested the previously verified stereo format.
It did not capture a microphone or synthesize the earlier test tone.

The reference session loop, handshake clock, audio preparation timestamps and
packet logger use the same `perf_counter_ns`/QueryPerformanceCounter domain
for this run, with reported100ns resolution. Reference files remain byte-unchanged;
worker and clock behavior are explicitly overridden in memory. This differs
from the earlier tone run's15.625ms-resolution GetTickCount64 clock and is not
a one-factor performance comparison because the source also changed.

The encoded queue remains bounded to four blocks, and the reference sender
discards prepared audio older than80ms. Capture overflow/short reads fail with
an error; none occurred. A final worker snapshot records exact encoded count,
queue discards, queued unsent blocks, capture frames and resampler tail. The
golden packet/PCM preflight passed before opening the session.

## Results

| Measurement | Result |
| --- | --- |
| America/Denver process window | 2026-11-03 18:48:21.010–18:49:22.291 MST |
| UTC process window | 2026-11-04 01:48:21.010–01:49:22.291 |
| Active session window | 60.023s, including source startup |
| Captured source audio | 2,789,280 stereo frames /58.11s at48kHz |
| Host source / receiver | 192.168.0.47:61347 /192.168.0.157:5534 |
| Session cookie | `cef6deba49b36459` |
| Encoded / sent audio blocks | 5,557 /5,530 |
| Queue drops / stale-audio drops / unsent queued at close | 24 /0 /3 |
| Source capture errors / worker error | 0 /none |
| Last partial resampled tail | 5 stereo frames, not padded/sent |
| First / last sent audio sequence | 0 /5553 |
| Internal sequence values omitted by host | 24, matching queue drops |
| MSI1 packets including initial handshake / sequences | 2,826 /0..2825 |
| MSI1 gaps / invalid / stale / input timeouts | 0 /0 /0 /0 |
| STOP sent | Control sequence570 |
| Process result / stderr | Exit0 /empty |

Accounting reconciles exactly:5,557 encoded =5,530 sent +24 queue-dropped +3
still queued at shutdown. All5,530 captured MSA1 bodies validate and decode to
2,020 PCM bytes each using the product-rounded profile. Packet CRC/schema checks
passed for the entire captured exchange and endpoints stayed pinned.

All5,811 capture reads contained nonzero source samples; the largest raw input
magnitude was32,768 before gain. This confirms non-silent PC output capture,
not source identity, acoustic quality or freedom from source clipping. Startup
inside the active session accounts for the difference between its60-second
duration and58.11 seconds of captured source material. No extra session was
started to fill the startup interval.

## Receiver-reported digital playback

| Snapshot field | First valid | Last valid |
| --- | ---: | ---: |
| Accepted audio blocks, current AV session | 0 | 5,476 |
| Rejected/unconfirmed audio blocks, current AV session | 0 | 4 |
| Queued PCM frames | 0 | 2,040 |
| Played PCM frames, lifetime | 475,721 | 3,239,065 |
| Underruns, lifetime | 13 | 30 |

The observed played-counter increase was2,763,344 PCM frames, and underruns
increased by17 during the captured valid-snapshot interval. Final state was7
(ACTIVE, negotiated AUDIO_ENABLED and FPGA_SNAPSHOT_VALID), build ID
`0x4d424f50`. These are receiver-reported digital counters, not acoustic output.
The mode bit is not readiness or health evidence.

The last MSI1 accounts for5,480 accepted or rejected/unconfirmed outcomes,
50 below5,530 host sends. At that point final post-STOP evidence was pending;
the later report is recorded below. Do not label those50
as lost or accepted from host data alone. The4 rejected/unconfirmed count also
does not establish physical rejection after an ambiguous commit. STOP has no
ACK; host transmission does not prove final flush/silence.

### Post-STOP receiver confirmation

The operator subsequently confirmed that the PC audio was audible. Post-STOP
receiver counters were5,477 accepted blocks,4 rejected/unconfirmed, zero queued
PCM frames,3,239,425 lifetime played frames and30 lifetime underruns. The final
played delta from475,721 was2,763,704 frames; underruns increased17, from13 to30.
This adds one accepted block and360 played frames beyond the last MSI1 snapshot.

The final admission accounting covers5,481 of5,530 sends, leaving **49 sent
blocks without a recorded outcome**. This is not evidence that those49 were
necessarily lost on Wi-Fi; receiver per-sequence records are needed to assign
causes. The four rejected/unconfirmed outcomes retain their published ambiguity.
Zero queued after STOP is receiver-reported final occupancy, not an independent
acoustic silence measurement. The original host snapshot is preserved above.

The receiver recorder is being fixed to re-arm for each audio session before a
repeat is requested. No new session was started in response to this report.

## Host timing and acoustic limits

High-resolution host audio send gaps: min0.154ms, median10.823ms,
p95 20.792ms, max32.463ms. Preparation-to-send ages: min0.273ms,
median15.704ms, p95 29.936ms, max58.479ms. Timestamps follow successful host
socket sends, not receiver arrival, RF transmission or DAC presentation. These
measurements do not establish which scheduling/transport event caused any of
the17 additional underruns.

The operator was asked whether the PC audio was audible and whether gaps,
clicks or distortion occurred, plus final receiver counters after STOP. Audible
quality beyond audibility remains uncharacterized. The operator confirmed the
PC audio was heard and supplied the post-STOP counters above; gaps, clicks and
distortion were not characterized. The Windows agent cannot hear the handheld.
This is a completed one-minute test, not a clean-continuity or A/V sync pass.

Artifacts under `tools/gamebub/artifacts/av-v1-loopback-60s-product-qpc-20261103/`:
reference sources and hashes, `loopback-first-60s.jsonl`, raw `packets.jsonl`,
`stdout.jsonl`, `stderr.txt`, `run-metadata.json` (exact worker accounting and
QPC details), `analysis.json` and `sent-blocks.ima`.
`receiver-confirmation.json` preserves the later attributed post-STOP report.
The preflight result is
`artifacts/av-v1-before-loopback-minute-golden-20261103.json`. The socket was
closed at completion; no additional stream was started.
