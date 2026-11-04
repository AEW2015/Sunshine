# Native encoder conformance, 2026-11-04

The separate Windows candidate now encodes original RGB8 sources into GM01,
CP02 raw/Rice coefficients and HP01/HR01 patches, then constructs complete
AR03 frames. Parallel agents implemented the inner and patch encoders; Luna
prepared and reviewed bounded fixture tooling. This work used offline inputs
and did not start a hardware session or change the installed Sunshine service.

## Verified behavior

The reference is MoonBub commit
`27a4dde6a7e2ea4fab09d892551ef542f05c8965`. The final fixture export is
`artifacts/v20-encoder-cases-20261104`, with manifest SHA256
`4047c666d473149e184356a7d2d56be25c39fc0a6188b42f33a11777a58731c4`.
The campaign report is
`artifacts/v20-native-encoder-validated-20261104.json`; its executable SHA256 is
`89f2b28b9815b0b9e94463187a3ba4043aaacbced53ef772d46b834c2502807e`.
After enforcing the independently pinned source-results hash, the repeated
campaign also passes in `artifacts/v20-native-encoder-pin-validated-20261104.json`.

| Check | Result |
| --- | ---: |
| Complete AR03 packets matching frozen bytes | 20 / 20 |
| Inner streams and selected patches matching frozen bytes | 20 / 20 cases |
| Mandatory policy cases | 10 / 10 |
| Actual policy encoding attempts | 13 |
| Losing attempts included in cost accounting | 3 |

These include exact RGB-to-YCbCr conversion, Q14 forward transforms,
quantization, Rice parameter selection, raw fallback and patch tie rules.
The mandatory policy prepares all four original-source HUD patches, tries the
four ordered maps and enforces the 49,152-byte complete-frame cap. A control
case rejects its first 54,894-byte attempt and accepts its next 47,238-byte
attempt. Tests also exercise commit, exact AF03 acknowledgement, bank
publication and release of candidate reader leases.

The other ten cases retain the upstream baseline's partial HUD patches.
They prove byte conformance for those controls and do not qualify for the
mandatory HUD profile. Each case restores its exact reference banks; the
twenty cases do not form a continuous stream.

## Validation and limits

The native regression suite passes 42 tests, including corrected sparse and
dense CP02 micro-oracles, asymmetric forward-transform checks and patch-mode
controls. Logs and XML are saved as
`artifacts/v20-native-encoder-final-tests-20261104.*`. Additional rectangle
boundary cases pass in the same 42-test suite, with a clean final log at
`artifacts/v20-native-encoder-bounds-final-20261104-clean.log`.
The final full Python run passes 372 tests with five existing skips; its log is
`artifacts/v20-encoder-final-python-tests-20261104.txt`. Actual encoder CLI
tests are enabled in that run, including malformed duplicated oracle fields.
The normalizer and campaign verifier each reach 100% statement and branch
coverage in focused tests (198/133 statements and 94/64 branches respectively).
After the full run, an oversized source-results boundary case was added to
the existing verifier regression; all 13 focused verifier tests pass again.
Native inner-encoder coverage is 215/216 lines (99.54%); the uncovered line
is attributed to function cleanup. This is not a claim of full native branch
coverage. Patch-encoder line coverage is 105/109 (96.33%); the four uncovered
lines are closing-brace cleanup attribution. The native exception and allocator
paths are not fully covered. Formatting, CMake lint and whitespace checks pass.

This campaign is software conformance, not a throughput benchmark or verified
end-to-end playback. Its measured totals across thirteen instrumented policy
attempts are 182.075 ms building, 132.411 ms validating and 0.042 ms discarding.
They exclude capture, scaling, transport, hardware decoding and presentation;
they must not be converted into an achieved streaming FPS or latency claim.
There is no persistent source-analysis or patch cache, so repeated transform
work is paid on retries. No new image-quality metric was measured.

All source canvases are 720×480 with the pinned 720×405 active region.
SR01 is decoded by the existing conformance implementation, but this encoder
currently emits GM01. There is no live custom-codec endpoint or negotiated
GF03/FG19/PC18 transport implementation. Existing MSV1/JPEG and AV operation
remains separate; stock clients do not receive custom data under H.264 IDs.

## Next development gate

Agree the exact live capability, credit, reference-acknowledgement and
reset/rekey contract with the receiver agent before connecting this encoder
to transmission. Then test bounded ownership, loss and recovery on localhost,
and benchmark capture/scaling plus every encoding attempt using sustained
moving footage. Only after those checks should a short hardware trial measure
received, decoded and presented rates separately. Reproduction commands are
in [V20-DEVELOPMENT.md](../V20-DEVELOPMENT.md).
