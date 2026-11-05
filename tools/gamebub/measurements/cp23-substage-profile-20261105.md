# Optional native encoder substage observations

The independent CP23 snapshot identified aggregate base candidate construction
as 82.05% of encoder wall time. That bucket did not distinguish quantization,
inverse reconstruction, entropy or tag work, so no algorithm optimization was
selected from it. New optional instrumentation measures those operations while
preserving all encoded bytes, candidate order, cap checks and default validation.

`encoder::Profile` is caller-owned and used on one encoder thread. A null
observer performs no inner steady-clock reads. Each enabled operation records
two clock reads, elapsed wall nanoseconds and a call count. Aborted operations
retain their partial paid time and increment an abort count; a regressing clock
records a diagnostic and clamps the interval to zero. No global timer setting,
worker thread, receiver session, protocol field or transport endpoint is added.

| Diagnostic stage | Measured boundary | Calls |
| --- | --- | --- |
| `request_validation` | Request and exact reference/analysis binding checks | One per attempt |
| `source_conversion` | Original RGB8 to source-plane conversion | First frame-local attempt only |
| `forward_residual` | Residual preparation and forward DCT | One per uncached block |
| `quantization` | Scaled quantizer computation, coefficient quantization/bounds/dequantization | One per block |
| `inverse_reconstruction` | Inverse transform and reconstructed-pixel placement | One per key/promoted block |
| `entropy` | Complete coefficient entropy encoding for one plane | Three per attempt |
| `inner_framing` | GM01 header, map, payload serialization and CRC | One per attempt |
| `canonical_tag` | Canonical reconstructed-bank tag | One per key/promoted attempt |

A 720×480 YUV420 source has 8,100 blocks. Uncached key encoding therefore records
48,614 clock reads; each cached key retry records 32,412. Profile bookkeeping,
clock calls and code layout can affect measured costs. Stage intervals include
observer overhead, and no correction is silently subtracted. FrameBuilder
preconditions, allocation/capture bookkeeping and other unclassified work remain
inside the existing whole-build measurement, so the stage sum is not an exact
replacement for that enclosing wall interval.

## Explicit use

Add `"profile_substages": true` to an independent source-case JSON and use the
existing `--composed-encode-case` command. Its report adds `inner_profile_enabled`
and a stage snapshot with clock/call/abort counts. Omitting the flag leaves the
observer absent. Existing frozen AR03 cases can use `--encoder-case-profiled`;
direct and mandatory-policy observations are reported separately because the
validator performs both operations.

The default independent decoder/JA23 validation still runs. Its separately
reported `validation_ns` is not inside inner encoder stages and must not be
misrepresented as pure sender encoding cost. Fixture source preparation still
includes file reading, source SHA verification and snapshot construction;
it is not live desktop capture.

## Correctness gate

The complete native target built successfully, and all 162 scoped GameBub tests
passed across 21 suites. Twelve published static CP23 instances and four
additional pinned-model source/cap cases match with profiling disabled and
enabled: full pair bytes, JA23 bytes, every candidate map/size/admission and
cap rejection remain identical. Additional regressions compare key, ordinary
and promoted inner packets/tags, verify exact bounded stage counts, and exercise
disabled, repeated-completion, aborted and regressing-clock behavior.

All 20 earlier frozen AR03 cases also pass both normal and instrumented CLI
verification, including exact inner/patch/complete bytes, tags, confirmed bank
state and mandatory candidate-policy decisions. These correctness runs occurred
under concurrent local stress; their timings are not performance evidence.

Fresh coverage reports 37/37 executable lines in `encoder_profile.h` and 9/9 in
`encoder_profile_json.h`. All 25 changed executable inner-encoder lines are hit
across the relevant test translation units. Combined raw inner-header coverage
is 334/335, with one preexisting closing-brace exception-cleanup line unhit.
The composed framer's previously documented closing-brace caveat also remains.
Compiler-generated exception/allocation branches prevent a full branch-coverage
claim; no coverage exclusions were added.

Evidence is under `artifacts/composed-encoder-20261105/`: the native test log/XML
and fresh `profile-coverage/` data. The earlier
native executable (SHA256 `0fb151b88d9ffc1b2decc415e55ae1cddf8e44bb6203f5e98f10387f9ed2e48b`)
was preserved separately for a matched default-path regression comparison.

## Performance gate

An old-disabled/new-disabled ABBA and new-disabled/new-enabled ABBA ran in the
reserved quiet slot, completing at 03:03:06–03:03:33 Denver. The same 60 native
decoded Xonotic sources ran in each pass. All 480 cases preserve the earlier
complete-pair/ACK hashes and every candidate map/size/admission decision:
34 accepted and 26 cap-rejected in each pass. Source, encoder, case and fresh
process wall times remain separate. The sources are 1024×600 content resized
to 691×405 at `(14,37)` inside the 720×480 canvas, with a 720×405 viewport.

| Pass | Mean encode + independent validation | p95 |
| --- | --- | --- |
| Old disabled A1 | 47.793 ms | 62.949 ms |
| New disabled B1 | 46.712 ms | 61.202 ms |
| New disabled B2 | 47.326 ms | 60.752 ms |
| Old disabled A2 | 52.004 ms | 72.748 ms |
| New disabled C1 | 46.804 ms | 63.613 ms |
| New enabled D1 | 51.601 ms | 66.978 ms |
| New enabled D2 | 51.002 ms | 62.452 ms |
| New disabled C2 | 47.880 ms | 58.376 ms |

No default-path regression was observed, but the old A2 tail was larger and
external load was not controlled beyond the reserved agent slot. The variation
does not justify attributing a speedup to instrumentation. Enabled versus paired
disabled mean wall time adds approximately 8.36%; no overhead is silently
removed from stage observations. Each enabled pass records 7,065,576 clock
reads, with zero regressing or aborted intervals. Each stage sum remains bounded
by its enclosing base-build wall interval.

| Inner stage, summed across 60 sources | Enabled D1 | Enabled D2 |
| --- | --- | --- |
| Canonical reconstructed tag | 519.453 ms | 512.108 ms |
| Quantization/dequantization | 486.748 ms | 478.520 ms |
| Plane entropy | 428.271 ms | 418.127 ms |
| Inverse/pixel reconstruction | 419.984 ms | 410.656 ms |
| Residual/forward transform | 296.533 ms | 291.654 ms |
| Source-plane conversion | 92.053 ms | 90.517 ms |
| GM01 framing/CRC | 18.719 ms | 17.984 ms |
| Request/reference validation | 0.185 ms | 0.187 ms |

The largest single observed stage is canonical-tag construction. Its 188 calls
use only 376 clock reads per pass, while quantization and inverse reconstruction
each use 3,045,600 reads. Those per-block stages are more affected by observer
overhead; their observed times are not corrected uninstrumented estimates.

The 26 rejected sources contain 104 definitely losing attempts: tag work costs
293.427/276.711 ms and inverse reconstruction 240.509/227.367 ms. The 34 accepted
sources contain 84 attempts, including 50 losers and 34 winners. Their aggregate
observer does not distinguish each attempt's stage duration, so no exact timing
is assigned to those 50 losers individually.

Source review found that canonical-tag serialization reserves a byte vector and
pushes two bytes per validated sample before SHA256. The next isolated candidate
is exact zero-initialized allocation with validated low-byte stores at stride2.
This preserves canonical byte order, checks and hashes; its own tests and timing
must pass before a benefit is claimed. No quantizer or loser-finalization
optimization was selected from this study.

The profiled executable SHA256 is
`0660b6b512ac5e40034d95a1ca15fdc7e4374a92f2aca449cc43d6615b606f48`.
Its complete source snapshot and binary were archived before the tag experiment.
Full runs are under `artifacts/native-profile-abba-20261105/`; a compact tracked
[JSON summary](cp23-substage-profile-20261105.json) includes provenance, stage
groups, exact executable/source hashes, validation and timing boundaries.

One correctness artifact was accidentally reused during the subsequent optimized
rerun: `profile-old-golden-results.json`. Frozen vectors, native XML, source/binary
archives and every performance ABBA output remained intact. The optimized result
was saved separately as `tag-old-golden-results.json`; future checks refuse an
existing report path. A fresh old-source verification from the preserved binary
is separately timestamped in `pre-tag-regenerated-golden-results.json` with its
exact executable hash. That regenerates correctness evidence and does not recover
or claim the initial correctness run's timestamps.
