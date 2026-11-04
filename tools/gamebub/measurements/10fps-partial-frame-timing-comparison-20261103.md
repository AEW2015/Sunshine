# Comparing 10 fps partial frames before changing bitrate or quality

No receiver application, v19 mode, admission policy, sender source code, quality,
bitrate or deadline was changed. No additional hardware stream was sent. This
compares the saved [10 fps run](handheld-v19-overlap-10fps-20s-8218-20261103.md)
with the [5 fps run](handheld-v19-overlap-5fps-5m-6718-20261103.md), plus two
separate offline host probes at unchanged quality and packet interval.

## Failure classifications and receiver evidence

The 200 offered frames divide into 161 complete sends, 28 partial sends stopped
at packet-pacing deadline guards, and 11 zero-byte whole-frame preflight
refusals. There were no host socket errors, feedback timeouts/suppression,
capture-slot skips or raw/encoded replacements. The exact pre-wait versus
post-wait guard and its timestamp were not logged for the partial frames.

The receiver independently counted all 161 accepted frames decoded/presented,
zero queue packet drops, zero errors/faults/overflows/underruns and no recorded
Busy diagnostics. Session queue high-water remained 25/32; no separate run peak
was recorded. Its 28 new drops numerically match the 28 host partial sends.
That numerical agreement is not an individual receiver reason for each frame.

Only 8340 retains another partial-frame timing sample. For 8244 and
8264..8288, no reason, byte count or timestamps survived. None of these partial
frames has an explicit retained receiver reason string.

| Frame 8340 detail | Host evidence | Receiver evidence |
| --- | --- | --- |
| Packet count | 20 sent datagrams | 20 observed socket packets |
| Payload | 20,480 bytes sent of a 21,652-byte JPEG | 20,480 bytes successfully forwarded over QSPI |
| Last sent offset / first unsent offset | 19,456 / 20,480; 1,172 bytes remained | Not independently retained |
| First-to-last packet span | 93.4988 ms | 91.066 ms, socket reception timestamps |
| Subsequent interval | Next actual SOF 8341 sent 5.2492 ms after last packet | Trace finished 10.667 ms after last socket packet |

Receiver timestamps were first packet 5,577,180,408 us, last packet
5,577,271,474 us and trace finish 5,577,282,141 us. The QSPI byte count is not
an independent received-byte counter. Socket timestamps are not RF-arrival
timestamps. No next-SOF identity or explicit supersession event was retained.
The finish is consistent with next-SOF supersession, but that remains an
inference. These host/receiver intervals have different event boundaries;
do not subtract clock origins or interpret their difference as network latency.

## Encoding versus queueing and packet pacing

Values below are exact full-log nearest-rank p50 / p95 milliseconds.

| Send class | Frames | Encode/validation | Encoded queue wait | First-to-last packet span | Post-retrieval age at send record |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete | 161 | 2.158 / 2.685 | 0.237 / 62.936 | 94.554 / 123.870 | 113.642 / 189.950 |
| Partial | 28 | 2.222 / 2.772 | 82.804 / 87.514 | 95.123 / 115.004 | 194.541 / 196.134 |
| Zero-byte | 11 | 2.467 / 12.676 | 83.088 / 89.455 | No packets | 94.773 / 100.488 |

Partial-frame encoding had no large spikes: its maximum was 2.796 ms. Complete
and zero-byte groups each contain a larger isolated encoding observation, but
the consistent partial-frame difference is substantial encoded queue residence.
The groups differ in size/content and are not randomized treatment groups.

For 100 common nominal source times (the first 100 frames at 5 fps versus
every second frame in the 10 fps sample), JPEG lengths matched in all 100
pairs. This is a size check, not a pixel/hash identity check. In those pairs:

| Metric | 5 fps p50 / p95 ms | 10 fps p50 / p95 ms |
| --- | ---: | ---: |
| Encode/validation | 2.223 / 2.539 | 2.185 / 2.851 |
| Encoded queue wait | 0.146 / 0.235 | 12.787 / 85.402 |

At the configured 2 Mbps, a full 1,024-byte payload plus 40-byte MSV1 header
has a 4.256 ms serialization interval. The 3,692 observed within-frame packet
gaps were p50 4.9838 ms, p95 5.2033 ms, maximum 7.5815 ms. Successful frames'
first-to-last packet spans exceeded their ideal configured spans by median
13.627 ms and p95 17.884 ms (mean 13.692 ms). This excess includes scheduling,
callbacks, locks and socket work; sleep overshoot cannot be separated from
those components in the original log.

All 200 complete JPEGs would require 4,408,543 MSV1 bytes: **1.763 Mbps** over
the nominal 20-second offered timeline. The largest ten-frame nominal one-second
window requires **2.176 Mbps**. Thus mean demand is below the configured cap,
but content bursts exceed it. Existing queue age, preparation time and pacing
overhead consume the 200 ms budget. Improving waits alone is not yet proven
sufficient for loss-free delivery of every frame at the same cap/deadline.

## Separately measured offline source preparation

The original hardware run timestamps age only after source acquisition returns.
It did not record acquisition start/end, canvas/copy duration, raw-queue wait,
the precise deadline guard or sleep requested/returned timestamps. These cannot
be reconstructed as distinct stages from its residual age.

An uncapped sequential offline profile processed the same first 200 clip frames
at 10 fps source sampling and quality 25, without a socket or pipeline. All
200 resulting JPEG lengths matched the original log, totaling 4,239,103 bytes.

| Offline operation | p50 ms | p95 ms | Maximum ms |
| --- | ---: | ---: | ---: |
| Acquire next selected clip frame (decode/iterator work) | 3.639 | 5.976 | 16.957 |
| Scale/convert/letterbox canvas | 7.752 | 8.734 | 9.175 |
| Owned RGB copy corresponding to pipeline submit | 0.343 | 0.483 | 0.685 |
| Strict JPEG encode and validation | 2.203 | 2.592 | 15.737 |

This separate Windows profile excludes live desktop capture, worker overlap,
queues, network and receiver processing. It does not recover original-run
capture timing or establish playback throughput. Stage percentiles must not be
added to claim a combined percentile.

An additional isolated 500-sample probe requested `time.sleep(0.004256)` without
capture, sockets or the receiver. Observed sleep p50 was **4.98345 ms**, p95
**5.1782 ms**, range **4.273..5.4384 ms**. This reproduces most of the observed
gap scale without a network, making host wait behavior a concrete optimization
candidate. It does not prove that all original gap excess was sleep overhead.

## Next development step

Keep v19/application/admission unchanged and retain quality 25, 2 Mbps and the
200 ms deadline for the next comparison. Before selecting a higher bitrate or
lower quality:

1. Add bounded host-only acquisition, canvas/copy/raw-queue, send-start/end and
   explicit deadline-rejection metadata, including failed offset, due time,
   requested wait and actual return. Preserve existing scheduling behavior.
2. Compare current and candidate wait strategies offline at the same packet
   interval, including CPU cost, tails and the existing no-catch-up-burst rule.
   Do not shorten packet spacing to make up accumulated scheduler delay.
3. Validate a selected pacing change through deterministic deadline/no-burst
   tests and loopback before requesting an unchanged-settings hardware repeat.
4. Use the repeat to determine remaining content-burst headroom before choosing
   bitrate or quality changes. Admission-wait remains a separate experiment;
   Busy has not been demonstrated in this 10 fps run.

## Artifacts

Under `tools/gamebub/artifacts`:

- `handheld-v19-overlap-10fps-20s-8218-20261103-timing-comparison.csv`: all 200
  frame dispositions, encoding/queue/pacing times, offsets and next-SOF gaps.
- Matching `-timing-comparison.json`: grouped distributions and source-pair checks.
- Matching `-frame-8340-correlation.json`: retained receiver timing with limitations.
- `host-10fps-clip-stage-profile-20261103.csv` and `.json`: offline stages,
  source/module hashes, dependency versions and exact reproduction command.
- `host-2mbps-sleep-probe-20261103.json`: 500 raw wait observations and provenance.

No new receiver run or production source edit was made for this analysis.
