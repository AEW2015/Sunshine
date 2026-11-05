# Explicit size-first independent CP23 keys

The measured retry cost justified a separate opt-in key builder that delays
inverse reconstruction and canonical-tag calculation until actual entropy bytes
prove the candidate fits. The existing `FrameBuilder`, default strategy,
quantization math, map order, frame cap, selected bytes and independent decoder
validation remain intact. This is an offline software encoder subset, with no
P frames, HD22 state, reference publication or live endpoint.

`KeyBudgetBuilder::attempt(request,max_inner_bytes)` returns an actual complete
GM01 byte count and an optional fully finalized `BuildResult`. Every ordered map
still performs real coefficient quantization, entropy encoding, header/map
serialization and CRC. Only a fit reconstructs pixels, computes its nonzero tag
and exposes valid bytes/tag. An oversize candidate returns size only; no missing
tag or partially valid result reaches a legacy policy or packet serializer.

The CP23 wrapper derives inner room from the complete cap minus actual HC22 and
fixed CP23/AR03 framing. If fixed bytes already exceed the cap, room is zero;
the explicit guard prevents unsigned underflow. Cap 256 still pays all four
actual candidate sizes. A chosen pair still runs full independent software
decode and exact JA23 construction before returning.

One immutable analysis belongs to one source/frame/epoch. Strict binding and
ordered-map checks prevent reuse for a different source even if pixels match.
P, promoted, referenced and incompatible-bank requests reject before analysis.
Successful finalization, exhausted maps, explicit retirement, failure and
destruction release only this builder's private analysis/source owner. Temporary
payload/coefficient/reconstruction retirement is measured, and returned finalized
bytes remain valid after builder retirement or later misuse.

## Explicit use and timing boundaries

Add `"budgeted_keys": true` to an independent source-case JSON and run the
existing `--composed-encode-case` command. The flag must be a JSON boolean;
the default remains false. `"profile_substages": true` independently enables
diagnostic clocks.

The final report declares `inner_strategy` and `inner_stage_boundaries`:

- Legacy quantization includes dequantization; inverse reconstruction excludes it.
- Budgeted preparation quantizes only. A selected inverse stage recomputes
  dequantization from retained quantized coefficients before inverse/pixel writes.
- Budgeted `analysis_ns` includes binding/allocation, source conversion, residual
  preparation and forward transforms together. Its fine-grained source/forward
  buckets are therefore zero, not unpaid work.
- `retire_ns` includes private coefficient/payload/reconstruction/analysis release.
  Both `analysis_ns` and `retire_ns` are already inside `build_ns`; do not add them
  again when calculating total paid work.
- `encode_total_ns` includes all candidates, finalization, framing, chosen-pair
  independent decoder/JA23 verification and cleanup. Source fixture read/hash/
  snapshot costs, case wall and fresh CLI process wall remain separate.

No quantization-versus-inverse bucket speedup is inferred across strategies with
different boundaries. Whole build/encode wall comparisons are authoritative.
Observer overhead is never silently subtracted.

## Correctness and ownership gate

The standalone CLI and complete native target build. All 168 scoped GameBub tests
pass across 23 suites. Twelve static CP23 instances and four additional pinned
source/cap cases retain exact pair/ACK bytes and every map/size/admission under
legacy and budgeted paths, with profiling disabled and enabled. All 20 old AR03
source cases pass both default and profiled verification.

Four focused tests cover zero/exact/one-less budgets, valid-result-only output,
four real rejected sizes, explicit/automatic/destructor retirement, strong source
ownership, source/frame/epoch cache binding, P/promoted/reference/order rejection
and immutability of previously finalized output after a later invalid call.

Fresh coverage hits 130/130 executable lines in `key_budget_encoder.h`,33/33 in
the JSON case helper and all 37/9 lines in the profile/helper headers. The existing
composed framer's closing-brace exception-cleanup caveat remains 113/114 raw lines;
no substantive composed encoder statement is unhit. Compiled exception/allocation
and profile-unreachable branches prevent a full branch-coverage claim. No coverage
exclusions were added.

## Quiet matched snapshot

The root reserved a quiet slot after media/tests ended. Two ABBAs compare the
preserved pre-budget executable with the new default, then new legacy versus new
budgeted behavior. A final profiled budgeted pass checks stage/counter boundaries.
All 540 source cases preserve the original pair/ACK hashes and candidate outcomes:
34 fit and 26 cap-reject per 60, with 188 actual attempts each pass.

| Pass | Mean encode + independent validation | p50 | p95 |
| --- | --- | --- | --- |
| Pre-budget default A1 |48.096 ms |48.376 ms |60.316 ms |
| New default B1 |43.940 ms |46.016 ms |54.876 ms |
| New default B2 |44.901 ms |46.073 ms |55.736 ms |
| Pre-budget default A2 |44.641 ms |46.178 ms |57.279 ms |
| New legacy C1 |46.075 ms |47.724 ms |57.525 ms |
| New budgeted D1 |31.934 ms |29.860 ms |42.315 ms |
| New budgeted D2 |31.967 ms |30.322 ms |43.862 ms |
| New legacy C2 |44.963 ms |46.297 ms |55.337 ms |
| Budgeted profiled E1 |34.485 ms |32.047 ms |44.731 ms |

No default regression was observed within run variation. The paired all-source
mean falls about 29.8%, from 45.519 ms to 31.950 ms. That average includes 26 rejected
frames; accepted-only budgeted means remain 34.996/34.922 ms, and tails exceed the
33.333 ms budget. This does not establish 30 fps complete encoding or playback.
The unchanged cap rejection is an independent limitation that CPU work cannot fix.

Each budgeted pass skips 154 proven-oversize reconstruction/tag operations while
still paying 188 quantization/entropy payloads. First analysis costs 385.501/
382.642 ms and retirement 41.185/40.936 ms per 60, already charged inside build wall.
The diagnostic pass records 3,598,348 observer reads, with zero aborts/regressions:
1,522,800 quantized blocks,564 entropy planes,275,400 finalized inverse blocks
and 34 canonical tags. No clock correction, CPU or peak-memory claim is made.

The clip is 1024×600, resized to 691×405 at `(14,37)` in a 720×480 canvas with
720×405 viewport. Sixty native decoded frames have unique source IDs/PTS; each
fixture uses its own fresh codec epoch and frame 0, not a stateful stream or a
transport-epoch transition. Every RGB file is rehashed; the original clip hash
is provenance and the original video is not reread during this study.

- Original clip SHA256:
  `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
- Source manifest SHA256:
  `f27c9b4da3fd2d4999d17ac08768021a4e09711c4dfb73b60c67c1fcba16d1d9`.
- Pre-budget executable:
  `45598ddb7842671fa0cb27ab36afd2471487027db749c2f68adb24b69e94ff81`.
- Measured budgeted executable:
  `28a0d154eea3b79c5ced353e7e2d698b70bf94707db0d0f149ba663901e213b3`.
- Final diagnostic-label build:
  `a6239708c2b4823b5a281e8dedd981b02e74ffa829d1ab0dc8b639b25e399d97`.

The measured binary and full source snapshot remain archived before the later
diagnostic-label-only change; the final native 168-test gate passed again. Full
records are in `artifacts/native-budget-abba-20261105/`; a compact tracked
[JSON summary](cp23-budgeted-key-20261105.json) preserves all run aggregates,
accepted/rejected timing groups, stage counts, exact hashes and coverage.

The next custom-codec step is stateful P/HC22/HD22 and joint reference/publication
work against the same pinned profile, plus an actual FPGA decoder/loader and
receiver endpoint before hardware playback. No wire/profile change or cap
increase is justified by this host-only snapshot.
