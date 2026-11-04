# Windows AV v1 conformance check

Pinned MoonBub revision: `dff5452871e911a60c8a278134e1f6fabdaa95e2`, branch
`feature/av-v1-20261103`, `host/av-v1/fixtures/av-v1`.

## Current result after receiver clarification

**Offline packet and PCM conformance pass.** Contract clarification
`aab1ba337550ba472c30ee417fcf6d439b5a7f1e` requires full-product IMA rounding in
both decoder and encoder feedback. It changes no packet or golden-fixture bytes.
The Windows codec now implements that arithmetic explicitly; resampling still
uses PyAV. All seven golden packets remain byte-exact and the decoded2020-byte
PCM now has the required hash
`85459adb008cf8af659afb72f6f03823940f1393bbc92a39840b9adfd62a81cc`.
The acceptance verifier returns zero with wire/PCM/complete flags all true.

A fixed encoder test uses source frames(0,0),(13,-13),(16,-16): product feedback
chooses the next magnitude0, whereas shift/add feedback would choose1. This
checks the encoder predictor update, not just a matching standalone decoder.
Additional cases cover signed predictor/index clamps, invalid PCM/state, channel
packing and starting indices copied into subsequent independent block headers.

All23 focused tests pass with100% coverage across368 source statements and130
branches. Full discovery completed245 tests in17.189 seconds with5 existing
integration skips and no failures; Ruff checks and formatting pass. The saved
five-second stereo capture was also re-encoded with the new product codec:
478 blocks,241,390 decoded frames,75 source-resampled tail frames discarded.
This is local validation, not a fresh capture or physical receiver playback.

New evidence is saved separately: `artifacts/av-v1-product-vector-report-20261103.json`,
`av-product-final-tests-20261103.txt`, `av-product-final-coverage-20261103.txt`,
`av-product-full-tests-20261103.txt`, `windows-audio-product-adpcm-20261103.*`
and `audio-fixtures-product-v2-20261103/`. Initial failure evidence below remains
historical and was not rewritten. No live AV socket or hardware test was started.

## Initial check, before product rounding was made explicit

The Windows work previously had local audio preparation and a generic ordered
input adapter, without any AV datagram serialization. New `av_protocol.py` and
`av_session.py` now align packet bytes and local session behavior with the
published contract. They are not yet a live network runner or Sunshine mode.

| Check | Result |
| --- | --- |
| Fixed48-byte network-order header | Pass |
| Whole-packet CRC, zeroing bytes40..43 | Pass |
| All7 golden datagrams and SHA-256 | Exact match |
| Every one-bit mutation across560-byte audio datagram | Rejected |
| Wrong version/length/rate/reserved, with repaired CRC | Rejected |
| HELLO/OFFER/START correlation, retry and local expiry | Pass, in-memory tests |
| Independent control/audio/MSI1 sequence spaces and wrap | Pass, in-memory tests |
| Duplicate/stale/wrong-peer/cookie rejection,500ms neutral release | Pass, fake sink |
| Snapshot-valid gating for FPGA counters | Pass |
| Published decoded PCM versus this host's FFmpeg | **Mismatch** |
| Live peer-bound socket handshake / input injection / audio playback | Not tested |

The verification command below reports separate wire and PCM outcomes. It
initially exited nonzero; with the product-rounded codec it now succeeds:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked python verify_av_vectors.py'
```

See [protocol0.7.0](../protocol/0.7.0-av-v1.md) for exact hashes, decoder rounding
comparison and the resolved receiver decision. The mathematical product and shift/add
experiments each reproduce one output exactly; actual ESP32 rounding has not
been inspected or measured here. The audio encoder emits valid WAV IMA blocks;
packet syntax compatibility does not establish equality of decoder reconstruction.

All13 new unit regressions pass, with100% coverage across201 new source statements
and72 branches. Full lab discovery completed243 tests in16.832 seconds with5
existing integration skips and no failures. This includes tests ensuring the conformance command reports
failure rather than accepting a mismatched PCM oracle. Ruff checks/format pass.
The original failed strict-PCM test output was superseded by the dedicated
acceptance verifier, whose failure is preserved explicitly in the JSON report.

Artifacts: `artifacts/av-v1-vector-report-20261103.json`,
`av-v1-pcm-comparison-20261103.json`, `av-v1-host-decoded-20261103.s16le`,
`av-v1-rounding-experiment-20261103.json`, `av-v1-conformance-tests-20261103.txt`,
`av-v1-coverage-20261103.txt` and `av-v1-full-tests-20261103.txt`.
Reference binary assets, JSON vectors and source hashes are retained under
`fixtures/av-v1/`. No receiver traffic, installed service or driver changes were
made by these checks. Windows still reports the missing virtual-controller bus.

## Golden-vector revalidation

Repeated on2026-11-03 at17:16:34 MST (2026-11-04T00:16:34Z). The remote
`feature/av-v1-20261103` head still resolves to the pinned `dff54528` revision.
Compared all four local reference assets directly with `git show` bytes from
that commit; every file and SHA-256 matched. All seven packet vectors again
matched exactly, and all13 focused packet/session regressions passed.

The published PCM still differs from local FFmpeg reconstruction. Full
conformance remains false, and the verifier deliberately returns nonzero.
This recheck made no production-source or reference-vector changes. Detailed
results: `artifacts/av-v1-golden-revalidation-20261103.json`; test output:
`artifacts/av-v1-golden-revalidation-tests-20261103.txt`.
