# Windows candidate validation — 2026-11-05

The candidate was built and tested separately in `C:/ai/sunshine-gamebub`.
The original checkout and installed working Sunshine service were preserved.
The [environment record](windows-test-environment-20261105.json) identifies the
queried Windows build, CPU, UCRT64 compiler and sender libraries.
The [machine-readable validation record](windows-validation-20261105.json)
preserves parsed test counts, result-file hashes and measured module coverage.

## Regression and conformance

- Full Python suite: **548 tests passed, zero skips**, using the
  GameBub Python 3.11 venv under the required MSYS2/UCRT64 shell. Available
  native CLI/body/encoder/wire/reset/HD22 fixture integrations were enabled.
  The final pass also enabled all five optional pinned-receiver integrations,
  including the Rust parser, and completed in 49.357 seconds. The earlier
  543-pass/five-skip cohort remains retained separately.
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
- Final trace-enabled 30-minute AV repeat, with the sole audio gap matched to
  its recorded eviction: [repeat report](localhost-av-trace-native-30fps-30m-20261105.md).
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

## Reproduce the final cohort

Use the isolated build/setup instructions in [the laboratory README](../README.md)
and [native development guide](../V20-DEVELOPMENT.md). Recreate the pinned fixture
exports described there; ignored local artifacts are not shipped by Git. Paths
below identify this machine's validated exports and must be changed if yours
differ. The reference clone must contain revision
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52`; tests read and hash-check that revision
without changing its checkout. Rust is required for its parser integration.

From the candidate repository root, these commands select the full optional
fixture set and the scoped native test cohort:

```powershell
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'MOONBUB_REFERENCE=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/moonbub-30fps-study \
GAMEBUB_V20_EXE=C:/ai/sunshine-gamebub/cmake-build-gamebub-v20/gamebub-v20-conformance.exe \
GAMEBUB_V20_CONTRACT=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/overnight-v20-fixtures-20261105/contracts/wire-contract.json \
GAMEBUB_V20_BODY_FIXTURES=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/v20-body-fixtures-final-20261104 \
GAMEBUB_V20_ENCODER_FIXTURES=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/v20-encoder-cases-20261104 \
GAMEBUB_V24_RESULTS=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/v24-recovery-results-4025d355.json \
GAMEBUB_HD22_FIXTURES=C:/ai/sunshine-gamebub/tools/gamebub/artifacts/hd22-fixtures-20261104 \
tools/gamebub/.venv/Scripts/python.exe -m unittest discover -s tools/gamebub -p "test_*.py"'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub/tests/test_sunshine.exe --gtest_filter="Gamebub*"'
```

Do not rebuild a native executable while a test process is using it. The final
run used the immutable snapshot identified above, with equivalent fixture
environment options set only in its child process. Its logs are
`all-reference-tests.txt`, `.coverage-all-reference` and
`all-reference-coverage.json`. The coverage JSON selects repository GameBub Python
files: the pinned receiver also executes under a virtual source filename, whose
source is not present at that path in this checkout. No production statement or
branch exclusions were added.
