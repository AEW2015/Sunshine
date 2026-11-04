# GameBub v20 first milestone

## Goal and boundary

The first milestone is offline native conformance for the custom v20 codec, delivered as a Windows `gamebub-v20-conformance` executable and fixture runner, alongside one consolidated launcher for the existing JPEG AV path. It does not add a live custom-codec endpoint or change Sunshine/Moonlight negotiation. Keep the installed JPEG service and ordinary streaming baseline intact.

Use these pinned references:

- Sunshine: `3d49c6fe87753eb5b35d693991fdff0365e4bbbf`
- MoonBub: `27a4dde6a7e2ea4fab09d892551ef542f05c8965`

Custom codec v20 is distinct from the installed JPEG FPGA image also called v20/build50. Do not route custom AR03 data under H.264 or JPEG identifiers. Preserve coded geometry 720x480 and active geometry 720x405. No milestone result supports a physical 30 fps claim or integration under H.264.

## Staged acceptance

Mark a stage complete only with saved command output, test results, and artifact paths. Until implementation supplies its actual target and script names, commands below marked **pending** are placeholders and must be replaced with verified commands; do not infer success from planned work.

- [ ] **A0 — isolate and reproduce the existing AV path.** Build and run a single finite-session launcher that owns existing JPEG video, WASAPI audio, and the selected controller profile. Keep audio-only, video-only, and combined modes. Record capture/source, encode, send, feedback, queue/stall, audio sequence/gap, and audio tail/drain evidence. Distinguish invalid FPGA snapshots from actual rejection and capture failures. Preserve the existing installed service and normal client path.
- [x] **A1 — pinned offline contract.** Copied wire/profile JSON and exported fixture hashes match the pinned references. Custom codec artifacts remain separate from JPEG build50, with720x480 coded/720x405 active geometry and the49152-byte complete AR03 cap.
- [x] **A2 — isolated native body-fixture evidence.** The native tool now validates AR03/GM01/SR01 parsing, CP02/SP01 coefficients, HP01/HR01 patches, inverse/reconstruction, canonical tags, exact RGB565 output and atomic bank/AF03 publication. All 20 frozen body cases pass. This is software fixture evidence, not a live transport or hardware result. The inverse/envelope scopes remain separate.
- [x] **A3 — offline native GM01 encoder integration.** `native/inner_encoder.h` performs RGB8-to-YUV420 conversion, Q14 forward transform, quantization and CP02 raw/Rice selection. `native/patch_encoder.h` performs actual HP01/HR01 exact RGB565 encoding. The mandatory policy uses those native callbacks, reserves full framed patch bytes before trying ordered maps, decodes fitting candidates, and tracks commit/discard, readers and exact reference ACKs. All 20 frozen cases reproduce inner bytes, selected patch bytes and complete AR03 bytes. The 10 mandatory cases verify 13 actual policy attempts, including losing builds. The 10 baseline cases retain their original partial HUD selections and do not qualify the mandatory policy. SR01 decoding exists; SR01 encoding is not implemented. There is no persistent analysis or patch cache, and every call pays its current work.
- [ ] **A4 — offline protocol ownership and failure behavior (future work).** Replay the 1,725 serialized FG19 messages, intentional loss, and wrong-kind/slot/epoch replies. Preserve the three sender transactions, two frame slots, five data tokens, one control mailbox position (six total), and three separately accounted framebuffer roles. Verify unknown outcomes retain ownership and stop pending a defined recovery; never fabricate credits or free storage before ingress/read/decode drain. FINISHED frees the request-control token only; RELEASE follows actual drain; only validated AF03 confirms decoded-reference publication.
- [ ] **A5 — close the offline milestone.** Run native Windows build, fixture verifier, regression suite, and applicable sanitizer/overflow checks. Attach results and exact artifact locations. Keep live receiver negotiation, hardware flash, installed service restart, physical decoder/display qualification, and production recovery outside this offline milestone. A3 establishes the stated offline GM01 encoder scope; A4 and full codec/state conformance remain open.

Work toward A4 now includes native GF03/TOKEN/FG19/PC18/QC18 wire codecs and
a bounded, sender-only frame-intent/reply ledger. The ledger assumes the caller
proves DATA/CANCEL/FINISH eligibility; packet-credit ownership, receiver drain,
reference publication and live recovery are not supplied by it. The wire runner
checks the pinned 1,725 control messages and corruption/truncation probes.
Native `packet_ledger.h` now adds five DATA permits, one shared query/control
mailbox, bounded queries and exact generation/route matching. The independent
`--packet-model` driver exercises lost/unknown/corrupt/stale credits and explicit
external model RELEASE events. Packet and frame ledgers cannot be copied/moved
to duplicate ownership. Full-state ownership, real network I/O and recovery
remain open because these models do not establish receiver drain or a live peer.

The reference kit's 34 tests are upstream evidence. The inverse/envelope suite
independently replayed 101,667 inverse blocks / 6,506,688 residual samples, all
20 AR03 and 20 AF03 envelope fixtures, and 80 corruption/truncation negatives.
Four Sunshine GoogleTests passed. See [the saved validation](measurements/v20-offline-foundations-20261104.md).

The current [full-body report](artifacts/v20-full-body-validated-20261104.json)
checks20 pinned cases,10368000 YUV samples,6912000 display words,211200
mandatory source HUD words and40 private-copy corruption probes. Cases are in
[v20-body-fixtures-final-20261104](artifacts/v20-body-fixtures-final-20261104),
with manifest-bound case JSON hashes and policy identities. See
[the body/policy validation](measurements/v20-native-body-candidate-20261104.md)
for decoder dialect coverage, candidate limits and current test evidence.

The body-verifier harness has14 mocked-runner unit tests with100% statement
and branch coverage. These exercise report, path, timeout, corruption callback,
and exclusive report-write behavior; native decoder evidence comes from the
saved full-body run above.

## Safe local build workflow

Use a dedicated `cmake-build-*` directory. Do not point the build at the installed service or reuse its artifacts. Native Windows commands run through MSYS2 UCRT64:

The standalone target requires the UCRT64 GCC, CMake, Ninja and OpenSSL packages.
It reuses Sunshine's pinned nlohmann-json dependency (3.11.3 fallback); the first
configuration may download it. Conformance execution itself opens no network
socket. Example setup, if these packages are not already installed:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-openssl'
```

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd /c/ai/sunshine-gamebub && cmake -S tools/gamebub/native -B cmake-build-gamebub-v20 -G Ninja && cmake --build cmake-build-gamebub-v20'
```

The executable is `cmake-build-gamebub-v20/gamebub-v20-conformance.exe`. Modes
are `--inverse INPUT EXPECTED`, `--ar03 PACKET`, `--af03 PACKET`,
`--body-case CASE.json`, `--encoder-case CASE.json`,
`--transport-contract CONTRACT.json`, `--encoder-benchmark CASE.json FRAMES`
and `--encoder-benchmark-cached CASE.json FRAMES`, plus `--packet-model ROUNDS`.
Reports distinguish
`inverse_only`, `envelope_only`, `full_body_fixture` and
`native_encoder_fixture`; never substitute an outer-envelope pass for decoding.

Export pinned fixtures into a new directory (the directory must not already exist):

Both pinned commits must be present in the respective local Git object stores.
For a fresh reference, clone without checking out source or changing this
candidate's working branch:

```powershell
git clone --no-checkout --single-branch --branch handoff/gamebub-app-codec-v20-20261103 https://github.com/AEW2015/moonbub.git tools/gamebub/artifacts/moonbub-v20-reference
git fetch --no-tags https://github.com/AEW2015/Sunshine.git handoff/gamebub-app-codec-v20-20261103
```

```powershell
py.exe -3.11 tools/gamebub/prepare_v20_fixtures.py --reference-repo tools/gamebub/artifacts/moonbub-v20-reference --sunshine-repo . --output tools/gamebub/artifacts/v20-fixtures
```

Run the manifest/hash-checked native verification harness and save its JSON report:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 tools/gamebub/verify_v20_native.py --fixtures tools/gamebub/artifacts/v20-fixtures --executable cmake-build-gamebub-v20/gamebub-v20-conformance.exe --report tools/gamebub/artifacts/v20-native-report.json'
```

The fixture export and verification commands are offline; neither starts a hardware session. The verifier uses a 60-second timeout for each child command and refuses incorrect pins, unsafe paths, changed hashes/lengths, unexpected report scope/counts, or corruption checks that do not return exactly exit code 1. It creates the report with exclusive file creation so existing evidence is not overwritten.

Export full-body inputs from the same pinned no-checkout MoonBub repository and
run the native body harness into a new report path:

```powershell
py.exe -3.11 tools/gamebub/prepare_v20_body_fixtures.py --reference-repo tools/gamebub/artifacts/moonbub-30fps-study --output tools/gamebub/artifacts/v20-body-fixtures
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 tools/gamebub/verify_v20_body.py --fixtures tools/gamebub/artifacts/v20-body-fixtures --executable cmake-build-gamebub-v20/gamebub-v20-conformance.exe --report tools/gamebub/artifacts/v20-full-body-report.json'
```

Each body fixture is an isolated packet replay with its exact original pre-bank
samples and an unset sequence baseline. Encoder `last_issued` is retained only
as provenance; it is not invented receiver telemetry. This is not a sequential
stream transcript or a production reset/rekey procedure.
The negative probes corrupt private copies and refresh their local packet hash
so they exercise decoder rejection instead of only the fixture loader.

Derive encoder cases from the validated body export, retaining the pinned
source-results hash, original RGB8, exact reference planes and frozen byte/map
oracles. The output directory must be new. The final local export is
`artifacts/v20-encoder-cases-20261104`; choose a new suffix when reproducing it
on this checkout instead of overwriting saved evidence:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 tools/gamebub/prepare_v20_encoder_cases.py --source tools/gamebub/artifacts/v20-body-fixtures-final-20261104 --output tools/gamebub/artifacts/v20-encoder-cases-20261104'
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 tools/gamebub/verify_v20_encoder.py --fixtures tools/gamebub/artifacts/v20-encoder-cases-20261104 --executable cmake-build-gamebub-v20/gamebub-v20-conformance.exe --report tools/gamebub/artifacts/v20-native-encoder-report-20261104.json'
```

The encoder harness checks all 20 cases, including 10 mandatory cases and 13
policy attempts. It validates source pins, confined paths, metadata/raw hashes,
duplicated reference/destination/map fields and byte oracles before invoking
the native tool. Native results include a separate exact full-body replay,
AF03/bank checks, and paid build/validation/discard timings. The 60-second child
timeout and exclusive report creation bound the campaign. These timings do not
measure capture, network delivery, decoder service on hardware or displayed
FPS. Original fixtures and the earlier body-only reports remain preserved.

The consolidated existing AV launcher is implemented and locally validated;
see [SESSION-LAUNCHER.md](SESSION-LAUNCHER.md) for mode flags, a no-network dry
run and current limits. The new callback worker has not yet been physically
tested. Do not run competing sessions against the same AV endpoint. Existing
controller-only usage remains in [CONTROLLER-QUICKSTART.md](CONTROLLER-QUICKSTART.md).

## Offline transport replay and generated-motion profiling

After the pinned fixture exports above, run the actual wire replay:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake-build-gamebub-v20/gamebub-v20-conformance.exe --transport-contract tools/gamebub/artifacts/v20-fixtures/contracts/wire-contract.json'
```

The contract must match SHA256
`02a1655a56ac886ffad157753f07f8214325473f26b0227e2c17a3af4f42b0b7`.
`pinned_transport_wire_only` verifies nine histories, 1,725 FG19 round trips,
3,450 CRC/truncation rejections, PC18/QC18 examples and GF03 fragmentation.
It does not prove receiver drain or full ownership from message histories.

Profile a finite continuous software sequence generated by horizontally rotating
one original source image, with real key/P/promotion/refresh and software AF03:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake-build-gamebub-v20/gamebub-v20-conformance.exe --encoder-benchmark tools/gamebub/artifacts/v20-encoder-cases-20261104/cases/mass-effect-2600-mandatory-00.json 300'
```

Use the corresponding `mass-effect-7200-mandatory-00.json` seed for a separate
complex-source run. Frame counts are strictly bounded to 1..1800. Do not run
performance comparisons alongside compilation or another benchmark. Redirect
JSON to a new artifact filename when saving evidence; shell redirection can
overwrite existing files. The benchmark starts with clean software banks rather
than concatenating the isolated fixture pre-banks. Its per-frame map attempts,
source preparation, admission, patch coding, software decode and percentiles
are local costs. Generated image rotation is not fresh moving gameplay,
desktop capture, packet pacing, RF or hardware playback. All-cap-rejected frames
remain recorded; software roundtrip speed is not encoder-only FPS.

The cached benchmark mode uses the same workload and maps, with frame-local
source-conversion/forward-transform analysis reuse between map attempts. Its
first build now captures analysis while encoding the first map, rather than
running a separate analysis pass. Every attempt still pays map-dependent
quantization, coding and reconstruction work, and fitting candidates retain
independent decoder validation. Analysis must not cross source/reference/frame
identities or become a global cache. Compare both modes on the same seed and
frame count, sequentially with builds idle; retained source/reference invariants
and golden packet bytes remain required.

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake-build-gamebub-v20/gamebub-v20-conformance.exe --encoder-benchmark-cached tools/gamebub/artifacts/v20-encoder-cases-20261104/cases/mass-effect-7200-mandatory-00.json 600'
```

Exercise finite, independent sender bookkeeping fault cases:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake-build-gamebub-v20/gamebub-v20-conformance.exe --packet-model 10000'
```

The rounds argument is strictly 1..100000. This is a deterministic state model,
not a duration soak or UDP loopback. It uses synthetic packet payloads and
explicit external model RELEASE events; resetting objects between independent
cases is not production peer recovery. Unknown outcomes remain owned and stop.
Use [the readiness audit](measurements/receiver-readiness-20261104.md) and
[the first-window request](MOONBUB-HARDWARE-READINESS-REQUEST-20261104.md) to
coordinate a physical test. A first functional frame can precede 30 fps timing
qualification, but matching complete implementations and a safe-stop contract
must exist for the selected injection/network path.

Set `GAMEBUB_V20_EXE`, `GAMEBUB_V20_CONTRACT` and
`GAMEBUB_V20_ENCODER_FIXTURES` to enable the real transport/benchmark Python CLI
regressions. Existing body/encoder fixture environment variables still apply.

## Promotion gate

Offline conformance does not qualify a live stream. Before any custom endpoint integration, separately negotiate receiver capabilities/profile and reset/rekey behavior, then demonstrate bounded ownership under loss and recovery. Before claiming performance, measure native capture/scaling, patch preparation, every losing build, encode/admission, packet pacing, queue age, reference promotion, and receiver service. Existing prototype rate projections are not Wi-Fi measurements; current service estimates miss 33.33 ms, and no physical 30 fps result is established. Preserve the 720x480 / 720x405 geometry through those evaluations.
