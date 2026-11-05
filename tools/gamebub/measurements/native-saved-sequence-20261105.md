# Native saved-sequence comparison — 2026-11-05

## Result

This is a finite offline native AR03 component encode plus software-decode comparison using 60 unique decoded frames from `Xonotic-0-8-2-gameplay.webm`. The selected input starts at decoded id 0 / PTS 7,000 us and ends at PTS 1,974,000 us. The run uses the existing 720×480 canvas policy with aspect-preserving 720×405 content, no resampling, no looping, and no repeated timestamps.

Baseline and cached-analysis runs accepted the same 20 frames and rejected the same 40 capture frames, with 210 candidate attempts and 190 losing attempts each. The summary records identical acceptance and packet SHA-256 by source id. All 20 selected mandatory AR03 packets matched; the rejected frames have no packet hashes. The native case checks the direct packet, mandatory candidate, and committed packet against the AR03 golden bytes (`encoder_case.h`).

| Metric | Baseline | Cached analysis |
| --- | ---: | ---: |
| Admission p50 / p95 | 54.9142 / 62.6604 ms | 39.0400 / 46.5396 ms |
| Source file read p50 | 6.7575 ms | 0.5855 ms |
| Source hash p50 | 1.9673 ms | 2.0413 ms |
| Source prepare p50 | 9.7015 ms | 3.4775 ms |
| Analysis builds / reuses | 0 / 0 | 60 / 150 |
| Max analysis coefficients | 0 B | 2,073,600 B |
| Sequence loop wall time | 4.0885 s | 2.8365 s |

At 30 fps the frame interval is 33.3 ms. Cached admission p50 and p95 improved, but both p95 values remain above that interval. Source-file reads also became much faster while the measured source-hash median remained about the same. These observations do not establish that analysis caching alone caused the full wall-time change; this is offline profiling and includes file/hash input costs. The recorded source allocation is 1,036,800 bytes and the reader does not retain decoded pixels.

## Scope and verification

This is the older AR03 mandatory HUD-component path. It does not demonstrate complete CP23 behavior, live capture, network behavior, hardware decode, CPU use, peak memory, or playback pacing. The sequence artifacts explicitly mark capture, network, hardware, and CPU/peak-memory measurements as absent. Do not treat the result as a whole-protocol or hardware qualification.

The saved native test output records **154/154 native tests passed**. The associated source coverage summary reports 100% executable-line coverage for `encoder_sequence.h` (118/118) and `encoder_benchmark.h` (149/149). The separate CLI and exporter checks reported by the run owner were **5/5 CLI** and **13/13 exporter tests**. The full 20-case golden verifier was also run separately against the current V20 conformance executable and fixture corpus; see `artifacts/v20-encoder-verification-20261105-overnight-audit.json` for that result. These checks validate their stated test or fixture scopes, not live-session performance.

## Provenance

- Saved input: `Xonotic-0-8-2-gameplay.webm`, 48,552,136 bytes; SHA-256 `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
- Source manifest SHA-256: `f27c9b4da3fd2d4999d17ac08768021a4e09711c4dfb73b60c67c1fcba16d1d9`.
- Detailed run data: `artifacts/encoder-sequence-20261105/native-moving-summary.json`, `xonotic-native-60-baseline.json`, and `xonotic-native-60-cached.json`.
- The summary identifies the run as native offline AR03 encode/software decode with source file/hash costs; it is not full CP23/network/hardware.
