# Windows candidate validation — 2026-11-05

The candidate was built and tested separately in `C:/ai/sunshine-gamebub`.
The original checkout and installed working Sunshine service were preserved.
The [environment record](windows-test-environment-20261105.json) identifies the
queried Windows build, CPU, UCRT64 compiler and sender libraries.

## Regression and conformance

- Full Python suite: **548 tests run: 543 passed, five optional skips**, using the
  GameBub Python 3.11 venv under the required MSYS2/UCRT64 shell. Available
  native CLI/body/encoder/wire/reset/HD22 fixture integrations were enabled.
- Native: **173 GameBub tests across 24 suites passed**. Test headers use the
  shared `tests_common.h` support. Original twenty AR03 golden cases and all
  sixteen static/nonuniform CP23 instances remain exact in their stated modes.
- Optional budgeted preparation and substage profiling preserve complete
  packets, tags, ACKs, maps, candidate sizes and admission decisions. Same-process
  default/budgeted replay checked **7,200 rows** and every source retirement.
- Full Python fixture integrations used immutable native executable
  SHA256 `15a08cc10367e9f26531b8f6cf1503f97217ca3f8bf56bc9497087f8dcbf22af`,
  preventing a concurrent link from replacing an executable under test.

Focused and full coverage reports cover every statement and branch in the
waiter, timer-period helper, pipeline, launcher, capture owner/verifier, live
session, live audio, audio codec and AV session modules. The native clip reader
has 22/22 statements and 16/16 branches covered. Only bare program entrypoints
remain uncovered in the measured host/reference/sender files; they are not
reported as fully covered files. New native sequence and key-budget helpers
have 112/112 and 130/130 executable lines covered. Compiler-generated
allocation/exception branches and documented closing-brace line attribution
remain explicit limits, with no coverage exclusions added.

## Runtime checks

- Saved moving content, native source selection and concurrent input/audio:
  see the [30-minute report](localhost-av-native-30fps-30m-20261105.md).
- Trace-enabled five-minute AV and a controlled 121 ms owner stall:
  [eviction validation](audio-eviction-trace-validation-20261105.md).
- Real localhost capture owns start through actual STOP; an invalid interface
  aborts before media: [capture validation](capture-owner-validation-20261105.md).
- PowerShell wrapper dry runs verify native selection, source bind, pacing tail
  and optional fixed source-port forwarding without opening hardware sessions.

Both required `uv run --locked lb-update-clang-format` passes completed after
process-only exclusion of ignored dependency/archive trees. They checked 276,
then 277 source inputs with zero content changes; original bytes and unchanged
mtimes were preserved. Ruff and `git diff --check` passed on the candidate.

Raw command output, coverage and XML are retained under
`artifacts/overnight-complete-tests-20261105/` and the linked native study
directories. These validate software scopes. No new physical sender, receiver
flash, installed-service restart, stock-client pairing test, RF delivery,
FPGA presentation or acoustic playback qualification occurred in this phase.
