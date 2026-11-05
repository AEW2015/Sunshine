# Native independent CP23 encoder

The new offline encoder targets the selected CP23/HC22/HD22 laboratory family
at MoonBub `4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`. Its implemented subset
is an independent AR03 key plus four complete LEGACY HC22 patches, matching a
fresh pinned `JointSender`. It creates no network endpoint, does not add custom
Sunshine negotiation, and does not publish references or implement P frames/HD22.

`native/composed_encoder.h` prepares the four exact HUD patches and canonical
RGB565 HUD SHA16 once, then attempts ROI/background maps in order
`(8,16), (8,32), (16,32), (32,32)` using one frame-local transform analysis.
It selects the first complete CP23 fitting the configured cap, at most 49,152
bytes. Losing attempts remain in the paid-work report. The chosen pair includes
component hashes and CRCs and is independently decoded to construct its exact
JA23. The report includes HUD preparation, each build/framing/discard,
validation, retained-analysis cleanup and complete encoder wall time.

For an independent HUD, the pinned HD22 alternative is always RAW with 50 fixed
bytes plus two bytes per word. LEGACY always has an HP01 RAW choice with 28 fixed
bytes plus the same words, or a smaller compressed choice. Native preparation
therefore omits constructing the provably losing HD22 alternatives and emits
the same four LEGACY choices. This is a native optimization verified by exact
oracles, not an HD22 encoder implementation or a reproduction of Python CPU cost.

This is a fresh independent transaction with HC22 generation 1 and no HUD
reference. Repeated same-epoch stateful transmission is not implemented. The
codec fixture's positive epoch is separate from the current epoch 1 only
transport ownership wrapper.

The old mandatory-HUD AR03 framing costs `81 + inner + sum(patches)` bytes.
CP23 with patch-free AR03 and HC22 costs `205 + inner + sum(patches)` bytes.
The 124-byte difference matters to map/cap selection: earlier AR03 benchmarks
are component evidence and must not be reported as complete CP23 encoding.

## Frozen source checks

The dedicated native test regenerates exact original RGB8 and compares all 12
published static output instances, including exact 5,166-byte CP23 packets and
134-byte JA23 responses. Those are repeated probes of one uniform scene across
three distinct epoch variants, not 12 different scenes.

Four additional oracles come from unmodified pinned `JointSender` code in an
isolated child process, with deterministic sources and source hashes:

| Source/cap | Pinned-model outcome |
| --- | --- |
| Asymmetric boxes / 49,152 | first candidate 7,543 bytes accepted |
| Nonuniform pattern / 49,152 | first candidate 38,290 bytes accepted |
| Asymmetric boxes / 7,542 | reject 7,543, accept second 6,941 |
| Asymmetric boxes / 256 | reject all four 7,543/6,941/6,663/6,503 |

Accepted oracles include full pair bytes, joint ACK bytes and full RGB565
display hashes from the pinned software receiver. The source recipes and
provenance are in `fixtures/composed-encoder-oracles/README.md`.
Model write-drain/vblank calls are explicit injected events; they are not
physical FPGA or presentation measurements.

## Offline Windows command

Build separately from the installed Sunshine instance using the existing
standalone native CMake project. Fresh environments first follow
[V20-DEVELOPMENT.md](../V20-DEVELOPMENT.md) for UCRT64 dependencies and CMake
configuration:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cmake --build cmake-build-gamebub-v20 -j2'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub-v20/gamebub-v20-conformance.exe --composed-encode-case SOURCE.json'
```

The input is a bounded JSON descriptor:

```json
{
  "schema": "gamebub-cp23-independent-encoder-case-v1",
  "epoch": 1,
  "frame": 0,
  "cap": 49152,
  "source_rgb": {
    "path": "source.rgb",
    "bytes": 1036800,
    "sha256": "<64 lowercase hex digits for source.rgb>",
    "dtype": "|u1",
    "shape": [480, 720, 3]
  }
}
```

The source must be exactly packed original RGB8. The existing canonical
descendant-path, byte-count and SHA checks apply before encoding; RGB565-only
snapshots cannot be expanded and mislabeled as original input. `encode_total_ns`
measures the encoder after source loading/construction. `source_prepare_ns`
includes source file loading, SHA verification, original RGB8 copying and RGB565
derivation; `output_hash_ns` includes the returned pair/ACK report SHA256 work.
`case_total_ns` begins before case JSON reading and ends after report construction,
including all these costs. It excludes JSON serialization/stdout, process startup,
capture, network transport, playback and end-to-end latency. None of these fields
is an end-to-end latency measurement.

This encoder does not capture or resize. Gameplay inputs should use the existing
aspect-preserving sequence export: fit content inside a 720×405 viewport and
center it in the 720×480 canvas. Exactly 16:9 content uses 720×405. The saved
Xonotic clip is 1024×600, so its actual resized content is 691×405 at `(14,37)`;
the viewport width must not be reported as that clip's resized width. Synthetic
oracle patterns deliberately exercise the full canvas.

## Validation status

The standalone Windows CLI built successfully. All four additional pinned
source cases match full pair/ACK SHA256 and every attempt's map, complete size
and admission result. Ten malformed CLI inputs reject with a nonzero result:
schema, source hash/shape/type/size/path traversal, zero epoch, undersized or
oversized cap, and sentinel frame ID. Evidence is saved under
`artifacts/composed-encoder-20261105/cli-correctness-results.json` and
`cli-invalid-results.json`.

The complete Sunshine test executable built successfully and all 160 scoped
GameBub tests passed (20 suites), including six new independent-encoder cases.
Fresh gcov profiles report 27/27 executable lines hit in the case helper and
92/93 raw gcov lines in the encoder. The sole unhit encoder line is the closing
brace of `base()`, attributed by optimized gcov to exception cleanup; every
substantive encoder statement was exercised. Compiled branch coverage is
104/184 for the encoder and 171/342 for the case helper, including compiler-generated allocation,
exception and JSON branches; full branch coverage is not claimed.

Correctness runs occurred alongside compilation and a localhost stress soak;
their incidental timings are not a codec performance benchmark. No hardware
playback is claimed.

## Saved moving-source capacity snapshot

After the concurrent stress soak ended, the root agent reserved a quiet local
slot at 02:30:38 Denver. Sixty unique native decoded Xonotic frames were replayed
sequentially through the CLI, with fresh codec epoch `index+1`, frame 0 and HUD
generation 1 for each independent fixture. This is neither a stateful stream nor
a claim about transport epochs. No hardware or network endpoint was used.

- Original clip SHA256:
  `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
- Exported source manifest SHA256:
  `f27c9b4da3fd2d4999d17ac08768021a4e09711c4dfb73b60c67c1fcba16d1d9`.
- Native executable SHA256:
  `0fb151b88d9ffc1b2decc415e55ae1cddf8e44bb6203f5e98f10387f9ed2e48b`.
- Source PTS span 7,000–1,974,000 µs, with the original per-frame IDs, RGB hashes
  and timestamps preserved. The original clip hash is exported provenance;
  each RGB file was freshly hash-checked, but the original clip was not reread.

At the unchanged 49,152-byte cap, 34/60 independent frames fit and 26 rejected
after all declared candidates. All 188 actual candidate attempts were paid,
including 154 losing attempts. Selected maps were `(8,16)`×3, `(8,32)`×16,
`(16,32)`×11 and `(32,32)`×4. Selected complete packets ranged 41,116–48,985
bytes (p50 46,506; p95 48,871).

| Measured host stage | p50 | p95 | Maximum |
| --- | --- | --- | --- |
| Encoder, including independent validation |47.992 ms |59.646 ms |65.087 ms |
| Source read/hash/construction |12.372 ms |14.790 ms |20.576 ms |
| Case read through report construction |60.575 ms |75.320 ms |80.479 ms |
| Whole fresh CLI child process |71.022 ms |85.521 ms |91.665 ms |

The runner took 4.332 s, with a separate process for every source. Summed encoder
wall time was 2.888 s: base candidate building accounted for 2.370 s, HUD preparation
86.139 ms and selected independent validation 381.662 ms. These are wall-time
measurements; process CPU and peak memory were not measured. External system
load was not controlled beyond the reserved agent slot. Sixty frames from a
short clip prefix are not a sustained or representative gameplay measurement.

This subset misses the 33.333 ms frame budget and rejects 43.3% of these source
frames at the selected cap. It does not establish 30 fps encoding or playback.
The result directs further work toward base candidate cost and the missing
stateful CP23/HD22 path, rather than increasing the frozen cap without coordination.

Only the first old AR03 result is directly a matching key component: its
candidate sizes 55,304/44,543 become 55,428/44,667 in CP23, exactly 124 bytes larger.
The old AR03 60-frame run used one key and reference-dependent ordinary frames;
this new run uses 60 independent keys. Its 20 versus 34 admitted-frame counts
therefore cannot be attributed to framing or presented as a codec improvement.
Their packet hashes are also different packet/profile-state identities.

Full per-frame records, attempts, pair/ACK SHA256, source identities and timings
are saved in `artifacts/composed-encoder-20261105/saved-frame-results.json` and
`saved-frame-records.jsonl`. The preparation script writes only uniquely named
sidecars beside the unchanged RGB export. No original frame, manifest, fixture
or earlier measurement was overwritten. A compact tracked report, including
provenance, source-code hashes, timing aggregates, validation and coverage, is
[cp23-independent-encoder-20261105.json](cp23-independent-encoder-20261105.json).

## Paid work and next measurement

Base candidate construction consumed 2,369.706 ms, or 82.05% of encoder wall
time. Independent software reconstruction and JA23 validation consumed
381.662 ms (13.21%); this is a separate validation cost, not automatically a
requirement for a future production sender. HUD preparation consumed 86.139 ms
(2.98%), framing 40.263 ms (1.39%), discard 0.351 ms and cleanup 9.591 ms.

| Outcome / attempts | Sources | Mean encode + validation | Mean base builds | Mean independent validation |
| --- | --- | --- | --- | --- |
| Accepted / 1 | 3 | 29.102 ms | 16.136 ms | 10.990 ms |
| Accepted / 2 | 16 | 45.021 ms | 30.926 ms | 11.615 ms |
| Accepted / 3 | 11 | 51.897 ms | 38.457 ms | 10.950 ms |
| Accepted / 4 | 4 | 60.216 ms | 47.112 ms | 10.600 ms |
| Rejected / 4 | 26 | 48.799 ms | 46.731 ms | 0 ms |

Numerically subtracting validation still leaves 41.775 ms mean per source,
with only 13/60 source attempts inside 33.333 ms. This analysis does not remove
validation from the implementation or establish production throughput.
The separately measured source-preparation mean is 12.730 ms; it includes
fixture file reads, SHA checks and RGB8/RGB565 snapshot construction, so it
must not be labeled live desktop capture time. Those subcosts were not isolated.

First base builds had p50 17.629 ms versus 9.625 ms for retries. Source inspection
shows that frame-local analysis already reuses forward coefficients. Every map
still performs quantization, inverse reconstruction, entropy coding and a
canonical reconstructed tag. The aggregate build bucket cannot establish which
of these is the largest hotspot. The next safe step is explicit optional
substage instrumentation, with clock/call overhead measured against the default
path and all existing oracles preserved. Quantizer-table or reconstruction-cache
optimizations require that measurement first; no wire/profile changes are needed.
