# Packet permits, fused first-map capture and checksum optimization

Date: 2026-11-04, America/Denver. Work remains isolated from the installed
Sunshine service and original checkout. No receiver stream, probe, firmware
flash or FPGA reload was performed. Parallel agents implemented fused encoding
and permit accounting; Luna audited receiver readiness and measured CRC costs.

## Native changes

- The first cached map now captures raw forward coefficients while doing its
  normal conversion/transform/quantization/entropy work. It avoids the earlier
  separate analysis pass and duplicate first-call canonical validation. Later
  maps still validate canonical reference samples. No validation is removed.
- Incomplete capture is private and cannot be used as ready analysis. A failed
  callback clears retained analysis and permanently rejects callback reuse.
  Immutable source/reference/frame identity and ordered four-map limits remain.
- IEEE CRC32 now uses a compile-time 256-entry table, with the same polynomial,
  initialization, final XOR and wire bytes. The table occupies 1,024 immutable
  bytes. This is not the different CRC32C polynomial used by some CPU opcodes.
- `PacketLedger` accounts for five DATA permits, a shared QC18/FG19 mailbox,
  bounded frame accounts and queries, exact route/slot/generation matching,
  unsent cancellation and conservative stop. Unknown PC18 status2 can release
  its matching query mailbox but never the DATA permit. Late queried replies
  cannot return a newer DATA generation in a reused slot.
- Packet and frame sender ledgers are noncopyable/nonmovable, preventing
  accidental duplication or replacement of outstanding ownership. Calls must
  be serialized by one owner; this is not a thread-safe network endpoint.

The ledger owns logical receiver permits/metadata, not the caller's returned
`Outbound.bytes` or a host asynchronous-send/DMA lifetime. The actual sender
must retain those bytes until local send completion and all applicable readers
drain. A receiver PC18 permit is not a local send-completion certificate.

## Checks completed independently of hardware

The expanded executable passes all twenty encoder golden cases, including the
thirteen mandatory cached policy attempts. Report:
`artifacts/v20-packet-fused-crc-golden-final-20261104.json` for the final executable.
The full Python suite completes 379 tests with five existing skips, including
actual packet-model and baseline/cached CLI checks. Log:
`artifacts/v20-packet-fused-crc-python-tests-20261104.txt`.
All 81 native tests pass with a clean build/run in
`artifacts/v20-packet-fused-crc-tests-20261104.{txt,xml}`. Merged source-line
coverage is 138/138 for `packet_ledger.h` and 104/104 for `packet_model.h`;
branch coverage remains incomplete. Final CLI smoke checks pass seven tests
in `artifacts/v20-packet-fused-crc-cli-final-20261104.txt`.

`--packet-model 10000` uses real native packet parsers/serializers and both sender
ledgers, but no socket or hardware. Its independent deterministic cases produce:

| Result | Cases |
| --- | ---: |
| Complete host bookkeeping, with explicit external model RELEASE | 7,419 |
| Safe stop retaining unresolved DATA/query/frame ownership | 2,581 |
| Corrupted PC18 rejected | 10,000 |
| Stale PC18 ignored | 10,000 |
| Matching unknown credit retains DATA | 2,528 |

Peak modeled ownership is five DATA permits plus one control mailbox. Each
stopped case retains its five unresolved DATA permits. The aggregate retained
counter sums independent cases; it is not a live pool with 12,905 permits.
Report: `artifacts/v20-packet-model-10000-20261104.json`.

The payloads are synthetic packet bytes, not valid codec frames. A fresh ledger
per case is a fresh model, not a production reset. The modeled RELEASE is an
explicit external input, not something inferred from PC18. This does not prove
network delivery, receiver drain, AF03 publication or production recovery.

## Performance evidence and limits

A standalone O3 microprobe compared the old bitwise CRC with a 256-entry table.
It mutates a 49,152-byte payload for 1,000 iterations per variant to prevent
loop hoisting. Bitwise: 573.499 ms; table: 163.186 ms, an observed 3.514x speedup
for this CRC workload. All 2,064 seeded small cases plus aggregate/final large
checksums match. Artifact: `artifacts/crc32-probe/result.json`.
This is a single synthetic CRC comparison, not a video FPS or latency result.

Two exploratory fused/bitwise profiles briefly overlapped and are excluded
from sequential performance comparison. They remain saved as
`artifacts/v20-fused-bitwise-{2600,7200}-600-20261104.json`.
Their timing environment also had active WoW/background host load, with large
changes in unchanged stages. The cause of that timing change was not isolated.
Do not compare them directly with earlier runs with unrecorded or different
host load, or attribute the whole change to fused encoding.
Bitstream correctness is established separately by the golden/tests evidence.

After compilation and tests became idle, four new 120-frame diagnostics ran
sequentially with the same final binary and table CRC. WoW remained active;
background workload was not controlled. These short samples are not directly
comparable to the earlier 600-frame reports.

| Source preparation + admission | Easy raw | Easy fused/reused | Complex raw | Complex fused/reused |
| --- | ---: | ---: | ---: | ---: |
| Mean | 39.518 ms | 39.825 ms | 72.297 ms | 60.058 ms |
| p95 | 46.317 ms | 45.352 ms | 86.053 ms | 72.443 ms |
| p99 | 54.118 ms | 49.877 ms | 105.007 ms | 86.131 ms |
| Work intervals over 33.33 ms | 112/120 | 117/120 | 120/120 | 120/120 |

Every run admits/software-decodes all 120 frames because the workload is unpaced;
that count is not a 30 fps result. Per-frame decisions, maps, attempt/packet
sizes, kinds and software-confirmed IDs match within each pair. Easy runs use
120 attempts without retries; complex runs use 333 attempts with 213 losing
attempts/reuses. Full generated packet bytes were not retained for pairwise
comparison; exact byte/tag checks remain the separate frozen and native tests.

Keep reuse opt-in. The easy mean has a small remaining overhead and this sample
does not establish a universal speedup. Complex work is reduced, but its host
work still misses the frame budget. No isolated end-to-end CRC gain is claimed
from these pairs because both modes use table CRC. Summary, file hashes and
scope: `artifacts/v20-packet-fused-crc-timing-summary-20261104.json`.
Final executable SHA256:
`698c32a6746ca0ec4085e84947381c394d03b1b6992175cdf37c0ea35675060b`.

## Hardware timing and readiness

At the 49,152-byte cap, a frame uses 49 GF03 fragments; thirty fps means
1,470 fragments/s. Five DATA permits imply roughly 5/1470 seconds (3.40 ms)
average return turnaround for sustained full-window flow. This is a derived
budget, not measured capacity; jitter/control service can still stall it.
Any larger window needs a jointly versioned contract and real receiver storage.
The pinned GF03 model also defaults to 150 ms assembly lifetime from its first
chunk. At the cap this implies at least 2.62 Mbps payload rate before overhead
or stalls. Old JPEG 0.7 Mbps/3000 ms fixture pacing is not automatically valid
for GF03; the first-window rate/timeout must be agreed explicitly. Neither
calculation is a reason to require 30 fps before a functional fixture.

The first functional custom frame does not require 30 fps performance first.
It does require a complete functional decoder image, a matching tested lab path,
and agreed bounded ownership/safe-stop behavior. Published v23 evidence still
does not establish that readiness or current installed state. An FPGA-only
fixture can precede networking if a complete decoder supports local injection.

Use [the readiness audit](receiver-readiness-20261104.md) and
[the hardware-window request](../MOONBUB-HARDWARE-READINESS-REQUEST-20261104.md)
to obtain actual versions and a coordinated window. Existing JPEG/AV control
testing remains a separate option once its current readiness is confirmed.
No physical 30 fps result or calendar ETA is established here.

Since the audit, the user relayed a current receiver report: JPEG/AV is the
only available hardware test path; no deployable GM01 image, live custom receiver
or custom port exists yet. A v22 app-only regression is starting, with fresh
device identity evidence to follow and the FPGA unchanged. Windows will wait
for that ready record before any existing-path sender test.

The final source refresh also found MoonBub v24 at `4025d355`: it supplies
additional offline CP23/JA23/RS24 reset/profile and modeled drain/write/vblank
work. This is the next joint contract-review input, not a deployed endpoint or
an automatic wire-profile upgrade for the Windows v20 helpers.
