# First physical quiet stereo-tone AV session

Requested test: ten seconds from192.168.0.47 to192.168.0.157:5534, product-rounded
IMA encoding, stereo tone at gain0.25, with video and virtual-gamepad injection
off. The golden-vector preflight passed all seven packets and the exact2020-byte
PCM oracle immediately before the run. No capture/video sender process was found
running; the installed Sunshine service was left intact.

## Configuration and execution

The session/transport client is the published MoonBub reference at
`fba79ac27e7130c80d1f668e3377a0f35b0e8ae7`. Its audio worker still uses FFmpeg
encoding, so this diagnostic explicitly substitutes an in-memory tone worker
using the validated Windows `audio_codec.encode_block` full-product encoder.
The reference files themselves remain unchanged, with hashes preserved.
No claim is made that the original reference audio encoder was used.

The source is a continuous-phase440Hz left /660Hz right sine, amplitude12000
scaled by0.25 to peak3000 source sample units. Encoding is48,293 sample frames/s,
512-byte blocks containing505 stereo frames, with independent predictor/index
headers. The inherited reference worker has a four-block encoded queue. Its
transport drops audio older than80ms and performs no stale retransmission.
Handheld volume, routing and display timing were not changed.

Equivalent CLI options are:

```text
python av_client.py --receiver 192.168.0.157 --bind 192.168.0.47 --tone --gain 0.25 --seconds 10 --log tone-first.jsonl
```

The artifact wrapper installs the product encoder override before invoking that
CLI and records successful UDP sends and received datagram bytes. It never
creates a virtual controller, captures a microphone or starts a video sender.

| Measurement | Result |
| --- | --- |
| America/Denver process window | 2026-11-03 18:37:25.633–18:37:35.879 MST |
| UTC process window | 2026-11-04 01:37:25.633–01:37:35.879 |
| Requested active duration / recorded active loop | 10s /10.015s |
| Host source / peer | 192.168.0.47:59499 /192.168.0.157:5534 |
| HELLO / OFFER / START datagrams | 2 /2 /2 |
| Matching nonce / cookie | `97a383b166d322dd` /`7f9b475dd3cb7ed2` |
| Negotiated audio flags | 1; matching nonce echoes |
| Sent MSA1 audio blocks | 944 |
| First / last audio sequence | 0 /952 |
| Missing audio sequence values / host queue drops | 9 /9 |
| Host stale-audio discards | 0 |
| MSI1 packets including initial handshake / sequences | 473 /0..472 |
| MSI1 gaps / stale or invalid / input timeouts | 0 /0 /0 |
| KEEPALIVE datagrams / sequence range | 91 /2..92 |
| STOP sent / sequence | 1 /93 |
| All datagrams pass independent Windows schema/CRC parsing | Yes |
| All944 sent ADPCM blocks product-decode to2020 bytes | Yes |
| Process result / stderr | Exit0 /empty |

The sequence gaps match intentional host encoded-queue drops; they do not prove
Wi-Fi loss. All captured packets use the same pinned endpoints. Raw sent blocks
are retained separately for decoder replay; they are not a DAC/acoustic recording.

## Last MSI1 audio snapshot

| Field | Last reported value |
| --- | ---: |
| Accepted/committed audio blocks, AV session | 942 |
| Rejected/unconfirmed audio blocks, AV session | 0 |
| FPGA queued PCM frames | 1,142 |
| FPGA played PCM frames, lifetime | 474,067 |
| FPGA underruns, lifetime | 13 |
| State | 7: ACTIVE, AUDIO_ENABLED, FPGA_SNAPSHOT_VALID |
| FPGA build ID | `0x4d424f50` |

The first valid FPGA snapshot already reported3 accepted blocks,1,303 queued
frames,216 played frames and zero underruns. From that first valid snapshot to
the last, played advanced473,851 frames and underruns increased13. These are
receiver-reported digital consumption counters, not acoustic measurements or
an exact start-to-finish playback duration. AUDIO_ENABLED represents negotiated
mode, not health or proof that sound is reaching the speakers.

The last reported accepted count is two below the944 host sends. No audio send
was timestamped after receipt of the last MSI1, but FPGA snapshots can be cached;
that does not establish when its counters were sampled. The two-block difference
remains unresolved pending the receiver's final post-STOP counters/log. Do not
label it loss, acceptance or rejection from host counts alone. STOP has no ACK;
the host proves transmission, not the receiver's final flush or silence.

The operator subsequently confirmed that the receiver accepted **all944 sent
blocks**, with9 sequence gaps and13 underruns, and that the tone was audible.
This resolves the two-block admission-count difference from the earlier MSI1
snapshot. It does not independently verify final queue occupancy, STOP flush or
the reasons/timestamps for each underrun. The saved initial snapshot remains
unchanged.

## Sender sequence and gap records requested afterward

| Accounting item | Result |
| --- | --- |
| Sent blocks | 944 |
| Sender queue drops / stale drops | 9 /0 |
| First / last sent audio sequence | 0 /952 |
| Encoded blocks accounted for through sequence952 | 953 |
| Exact final worker encoded total | Not logged; at least953 |

The exact final encoder counter and unsent queue contents were not captured.
Do not equate953 accounted blocks with the complete final encoder total; a
bounded unsent tail may have remained at shutdown.

The skipped IDs are **69,139,175,235,495,504,713,762,906**. All nine are absent
from the host's successful audio sends, matching the reported nine sender
queue drops. With the receiver's confirmation that all944 sends were accepted,
there is no unexplained delivery deficit in this run's final frame accounting.
That does not locate or establish a cause for the13 underruns.

The eight largest recorded send gaps were32ms:

| Previous sequence → next sequence | Measured host gap |
| --- | ---: |
| 2 →3 | 32ms |
| 73 →74 | 32ms |
| 125 →126 | 32ms |
| 168 →169 | 32ms |
| 459 →460 | 32ms |
| 503 →505 | 32ms; sequence504 omitted |
| 802 →803 | 32ms |
| 938 →939 | 32ms |

There were also24 gaps recorded as31ms. The complete943-gap histogram is
0ms:336,15ms:215,16ms:360,31ms:24,32ms:8. Full before/after host monotonic
timestamps, preparation timestamps and every missing-ID window are saved in
`sender-gap-report.json` and `send-gaps.csv` in the session artifact directory.
The15.625ms clock resolution below limits the precision of these observations.

## Timing limits and acoustic result

The host reference uses Python3.11 `time.monotonic[_ns]`, implemented here by
`GetTickCount64()` with15.625ms reported resolution. The encoded block period is
about10.457ms. Recorded audio send gaps are quantized: min0ms, median15ms,
p95 16ms, max32ms. A zero measured gap does not prove simultaneous transmission.
Preparation-to-send ages were min0ms, median16ms, p95 32ms, max47ms. These are
coarse host timing observations, not receiver arrival or physical audio latency.
The host clock/scheduling is a candidate for a later controlled high-resolution
timing comparison; it does not independently explain every queue drop/underrun.
No settings were changed during this run and no second tone was started.

The Windows agent cannot hear the handheld or access the other machine's webcam
microphone recording. The operator was asked whether the tone was audible,
whether gaps/clicks occurred, whether channels could be distinguished, and for
final receiver counters. The operator has now confirmed **the tone was heard**;
gaps/clicks and left/right acoustic separation have not been characterized.
This run demonstrates AV ingress, receiver-reported digital playback and
operator-confirmed audibility, with
13 observed underruns; it is not a clean-continuity or A/V synchronization pass.

## Evidence

`tools/gamebub/artifacts/av-v1-tone-first-product-20261103/` contains unchanged
reference source and SHA-256 manifest, `tone-first.jsonl`, raw `packets.jsonl`,
`stdout.jsonl`, `stderr.txt`, `run-metadata.json` (including product-encoder and
wrapper hashes), `analysis.json`, and `sent-blocks.ima`. All files are local
evidence; receiver/acoustic recordings remain on the other machine.
The later accounting extraction adds `sender-gap-report.json`, `send-gaps.csv`
and the attributed `receiver-confirmation.json`; original logs remain intact.
The preflight result is `artifacts/av-v1-before-tone-first-golden-20261103.json`.
