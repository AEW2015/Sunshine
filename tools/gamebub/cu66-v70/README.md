# CU66 v70 Windows development branch

Branch: `gamebub/cu66-v70-windows-20261105`.
Worktree on this machine: `C:/ai/sunshine-cu66-v70`.
Forked from legacy Windows checkpoint `fd0376fd152c07f563a398c89395498d39079a28`.

This is the separate future CU66 backend. The working MSV1/JPEG sender stays on
`gamebub/windows-jpeg-retry-20261103`, with frozen candidate tag
`gamebub-msv1-25fps-candidate-20261105`. Neither branch installs or restarts the
working Sunshine service as part of development.

## First completed milestone

The unmodified MoonBub native reference from commit
`fcc02c58d46f96a26790ce02826a0bf937c2478b` builds and passes its Release
qualification under Windows MSYS2/UCRT64 GNU C++ 16.2.0:

- 457 frames across four causal histories: 20 keys and 437 predicted frames,
  with exact canonical YUV, HUD and RGB565 golden comparisons.
- 28 malformed/unsupported packet cases with unchanged accepted state,
  key recovery and previously returned object ownership checks.
- 1,371 entropy planes / 3,586,687 exact coefficient tiles.
- Directed entropy: six valid and 25 rejected cases; 32 HUD cases.
- Seed 6903: 512 mutations, 507 rejected; five accepted mutations preserve
  bound outputs. A valid mutation is not automatically an error.

All 3,348 exported source/fixture files were rehashed afterward and remain
unchanged. See [the Windows qualification record](../measurements/cu66-v70-windows-reference-20261105.json)
for source/archive, executable and log hashes and exact commands. These are
upstream native qualification programs, not new Sunshine GoogleTests.
The old 548-Python/173-native test record is a separate legacy cohort.

There is no CU66 encoder or live network sender in this branch yet. The
reference capability is epoch 25, 720x480 YUV420, CU66/GU66 profile
`16c998527276c7c5249e96c75931494b`, AB38 dispatch 5/6, zero base motion and
the pinned HUD subset. It is not the old CP23 profile or a full-format claim.

## Reproduce the offline qualification

Use a local MoonBub clone containing the exact pinned commit. Export
`experiments/cu66-native-v69` with Git archive into a fresh ignored artifact
directory; avoid a PowerShell text pipeline for binary tar data:

```powershell
$ReferenceRepo = '<local MoonBub clone>'
$ReferenceRoot = 'tools/gamebub/artifacts/cu66-v70-reference'
New-Item -ItemType Directory -Path $ReferenceRoot
git -C $ReferenceRepo archive --format=tar --output "$((Get-Location).Path)/$ReferenceRoot/reference.tar" fcc02c58d46f96a26790ce02826a0bf937c2478b experiments/cu66-native-v69
tar -xf "$ReferenceRoot/reference.tar" -C $ReferenceRoot
```

Then configure and build the frozen upstream project with the required shell.
The examples use a fresh build directory; the retained run used
`cmake-build-cu66-reference` with its original exported source path. Do not
reuse that CMake cache with a different source directory. Use matching paths
if reproducing the retained run instead of the fresh export above:

```powershell
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake -S tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69 -B cmake-build-cu66-reference-repro -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build cmake-build-cu66-reference-repro --parallel 2'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-cu66-reference-repro/test_native.exe tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-cu66-reference-repro/ab38_check.exe tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69/planes.tsv'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-cu66-reference-repro/test_entropy_directed.exe tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69/entropy-directed.tsv'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-cu66-reference-repro/test_hud_directed.exe tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69/hud-directed.tsv'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-cu66-reference-repro/fuzz_native.exe tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-cu66-reference-repro/native_decoder.exe tools/gamebub/artifacts/cu66-v70-reference/experiments/cu66-native-v69/index.tsv 1'
```

Use forward slashes in native fixture arguments: the unmodified reference CLI
derives index-relative paths with `/`. Fresh exports require no Python fixture
regeneration or board access. The native decoder itself uses only the C++17
standard library. Preserve the frozen source and its provenance rather than
formatting or patching this external qualification snapshot.

Root Python tooling was initialized with `uv sync --locked` after initializing
the pinned `third-party/lizardbyte-common`, `third-party/glad` and Flatpak
builder-tools submodules. This does not replace the legacy lab Python venv.
No production native source or dependency declarations were changed here.

## Next commits

1. Add a bounded, explicitly named CU66 adapter and Sunshine regression tests
   against the pinned oracle, retaining exact capability rejection and state
   ownership. Follow `tests_common.h`, doxygen and changed-source coverage rules.
2. Inventory/qualify an encoder restricted to the same capability from original
   RGB captures. Do not rename CP23 bytes or borrow its canonical tag domain.
3. Agree the actual receiver carriage, session/generation mapping, bounds,
   credits, irreversible commit ACK, presentation/release, reset and STOP
   semantics. HC70 internal HUD control is not an assigned network endpoint.
4. Add stateful local sender/reassembly/recovery tests. Preserve accepted
   reference dependencies when replacing stale source work.
5. Start hardware traffic only after compatible deployed firmware/RTL and fresh
   endpoint readiness are independently established. Follow
   [the coordinated v70 gates](../CU66-V70-AUDIT-AND-NEXT-PLAN-20261105.md).

This first Windows result has no ASAN/UBSAN, target-fit, ESP32, RF, FPGA-display
or physical 30 fps qualification. Native receive-call timings are smoke-run
telemetry, not an isolated benchmark or end-to-end playback measurement.
