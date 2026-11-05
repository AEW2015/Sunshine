# CP23 exact outstanding-ACK binding checkpoint

This adds an **offline host transaction prerequisite**, not a live custom sender,
reference/HUD bank implementation, physical ownership gate or deployed protocol.
The selected first-fixture profile remains CP23/HC22/HD22; CP25 is not enabled.

## Contract and implementation

The pinned MoonBub source at
`4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`,
`experiments/python-game-hd22-joint-study/model.py`, constructs the expected
JA23 from the exact CP23 pair and both component acknowledgements. Its joint
sender accepts only the exact outstanding whole-pair ACK. Existing native
`composed_wire.h` validates JA23 syntax and cross-component identities but
intentionally does not establish that transaction binding.

`native/composed_transaction.h` now provides:

- `expected_ack`: strict CP23 framing and fixed 720×480 identity checks, followed
  by exact AF03/HA22/JA23 expectations, packet CRC, component/pair digests,
  destination bank and declared publication tags. Declared tags are expectations,
  not independently reconstructed pixels.
- `PendingPair`: one fixed nonzero epoch and at most one copied immutable
  outstanding CP23. Retries return the retained exact bytes. Caller mutations
  and a second submission cannot replace them while an outcome is unresolved.
- ACK acceptance checks complete grammar and exact bytes. Invalid, stale,
  cross-transaction or merely syntax-valid altered replies leave pending bytes
  and the last matched frame unchanged. Successful acceptance retires only
  these private retry bytes and records the acknowledged frame.
- Frame identities advance without wrapping; reserved epoch/frame sentinels and
  reuse of a matched frame are rejected. There is no cancellation, reset,
  timeout-to-release or inferred-drain shortcut.

This helper does not validate predictor banks, decode HD22/HC22 content,
publish a reference, prove memory/transport drain or release physical owners.
Those separate gates remain required before a live integration can use it.
A new helper instance is not permission to reset a live peer.

## Validation

Seven native regressions cover the independent frozen first-frame JA23,
caller-storage mutations, unresolved second submissions, epoch/canvas/cap
bounds, all ACK truncations and single-bit corruption positions, trailing bytes,
ten CRC-repaired syntax-valid wrong replies, stale ACK retention, ordinary and
promoted P reply fields, and the last legal nonwrapping frame identity.

The first-frame bytes remain the checked-in source-model fixtures:

- CP23 SHA-256:
  `a44fcd4a62027dc9c609c4b64a68145ee9f915880a7ec312ade811525eceb24b`.
- JA23 SHA-256:
  `d9372f51eb797f5c369d359ca700c6ae36c6a7a499bf600ef78018696f5fa530`.

The Windows MSYS2/UCRT64 `test_sunshine` target rebuilt successfully. All
**128 GameBub tests from 17 suites passed**, including the seven new transaction
regressions, in 3.273 seconds. The executable ran from an owned artifact working
directory with an isolated `GCOV_PREFIX`, preserving existing root test logs
and previous profiling data. The original Sunshine service was not touched.

The independent post-format functional coverage probe matched the frozen ACK
and exercised both publication-destination branches: **59/59 executable header
lines hit**, 100% branches executed, 55.41% of branch outcomes taken. That probe
does not establish full branch coverage, performance or hardware correctness.
After final source formatting, the affected native translation unit was rebuilt
and all seven transaction regressions passed again in 18 ms. Its synchronized
native-test profile hits **62/62 executable header lines**, 94.25% branches
executed and 54.02% of branch outcomes taken. No newer-source warning remains.
The differing probe/unit line counts reflect their compilation/optimization
contexts. Full branch coverage is not claimed.

`uv sync --locked` passed. The required `uv run --locked lb-update-clang-format`
helper was invoked from the repository root, but recursively entered ignored
artifact virtual environments and spent minutes formatting generated
`dxcam/processor/_numpy_kernels.c`. Only that owned invocation/process chain
was stopped. The two changed native files were then formatted directly with
the same `.venv/Scripts/clang-format.exe`; no unrelated tracked native content
changes were retained. Whitespace checks pass for the changed files.

Local functional coverage source/logs and generated reports are retained under
`tools/gamebub/artifacts/cp23-outstanding-20261105/` and
`cmake-build-gamebub-transaction-probe/`.
The native suite output is `native-test-output.txt`, XML `native-results.xml`.
The final seven-case run is `transaction-final-output.txt` and
`transaction-final-results.xml`; synchronized actual-test coverage is in
`unit-final-gcov-summary.txt` plus compressed gcov JSON and profiles in
`gtest-gcov-final/`. Earlier diagnostic coverage with stale comment line notes
is retained separately and is not the final coverage oracle.

## Remaining implementation gates

| Component | Existing implementation | Still required |
|---|---|---|
| AR03/GM01/CP02 | Native encode, decode, per-frame candidate policy and software reference evolution | Sustained measured integration and full host ownership coupling |
| HD22 | Exact private RAW/COPY/SPAN_XOR patch decoder | Stateful HC22 dispatch, bank/generation/tag ownership and joint transactions |
| CP23 independent refresh | Exact static key/full-LEGACY-HUD reconstruction and expected JA23 | Stateful predictive/HUD composition and publication/release rules |
| JA23 | Wire grammar plus this exact one-outstanding binding | Reference/HUD state transitions and real transport/frame owner gates |
| RS24 | Wire checks and bounded host phase replay | Complete receiver/live ownership, durable epoch recovery and drained reset |
| Live custom carriage | Offline transport helpers/model replay | Jointly agreed matching sender/ESP endpoint and port, then complete hardware fixture |

Next coordinate the complete shared state transcript and native reference/HUD
publication layer, preserving immutable pending state on failures. A complete
decoder image/local loader is still needed for the first physical custom fixture.
No hardware, installed Sunshine service or existing JPEG/AV behavior changed.
