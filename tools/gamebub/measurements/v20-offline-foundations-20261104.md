# V20 offline foundations and consolidated JPEG/AV launcher

Implemented2026-11-04 in the separate `C:\ai\sunshine-gamebub` candidate,
preserving local work. Multiple agents handled the launcher, fixture exporter,
verification harness and documentation in parallel; Luna handled the fixture
and documentation tasks. No branch switch, commit/push, hardware streaming,
device capture, driver install, FPGA flash or service restart was performed.
Installed SunshineService remains running as PID7420.

## Delivered components

- `native/v20.h`, `native/conformance.cpp`: exact bounded inverse arithmetic,
  ZERO/DC and sparse general cases, plus little-endian AR03/AF03 envelope
  size/version/flags/length/trailer CRC checks. Native packet success explicitly
  reports `envelope_only`; it is not full decoder conformance.
- `build_v20_conformance.sh`, standalone CMake target
  `cmake-build-gamebub-v20/gamebub-v20-conformance.exe`. UCRT64 GCC16.2.0,
  C++20, warnings as errors, static MinGW runtime; no Sunshine install step.
- `prepare_v20_fixtures.py`: hash-checked pinned Git export without checkout
  or fetch; bounded decompression, canonical paths, fixed packet bounds and
  manifest-last completion. New output directories only. A failed export is
  retained without its completion manifest, never recursively removed.
- `verify_v20_native.py`: validates pins, schema, sizes and SHA256 before
  executing the native tool with finite subprocess timeouts. Reports are
  exclusive-create. Sources pinned to MoonBub27a4dde6a7e2ea4fab09d892551ef542f05c8965
  and Sunshine3d49c6fe87753eb5b35d693991fdff0365e4bbbf.
- `session_launcher.py`, `live_session.py`, `live_audio.py`,
  `start_gamebub_session.ps1`: explicit finite video/audio/input modes, shared
  AV session, existing profiles, product IMA and QPC timing. Callback capture
  has bounded PCM/encoded queues, source inactivity/resume events, visible
  overflow, stale dropping, per-sequence sends, tail accounting and bounded
  worker join. Input ordering/500ms neutral-release lease remains independent.
  Route preflight, owned-video health/cleanup and a no-network dry run are
  included. No silent switch to keyboard/mouse injection or custom v20 packets.

## Verified results

| Check | Result |
| --- | --- |
| Windows inverse golden replay |101667 blocks,6506688 residual samples exact|
| Frozen outer packet envelopes |20AR03 and20AF03 accepted|
| CRC/truncation negative packet replay |80 rejected with expected exit category|
| New Sunshine GoogleTests |4/4 passed via tests/tests_common.h|
| Native CLI file/error regression |3/3 passed against the actual Windows executable|
| Entire Python lab suite |310 tests,5 existing integration skips; passed17.736s|
| Focused new Python modules |50 tests passed;738 statements/254 branches,100%|
| Real localhost UDP integration |Audio-on and audio-off finite sessions pass; handshake, CRC, product-decoded synthetic audio, profile mapping and neutral release|
| PowerShell launcher dry run |600s15fps/q25/2Mbps/gain0.75/WoW manifest/command generated; no sockets/devices opened|
| Lint/build |Ruff passes, CMake lint passes, standalone Release and coverage builds pass|

Native gcov records100% executable-line coverage in the CLI and inverse/envelope
header. Nonthrow branch coverage is89/92 in the CLI and98/100 in the header;
remaining paths include file-I/O fault and compiler-generated call edges.
These are reported rather than treated as tested. UBSan was not run on Windows:
this UCRT64 compiler cannot resolve `libubsan.a`. The published Linux sanitizer
result is not substituted for Windows evidence. Legal signed extremes and
invalid-domain nonmutation are covered by frozen arrays and GoogleTests.

The required root `uv sync --locked` succeeded. The repository-wide
`lb-update-clang-format` command was started, but its traversal entered ignored
artifact virtual environments; its owned worker was stopped. Changed native
files were then formatted directly with the repository clang-format. No
unrelated tracked native formatting changes remained. Root cmake-lint failed
under managed Python3.15 due its re.Scanner incompatibility; invoking the same
installed cmakelang with Python3.11 passed after fixing the new file's lint.

## Evidence and reproduction

Use [V20-DEVELOPMENT.md](../V20-DEVELOPMENT.md) and
[SESSION-LAUNCHER.md](../SESSION-LAUNCHER.md). Native builds/tests use:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'bash tools/gamebub/build_v20_conformance.sh'
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub --target test_sunshine -j4 && ./cmake-build-gamebub/tests/test_sunshine.exe --gtest_filter=GamebubV20.*'
```

The second command assumes the existing Sunshine test build was configured.
Native fixture arrays were exported to `C:\ai\v20-fixtures-check3`; regenerate
them from pinned Git objects rather than relying on that machine-specific path.
Saved under `tools/gamebub/artifacts/`:

- `v20-native-conformance-final-20261104.json` and the earlier first replay.
- `v20-native-coverage-replay-20261104.json`, `native-v20-coverage/` gcov data.
- `v20-milestone-full-tests-20261104.txt`, focused tests and Python coverage.
- `v20-milestone-launcher-dry-run-20261104/manifest.json`.
- Launcher agent test/coverage files and local fake-device/UDP tests in source.

## Open gates and next implementation

The full custom encoder, entropy/HUD reconstruction, canonical reference tags,
FG19/PC18 lifecycle, negotiation/reset/recovery and live custom endpoint are
not implemented by this increment. The20 packet fixtures here exercise outer
framing only; their required predictor-bank, decoded image and HUD oracles are
not claimed as replayed. This is not a physical30fps result.

Next, validate the new WASAPI callback worker with a short audio-only hardware
session, including deliberate source inactivity/resume and shutdown, then a
matched5fps combined control run. Preserve firmware/settings and collect receiver
audio admission and snapshot validity separately. In the custom-codec track,
implement native full-body/state conformance and mandatory-HUD candidate
admission before negotiated live transport. Keep720x480 coded/720x405 active
geometry and the working JPEG path; the49152-byte custom cap does not replace
the JPEG cap. Never label custom AR03 as H.264 or JPEG.
