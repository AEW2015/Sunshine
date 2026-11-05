# Canonical-tag allocation experiment

The optional inner profiler identified canonical reconstructed-bank tag creation
as the largest single observed stage. The isolated experiment replaces repeated
byte-vector pushes with exact zero-initialized allocation and validated low-byte
stores at stride 2. It preserves dimensions, Y/Cb/Cr order, little-endian signed16
representation, every shape/domain check and exception message/order, SHA256
input and truncated output. It adds no cache, reference state or wire change.

The original profiled executable and complete native source were archived before
editing. Before SHA256 is called, all input samples must still be 0–255 and every
plane must have its exact shape. Invalid late samples cannot silently truncate;
all construction remains private and the input planes remain unchanged.

## Correctness

The standalone Windows CLI and complete native target built. All 164 scoped
GameBub tests passed across 22 suites. Added independent hashlib oracles cover
literal endian/plane-order bytes and minimum 2×2, full-area 720×480 and individual
dimension edges 2048×168/168×2048. Regressions cover short/long late planes,
negative/256 samples, geometry checks, failure order and input immutability.
All 20 frozen AR03 cases pass both default and profiled verification, and all 16
CP23 source/cap oracle instances retain exact packet/ACK bytes and candidate
decisions with instrumentation disabled and enabled.

## Matched measurement

The root agent reserved a quiet slot after the media stress tests ended. Each
pass replays the same 60 unique native Xonotic sources through separate fresh
CLI processes, with fresh independent codec epochs and unchanged 49,152-byte cap.
All 480 cases match the original packet/ACK hashes and map/size/admission outcomes:
34 accepted and 26 cap-rejected per pass. This is not a stateful stream, network
test or hardware playback measurement.

| Pass | Mean encode + independent validation |
| --- | --- |
| Original, profiling off A1 |44.535 ms |
| Candidate, profiling off B1 |45.197 ms |
| Candidate, profiling off B2 |45.648 ms |
| Original, profiling off A2 |46.597 ms |
| Original, profiling on C1 |49.737 ms |
| Candidate, profiling on D1 |49.644 ms |
| Candidate, profiling on D2 |49.452 ms |
| Original, profiling on C2 |49.824 ms |

The paired default mean differs by only 0.14 ms (about 0.32%), within the observed
run variation. Profiled total mean differs by about 0.47%. The tag stage itself
falls from 498.550/500.643 ms to 487.571/482.964 ms across 60 sources, about 2.87% or
0.239 ms per source. Quantization and inverse stages remain essentially unchanged.
No material whole-encoder speedup or 30 fps encoding/playback result is established.
External system load was uncontrolled outside the reserved agent slot; CPU and
peak memory were not measured. No per-stage clock overhead was subtracted.

- Original executable:
  `0660b6b512ac5e40034d95a1ca15fdc7e4374a92f2aca449cc43d6615b606f48`.
- Candidate executable:
  `45598ddb7842671fa0cb27ab36afd2471487027db749c2f68adb24b69e94ff81`.
- Original clip:
  `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
- Source manifest:
  `f27c9b4da3fd2d4999d17ac08768021a4e09711c4dfb73b60c67c1fcba16d1d9`.

The original 1024×600 clip occupies 691×405 at `(14,37)` in the 720×480 canvas;
720×405 is the viewport. Exported RGB inputs are reverified individually; the
original clip hash is provenance and the original file was not reread.
Full records remain in `artifacts/native-tag-abba-20261105/`. A tracked
[JSON summary](cp23-canonical-tag-allocation-20261105.json) preserves all run
aggregates, stage counters, provenance, source/executable hashes and limitations.

The root retained this as a small bounded-storage cleanup, with no claim of a
material whole-encoder speedup. The measured larger opportunity is that oversized
independent candidates still reconstruct and hash before cap admission; a
separate bounded prepare/admit/finalize interface would need its own exact-byte,
ownership and timing gates. No such optimization is included in this experiment.
