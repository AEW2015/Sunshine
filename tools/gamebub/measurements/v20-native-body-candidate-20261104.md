# Native full-body decoder and mandatory candidate policy

Implemented on 2026-11-04 in the existing separate Sunshine candidate. Work was
split across decoder, candidate policy, fixture/test and independent review
agents; Luna handled fixture export and Python harness tests. No hardware
stream, capture, driver install, board flash, installed service restart, branch
switch, commit or push was performed. Existing local changes were preserved.

## Native decoder and exact software fixtures

`native/body_decoder.h` implements bounded AR03/GM01/SR01 parsing, CP02 raw/Rice
and SP01 split coefficients, Q14 inverse/reconstruction, HP01/HR01 display
patches, canonical SHA256 reference tags, RGB565 rendering and exact AF03 ACKs.
Length, CRC, identity, geometry, plane, patch and tag validation happens before
state/output publication. Display overlays remain outside predictor banks.

`native/body_case.h` and CLI `--body-case CASE.json` replay an isolated case
with hash-bound raw source/expected arrays and exact precondition banks. The
normalized case JSON is an offline test format, not a new runtime packet.
`prepare_v20_body_fixtures.py` exports the20 source cases without checking out
the reference repository. `verify_v20_body.py` checks source provenance, case
JSON hashes, policy/packet/ACK identity and native output scope/counts, then
executes private-copy corruption probes. Existing reports are never overwritten.

Pinned MoonBub source is `27a4dde6a7e2ea4fab09d892551ef542f05c8965`. The current
full-body report `artifacts/v20-full-body-validated-20261104.json` verifies:

| Result | Count |
| --- | ---: |
| Isolated complete packet cases |20|
| Exact reconstructed YUV samples |10368000|
| Exact RGB565 display words |6912000|
| Mandatory original-source HUD words |211200|
| Exact AF03/post-bank comparisons |20 each|
| Hash-resealed private CRC/truncation negatives |40rejected|

All 20 retained real-source packets use GM01. SR01/SP01 and every HP01 palette
width are covered by synthetic native controls, not claimed as real-source
SR01 throughput. Cases include keys, ordinary P frames, promotion and refresh.
The five sampled IDs per case are not a self-contained streamed sequence.
Their sequence baseline is intentionally unset; encoder last-issued state is
provenance, not invented receiver telemetry. Expected post-bank samples are
the frozen decoded planes for a newly published bank and the unchanged exact
pre-bank planes otherwise; the upstream post-bank record supplies identities.

## Candidate admission and ownership

`native/candidate.h` implements the fixed 720x480 mandatory profile. It decodes
and validates every requested HP01/HR01 patch against the current immutable
source, reserves full length-prefixed patch bytes, and tries only the four
declared maps. Every fitting assembled AR03 packet is fully decoded before
admission. Four rejected maps reject the whole frame without consuming its ID.
Attempt bytes, build/validation/discard clocks and patch work are reported.
Unit-test clocks are not an encoding benchmark.

The policy retains capture/reference ownership through explicit commit/discard,
guards stale/foreign handles and callback reentrancy, preserves external reader
baselines, bounds active/external readers to three, and stages reference output
until exact AF03 epoch/frame/body/bank/id/tag matching succeeds. At most three
committed transactions can remain pending. Unknown outcomes do not fabricate
capacity or publish a reference. Production reset/rekey remains unimplemented.

Independent review found two issues that were fixed before this handoff:
copy/move operations could replace/move a source through a mutable shared alias,
and external leases lacked the frozen three-reader bound. Tests now cover both.
Source geometry is checked before copying. The RGB8 constructor owns the exact
original 720x480x3 bytes and derives RGB565 words; later mutation of the capture
input cannot change either representation. The RGB565-only constructor is
explicit patch-policy fixture mode and exposes no fabricated original RGB8.

**Actual native base and patch encoding are not implemented.** `InnerBuilder`
and `PatchBuilder` remain explicit callbacks. Policy tests supply valid synthetic
GM01 and actual HP01 bytes, then use the real decoder; these prove admission and
lifetime behavior, not real-game encoding, compression quality or encode FPS.
No FG19/GF03/PC18 live transport or Sunshine negotiation was added.

## Validation and tooling

- 30 native GoogleTests passed: 4 inverse/envelope, 7 body and 19 candidate tests.
  Tests use the shared `tests_common.h` and repository include conventions.
- 342 Python tests passed in 19.119 seconds, with 5 existing integration skips. Native
  CLI tests were enabled against the actual built executable and full fixtures.
- The new exporter/verifier have 100% statement/branch coverage: 269 statements,
  114 branches. Tests cover metadata, path, hash, oracle, timeout and report failures.
- Independent tiny packet cases exercise raw CP02 and HP01 palette 1/2/4/8-bit
  modes through the real CLI; native controls also cover 256 palette entries,
  nonzero padding, unused colors, extra bytes, nested repaired-CRC negatives,
  every truncated prefix, patch overlap and invalid predictor storage.
- Merged native gcov lines: inverse 61/61, CLI 57/57, body decoder 371/373,
  fixture reader 138/139, candidate 269/270. Remaining locations are reported in
  `artifacts/v20-body-candidate-coverage/summary.json`; mixed O0/O3 attribution
  and allocation-unwind paths prevent a blanket 100% native coverage claim.
- Legacy replay still passes 101667 inverse blocks and all 20 AR03/20 AF03 outer
  envelopes plus 80 rejection probes after the body-mode addition.
- Release and instrumented UCRT64 builds pass. CMake lint and Ruff pass.
  Changed native files pass clang-format. The required root formatter completed
  with a process-local walk filter that excludes retained evidence/virtualenvs;
  no unrelated tracked native formatting changes remained.

Toolchain observed: GCC 16.2.0-6, CMake 4.4.5-1, Ninja 1.13.2-1, OpenSSL 3.6.5-1.
The standalone CMake target reuses Sunshine's nlohmann-json 3.11.3 fallback.
MinGW/OpenSSL are statically linked; imports are Windows OS/UCRT DLLs. No
packages were installed for this work. UBSan was not available in this UCRT64
toolchain; upstream Linux sanitizer evidence is not substituted for Windows.

## Evidence and reproduction

Build/setup commands are in [V20-DEVELOPMENT.md](../V20-DEVELOPMENT.md).
Final fixture export is `artifacts/v20-body-fixtures-final-20261104/` with
per-case JSON hashes and original pinned source-results. Reports/logs:

- `artifacts/v20-full-body-validated-20261104.json` (Release decoder).
- `artifacts/v20-full-body-coverage-20261104.json` (instrumented replay).
- `artifacts/v20-body-candidate-complete-gtest-20261104.txt` and XML.
- `artifacts/v20-body-full-python-final-tests-20261104.txt`.
- `artifacts/v20-body-python-coverage-20261104.txt` and native gcov directory.
- `artifacts/v20-inverse-envelope-regression-20261104.json`.
- `artifacts/v20-body-format-20261104.log` and source-provenance JSON.

## Next development boundary

Implement real native RGB8→YUV analysis/forward transform, quantization, entropy
and patch encoders behind the policy callbacks, then compare complete outputs
and paid work against pinned source cases. Keep actual capture precision,
candidate generation/lease semantics, full 49152-byte admission and all mandatory
HUD words. Next implement separately negotiated grants/packet credits and
reset/rekey/reconnect handling before any live custom endpoint. None of this
software evidence establishes hardware 30 fps, latency, Wi-Fi capacity or audio
playback. The working JPEG/AV path and installed Sunshine remain unchanged.
