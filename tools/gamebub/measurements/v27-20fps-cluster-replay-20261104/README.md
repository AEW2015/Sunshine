# Windows packet-schedule replay and MoonBub handoff

The original host send schedule does not reproduce the hardware failures in
the pinned Python transport reference. **Do not start another hardware run yet.**
Add bounded packet-identity and consumer-phase history on MoonBub first, then
repeat the same 20 fps / 3 Mbps / Q25 scenario with camera coverage verified
before transmission. Build50 remains unchanged pending evidence implicating it.

## Reconciled five-minute run

IDs 2,001,000–2,006,999: 6,000 encoded = 5,360 complete sends + 640 host
replacements. Of the complete sends, 5,329 were accepted/decoded/presented,
29 had Sequence rejections and two remain unresolved: 2,004,772 and 2,004,806.
Receiver queue drops 45, peak 32/32, first recorded drop 2,004,708 / 5,120.
Core faults and transport overflows were zero. Power saving restored after STOP.
Camera confirmed changing content for the first 2m40s, not the failure cluster.

## What was replayed

The original JPEG bytes and actual UDP/RF arrivals were not retained. This
package preserves frame IDs, capture timestamps, frame lengths, offsets, counts,
SOF/EOF boundaries and successful host post-send timestamps. Replay replaces
payloads with zero bytes of the recorded sizes and recomputes frame CRCs. Those
payloads are **not JPEGs**: this checks transport assembly only, without JPEG,
FPGA, QSPI or receiver application queue behavior.

The reference is hash-checked MoonBub Python `host/moonshine/protocol.py` at
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52`. It is an older transport reference,
not the installed v27 receiver application. Its behavior cannot clear current
firmware of a defect or reproduce the hardware queue's scheduling.

| Inclusive frame-ID window | Transmitted frames | Packets | Recorded span | Offline / paced localhost complete |
|---|---:|---:|---:|---:|
| 2,001,108–2,001,112 | 3 | 75 | 0.259 s | 3 / 3 |
| 2,004,704–2,004,812 | 87 | 1,676 | 5.414 s | 87 / 87 |

Both windows include neighboring frame tails and SOFs. The cluster includes
both unmatched IDs and both following backward-offset failure IDs. Missing
frame IDs in these ranges can be host replacements, not missing packets.
Host-log order had no timestamp reversals, offset discontinuities or incomplete
tails before the next SOF. The reference reported zero invalid datagrams;
localhost returned all 90 ACKs. Maximum localhost scheduling lateness was
1.138 ms and 1.251 ms respectively, so this is an approximate real-time replay,
not an exact reproduction of network timing. No traffic reached the handheld.

## Backward-offset hypotheses

Host records put 2,004,773 offset 1,024 before 16,384, and 2,004,807 offset
6,144 before 14,336. Selected surrounding gaps were approximately 2.9–3.9 ms.
These post-send-call records do not establish NIC/RF departure or receive order.

Two explicit injected-loss demonstrations truncate an older frame, then omit
the following frame's SOF/prefix:

| Older frame retained | Expected older offset | New incoming frame | Observed newer offset |
|---|---:|---|---:|
| 2,004,772 | 16,384 | 2,004,773 | 1,024 |
| 2,004,806 | 14,336 | 2,004,807 | 6,144 |

The reference rejects both with `no matching frame start`. This demonstrates
how numerically backward offsets can occur across frame identities without
same-frame reordering. **Loss was deliberately injected; neither scenario is
established as the hardware cause.** The receiver records lack the active
assembler frame ID, and neither unresolved older send has a retained outcome.

The first measured queue overflow's 1.963 ms since last dequeue does not give
the preceding backlog or consumer phase. Frame 2,004,810's maximum residence
21.179 ms, QSPI 326 us and lock 24 us cannot characterize earlier failures.
Consumer timing excludes error cleanup and buffer recycling. No cause emerged
from this replay that justifies choosing a pacing or FPGA change now.

## Receiver instrumentation before repeating

Use a bounded ring keyed by receiver monotonic time and packet ordinal. Record
incoming frame ID/capture timestamp/offset, active assembler frame ID and next
expected offset at enqueue, dequeue, reject and overflow. Retain queue occupancy,
consumer phase transitions, lock/QSPI waits, completion/admission waits, cleanup
and buffer recycling. Include absolute first-overflow timestamp and the last
bounded history entries. Export on failure after the run; avoid per-packet
serial printing in the receive path. Record trace overflow/lost-event counts.

This is a receiver-agent implementation proposal, not an installed change.
Keep build50, overlap, 32 slots and existing video settings fixed when evaluating
that instrumentation. Verify the actual receiver identity and camera recording
coverage before transmission. A saved moving clip is preferable for repeatable
content: this soak captured an uncontrolled desktop, so an identical source clip
cannot be recovered from this package.

## Files and reproduction

`video.jsonl` is a filtered metadata-only excerpt, not the full run. Its summary
line describes the full run; do not apply full-run totals to the excerpt.
`provenance.json` records both full-log and excerpt hashes. TSV schedules are
portable for the receiver agent. `receiver-reconciliation.json` contains selected
exact host timestamps and the operator-supplied receiver counters.
`schedule-replay-result.json` is the original Windows result; rerunning the
script overwrites that file with a new result and new timing measurements.

From this directory, using the existing GameBub laboratory Python environment:

```powershell
$env:MOONBUB_REFERENCE = 'C:\path\to\moonbub'
& '..\..\.venv\Scripts\python.exe' -m unittest -v test_replay_study
& '..\..\.venv\Scripts\python.exe' replay_study.py
```

The local MoonBub clone must contain the pinned reference commit above; no
checkout is required. The scripts reuse Sunshine's existing `reference_loopback`
and `msv1` modules. Five regression checks pass: CRC/completion, window export,
frame boundaries/timestamp regression, missing-tail/SOF identity conflict, and
reorder rejection followed by newer-SOF recovery. No production code changed.
