# Native transport wire replay and continuous software profiling

Implemented 2026-11-04 on the separate Windows development candidate. Parallel
agents implemented transport and profiling; Luna audited the frozen contract.
No hardware stream, firmware flash or installed-service restart was performed.

## Wire conformance and bounded local bookkeeping

`native/transport.h` implements explicit big-endian GF03, TOKEN, FG19, PC18 and
QC18 parsing/serialization with bounded lengths, identities, reserved fields and
CRC handling. It also supplies a two-slot sender frame-intent/reply ledger with
a single pending control request and conservative stop on unknown outcomes.
FINISHED retains the frame owner; a matching later RELEASE frees that owner.

This ledger is deliberately incomplete protocol machinery: callers must still
prove CANCEL occurs before DATA and FINISH follows return of all packet permits.
It has no packet-credit ledger, live receiver, physical-drain proof, reference
publication or production reset/rekey implementation. Do not use it alone as
a safe live streaming endpoint. A4 remains open.

`--transport-contract` requires the exact pinned contract SHA256
`02a1655a56ac886ffad157753f07f8214325473f26b0227e2c17a3af4f42b0b7`.
The native runner passes nine histories / 1,725 FG19 byte round trips and
3,450 private CRC/truncation rejection probes, plus PC18/QC18 examples and
26 GF03 fragments reconstructing the golden AR03 example. Report:
`artifacts/v20-transport-wire-20261104.json`.

The messages were serialized from upstream model histories, not captured from
hardware. This is wire conformance; the histories omit the explicit drain events
needed for full-state ownership verification. See the
[source audit](v20-transport-contract-audit-20261104.md).

## New profiling workload

`native/encoder_benchmark.h` generates a finite continuous horizontal rotation
of one hash-bound original RGB8 source, starts with clean software reference
banks, and runs actual mandatory candidate admission, commit, software decode
and AF03/reference updates. It does not concatenate unrelated fixture P frames.
Options bound work to 1..1800 frames; reports retain every attempt and reject.

The CLI `--encoder-benchmark CASE.json FRAMES` uses one-pixel circular motion,
promotion every 30 frames and key refresh every 300. It reports source
preparation, patch preparation, each build/validation/discard, full admission,
separate software decoding and serial loop wall costs. Timing distributions
include p50/p95/p99/max. CPU utilization and peak memory are not measured.

Admission includes the encoder's independent candidate validation. A second
software decode in the loop verifies receiver/reference evolution. Serial loop
speed includes that extra decoder and is not encoder-only throughput. There is
no capture, scaling, pacing, Wi-Fi or physical decoder/display measurement.
Rotating a frozen gameplay image is generated motion, not fresh moving gameplay.

An initial 300-frame run overlapped compilation. Its report is retained as
`artifacts/v20-generated-motion-2600-300-20261104.json` for exploratory accounting
only; it must not serve as a controlled performance comparison.

### Sequential baseline measurements

Two 600-frame runs were then executed sequentially without another agent build
or benchmark running. Host: Intel Core i7-10875H, 8 cores / 16 logical processors;
MSYS2 UCRT64 GCC 16.2.0, Release `-O3 -DNDEBUG`. Background Windows activity is
not controlled. Metadata: `artifacts/v20-generated-motion-sequential-metadata-20261104.json`.

| Metric | 2600 image seed | 7200 image seed |
| --- | ---: | ---: |
| Admitted / software decoded | 600 / 600 | 600 / 600 |
| Actual attempts / losing attempts | 600 / 0 | 1,398 / 798 |
| Source preparation + admission mean | 27.993 ms | 46.668 ms |
| Source preparation + admission p95 | 32.103 ms | 58.045 ms |
| Source preparation + admission p99 | 36.059 ms | 74.271 ms |
| Above 33.33 ms source/admission work | 23 / 600 | 560 / 600 |
| Mean actual build work, all attempts | 11.891 ms | 29.905 ms |
| Mean independent candidate validation | 13.315 ms | 13.834 ms |
| Mean extra software decoder check | 12.545 ms | 12.942 ms |
| Mean complete AR03 bytes | 29,817.11 | 45,078.78 |
| AR03 body load if those means ran at 30 fps | 7.156 Mbps | 10.819 Mbps |
| Serial software loop wall duration | 24.432 s | 35.892 s |

Both runs contain two keys, eighteen promotions and 580 ordinary frames, with
final software-confirmed ID 599 and no cap rejection. Complex-source accepted
maps 8/16, 8/32, 16/32 and 32/32 occur on 42, 328, 220 and 10 frames. Thus
558/600 frames retry; losing builds alone average 17.356 ms per input frame.
The above bitrate rows are arithmetic projections excluding transport, reverse
feedback, audio and radio overhead, not measured link capacity.

Reports: `artifacts/v20-generated-motion-2600-600-sequential-20261104.json` and
`artifacts/v20-generated-motion-7200-600-sequential-20261104.json`. The second
software decoder is additional oracle work; exclude it from host admission,
but do not hide the independent candidate validation already within admission.
The measured complex workload exceeds the host's 33.33 ms interval before
capture/scaling/network are included. These baselines motivated the optional
frame-local analysis reuse measured below.

### Implemented analysis reuse and paired measurements

`encoder::Analysis` retains raw forward coefficients for one immutable source,
reference and frame identity. `FrameBuilder` permits only the four ordered map
attempts of one prepare; repeated prepare/source/reference/frame use is rejected.
Every encoded attempt still checks the current canonical reference samples,
including mutations through a retained mutable Bank alias. Quantization, entropy
coding, reconstruction, complete-byte limits and independent validation remain
unchanged. First-build analysis cost is paid in the measured callback.

Coefficient storage is bounded to 2,073,600 bytes per prepare, excluding input
ownership/object overhead; this is not a process peak-memory measurement. The
benchmark destroys analysis before commit or advancing to the next source.
There is no global cache. The ordinary `encode_inner` API and default benchmark
remain uncached. `--encoder-benchmark-cached` explicitly enables reuse; the
mandatory frozen-case runner now exercises cached retries for conformance.

After regression checks, four new 600-frame runs used the same optimized binary
sequentially, with no concurrent agent build or benchmark. Summary and input
report hashes: `artifacts/v20-analysis-ab-summary-20261104.json`. Executable SHA:
`d48d7b6c12eb78b7f337402543cc6b32a0cf399c8aed66fc177878bbeb6fbcce`.

| Source preparation + admission | Easy baseline | Easy cached | Complex baseline | Complex cached |
| --- | ---: | ---: | ---: | ---: |
| Mean | 27.914 ms | 30.124 ms | 46.461 ms | 41.111 ms |
| p95 | 31.189 ms | 34.421 ms | 59.022 ms | 49.188 ms |
| p99 | 36.692 ms | 37.755 ms | 70.394 ms | 60.244 ms |
| Work exceeding 33.33 ms | 18/600 | 44/600 | 559/600 | 566/600 |

All runs admit and software-decode 600 frames, with identical per-frame recorded
decisions, maps, attempt sizes, packet sizes, kinds and software-confirmed frame
IDs between
baseline/cached modes. Full bytes for all 600 generated packets were not retained
and compared. Byte/tag equality is separately covered by all twenty golden
cases (including thirteen cached policy attempts) and native four-map key/P/
promotion tests. No new image-quality score was measured.

The easy workload has no retries and regresses with analysis materialization.
The complex workload reuses analysis 798 times: mean improves 11.51%, p95
16.66%, but still misses the 33.33 ms budget. Its number of work intervals over
that budget increases slightly; these are unpaced work-time diagnostics, not
measured dropped frames. Neither mean speedup nor total accepted count proves
30 fps operation. These are single paired samples on this Windows host, not a
statistical guarantee or hardware playback qualification.

Keep reuse opt-in. Profile and fuse first-map analysis capture to reduce its
observed approximately 2.32 ms first-build overhead, then repeat both workloads.
Complex later-attempt build work falls 46.17%, while independent candidate
validation remains about 13.70 ms/frame. Do not remove checks to obtain a faster
number; separately profile validation/tag/render/CRC work before optimizing it.

## Reproduction and next gates

Commands and environment variables are in
[V20-DEVELOPMENT.md](../V20-DEVELOPMENT.md). After analysis reuse, the full Python
suite completes 377 tests with five existing skips, including actual baseline/
cached CLI comparisons; log: `artifacts/v20-frame-analysis-python-tests-20261104.txt`.
All twenty encoder golden cases pass with the expanded executable and cached
mandatory policy; report: `artifacts/v20-frame-analysis-golden-20261104.json`.
All sixty-four native tests pass in
`artifacts/v20-frame-analysis-tests-clean-20261104.{txt,xml}`. Native transport
line coverage is 211/213 (99.06%); merged inner-encoder line coverage across
encoder/benchmark translation units is 277/278 (99.64%). Remaining attributed
lines are cleanup braces. Native exception/allocator branch coverage is not
complete. Earlier sixty-test and 376-test evidence remains preserved.

Next implement packet-permit ownership and the agreed explicit full-state
transcripts, then localhost loss/recovery soak. Optimize measured host stages
without removing validation or hiding retry costs. Complete receiver pipeline
and endpoint readiness remain separately required before a custom hardware test.
No new achieved hardware FPS, wire bitrate, end-to-end latency or image-quality
score is established here.
