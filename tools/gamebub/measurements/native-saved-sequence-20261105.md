# Native saved-frame sequence profiling checkpoint

The native conformance tool now accepts a finite, hash-bound sequence of saved
720×480 RGB8 frames. This replaces generated rotation with real moving footage
for a component benchmark; it does not add a live custom sender, implement the
full CP23/HC22/HD22 state machine, contact the handheld or establish playback FPS.
Installed Sunshine and the existing JPEG/AV sender default were unchanged.

## Implemented interfaces

- `prepare_encoder_sequence.py` exports a fresh directory and versioned
  `gamebub-v20-rgb8-sequence-v1` manifest. Each frame has an exact byte count,
  SHA-256, dtype/shape, source identity and original PTS. The clip is hashed
  before decode; offset and selection/canvas policies are explicit. No loop.
- **Resampled mode** retains the existing `clip_frames` behavior but rejects
  repeated selected PTS rather than claiming duplicate samples are distinct.
- **Native-decoded mode** decodes each original frame once, retains decoded
  frame IDs and original/relative PTS, and declares the stream's nominal rate
  as a rational. `sample_fps` and sampling-grid index are null; no artificial
  30 fps timeline is assigned. Source PTS must increase strictly.
- `native/encoder_sequence.h` bounds manifests to 1 MiB and 1..1,800 frames,
  validates source mode/timestamps and confines file paths below the manifest
  directory. Only one requested source frame is loaded/hashed at a time.
  Existing immutable source snapshots, analysis and codec banks allocate their
  own additional storage; the 1,036,800-byte loader bound is not a process peak.
- `--encoder-sequence MANIFEST FRAMES` and `--encoder-sequence-cached ...` run
  the existing native mandatory-patch AR03 encoder/policy and software decoder,
  including all map attempts and discarded work. They load no unrequested
  pixel data, never implicitly loop and reject a request exceeding the manifest.
- Accepted packets get a paid SHA-256 phase, enabling exact selected-packet
  identity checks between variants. Rejected admissions record a null packet
  hash and zero hash work, not an invented output. Old generated-workload schema,
  wrapper/defaults and golden outputs are preserved; output hashing defaults off.

File reads, input hashes, immutable-source preparation, admission/all candidate
work, software decode and output hash costs are separate. File/hash costs are
also included in source preparation and overall measured wall time, so do not
sum those nested measurements twice. Manifest validation and complete sequence
wall time are reported separately. Clip decode/scaling happened during export,
not inside the native benchmark; those are not live-capture measurements.

## Real-source export

Source: [saved Xonotic gameplay](xonotic-source.json), 48,552,136 bytes, SHA-256
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
Offset zero; 60 unique native decoded frames, IDs 0–59, PTS **7,000–1,974,000 us**,
span 1.967 seconds. The declared stream rate is 30/1; that does not establish
native encoder throughput or physical presentation. Original proportions are
preserved by the existing canvas transform (691×405 active for this source).

The first attempted 30 fps resampled export safely rejected repeated PTS and
published no manifest. Its selected PTS began 7, 40, 40, 107, 140, 140 ms. This
comes from the old resampler and quantized source timestamps; the sender was not
silently modified. The subsequent **explicit native-decoded** mode produced the
60 unique inputs without resampling or repetition.

Dataset: `artifacts/encoder-sequence-20261105/xonotic-native-60/manifest.json`,
62,208,000 bytes of RGB files. Manifest SHA-256:
`f27c9b4da3fd2d4999d17ac08768021a4e09711c4dfb73b60c67c1fcba16d1d9`.
The native loader rechecks each selected RGB hash but does not reopen/reverify
the original compressed clip; its report explicitly distinguishes those facts.

## Initial paired component measurements

Baseline then cached variant ran sequentially without another controlled
benchmark/build overlapping. This is one short pair, not a broad performance
qualification. Source I/O was much colder in baseline, so whole-wall differences
are not an isolated measure of analysis reuse.

| Component workload, 60 source frames | Baseline | Frame-local analysis reuse |
|---|---:|---:|
| Accepted / software decoded | 20 | 20 |
| Rejected by complete-cap admission | 40 | 40 |
| Total attempted maps / losing attempts | 210 / 190 | 210 / 190 |
| Selected complete bytes | 926,054 | 926,054 |
| Admission p50 | 54.914 ms | 39.040 ms |
| Admission p95 | 62.660 ms | 46.540 ms |
| Accepted software-decode p50 | 11.914 ms | 12.227 ms |
| File-read p50 | 6.758 ms | 0.586 ms |
| Input-hash p50 | 1.967 ms | 2.041 ms |
| Loop wall, all requested work | 4.089 s | 2.836 s |
| Complete sequence wall including metadata | 4.141 s | 2.884 s |
| Analysis builds / reuses | 0 / 0 | 60 / 150 |

**All 20 selected AR03 packet SHA-256 values match exactly across variants**;
all 60 admission decisions match. The other 40 packet hashes are explicitly
null in both reports. Cached coefficients peak at 2,073,600 declared bytes;
this is not a measured process-memory peak. No CPU or live capture cost was
measured in these native reports.

These are the older **AR03 mandatory-exact-patch component profile** under its
49,152-byte complete cap, not full stateful CP23/HC22/HD22 results. Do not
unilaterally raise that cap or infer the future joint codec's acceptance from
this narrower profile. Q25 applies to the separate JPEG experiments; this
native profile uses the fixed ROI/background maps, not JPEG quality units.

The pair exposes two actual limits for this component workload: many frames do
not fit the cap, and even cached median admission exceeds the 33.333 ms budget
before decode/source overhead. It does not demonstrate 30 fps, a quality floor,
end-to-end latency, live reference publication or hardware playback. Deeper
optimization or joint-codec integration must retain the rejection costs and
exactness checks rather than count only the winning frames.

## Validation

- All **154 GameBub native tests / 19 suites passed** (4.008 s), including
  seven transaction-binding, twelve saved-sequence and fourteen ownership tests.
- **13 exporter tests** and **five real native sequence CLI tests** passed.
  They cover both source modes, duplicate PTS/IDs, native nominal-rate metadata,
  nonexistent/oversized/truncated/corrupt files, traversal, malformed descriptors,
  finite EOF, invalid counts and failure/acceptance hash accounting.
- The original **20 native encoder goldens**, including ten mandatory cases
  and all thirteen mandatory policy attempts, remain exact against the rebuilt
  CLI. Executable SHA-256 for that verification:
  `d02b96a86fc24018c03fff1518e0094042fa19aaa5768b31fdad638340129416`.
- Prior sequence coverage before the final source-mode/hash extension hit every
  executable line. Final coverage must be refreshed for the new branches before
  claiming the final source's complete line coverage; full branch coverage is
  not claimed. Ruff/format and native direct-format checks pass.

Native builds/tests used MSYS2 UCRT64 and separate `cmake-build-*` directories.
The required whole-tree format helper had already been invoked for this phase
and stopped after recursively entering ignored generated virtual-environment C;
only modified native files were directly formatted afterward, as coordinated.
No unrelated tracked formatting changes were retained.

## Reproduction

Use the existing GameBub lab `.venv` and source clip setup in
[xonotic-loopback.md](xonotic-loopback.md). Export into a fresh destination:

```powershell
& tools/gamebub/.venv/Scripts/python.exe tools/gamebub/prepare_encoder_sequence.py --clip tools/gamebub/artifacts/media/Xonotic-0-8-2-gameplay.webm --output-dir tools/gamebub/artifacts/NEW-SEQUENCE --frames 60 --selection native-decoded --offset-us 0 --expected-sha256 36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub-v20/gamebub-v20-conformance.exe --encoder-sequence tools/gamebub/artifacts/NEW-SEQUENCE/manifest.json 60'
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub-v20/gamebub-v20-conformance.exe --encoder-sequence-cached tools/gamebub/artifacts/NEW-SEQUENCE/manifest.json 60'
```

Build the isolated CLI with the existing [native build instructions](../V20-DEVELOPMENT.md).
Do not overlap benchmarks. Source decode/export and native replay are separate
cost domains and must stay labeled. More varied/longer clips and the full joint
profile still need independent tests after this short component checkpoint.

Full local evidence is under `artifacts/encoder-sequence-20261105/`: exporter
summary, native manifest/RGBs, paired complete JSON reports,
`native-moving-summary.json`, `encoder-goldens-report.json`, native test logs/XML,
coverage profiles and metadata. The public summary contains no RGB payloads.
