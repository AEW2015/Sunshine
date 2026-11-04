# CP23 independent-refresh software checkpoint — 2026-11-04

Windows now has offline CP23/JA23 envelope support and an independent-refresh
decoder for AR03 key frames with all four nonreferenced LEGACY HUD patches.
This is a bounded subset: it rejects predictive refresh inputs and HD22 dispatch.
There is no live CP23 sender, stateful HC22/HD22 receiver, negotiated custom
endpoint or physical presentation measurement.

## Source, bytes and reconstruction

The wire implementation follows MoonBub commit
`4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`, specifically
`experiments/python-game-hd22-joint-study/model.py`. CP23 has a 53-byte header,
two hash-bound AR03/HC22 components and a four-byte outer CRC, with a strict
49,152-byte complete cap. JA23 is 134 bytes with AF03 at offset 33 and HA22 at
offset 76. Parsing a JA23 does not establish an outstanding transaction or
publication; successful reconstruction independently constructs the full ACK.

The existing pinned v24 results contain twelve media-output instances but only
three distinct epoch variants of one static RGB(44,96,156) scene. Every packet
is 5,166 bytes and every ACK 134 bytes. HC22 carries four LEGACY patches and
requires no previous HUD bank. These probes are not detailed moving footage.

`--composed-contract` checks exact envelope reserialization, decodes the base
through the native software decoder, validates all four exact HUD rectangles,
recomputes the canonical HUD tag, overlays the words and constructs JA23 from
the actual reconstructed results. It compares the complete little-endian RGB565
display hash and ACK bytes with the frozen Python-model outputs. Separately,
RGB565 conversion of the declared source color gives `0x2b13`: all 21,120 HUD
words per instance must equal that independently calculated value.

The full-image hash is a source-model oracle checked by a separate native
implementation; it is not a camera result or independently captured hardware
reference. Base/reference state is private to each refresh and discarded after
the call. No existing live banks or sessions are changed.

## Ready-to-share first-frame assets

Checked-in files under `tools/gamebub/fixtures`:

- `v24-independent-refresh.json`: source pin, hashes, geometry and expected words/hash.
- `v24-independent-refresh-epoch1.cp23`: complete 5,166-byte synthetic packet.
- `v24-independent-refresh-epoch1.ja23`: exact expected 134-byte joint response.

These are media bytes with **no assigned network carriage or port**. They must
be used with a compatible decoder/local loader, not sent through the existing
JPEG/AV endpoints. They make the first local fixture concrete; they do not make
a decoder image or integrated receiver exist.

Build the isolated executable using [the existing guide](../V20-DEVELOPMENT.md),
then reuse the exact results blob exported for [RS24](v24-reset-wire-20261104.md):

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub-v20/gamebub-v20-conformance.exe --composed-contract tools/gamebub/artifacts/v24-recovery-results-4025d355.json'
```

## Verification

Validation: 113 native GameBub tests pass (nine new envelope tests and seven
new refresh tests). The full Python suite completes 385 tests with five existing
skips; all six RS24/CP23 real-command tests also pass in the Debug coverage
build. All 20 existing encoder golden cases remain exact. Formatter, Python lint
and diff whitespace checks pass.

GCC source-line coverage across the actual native tests and Debug CLI reaches
154/154 lines in `composed_wire.h`, 34/34 in `composed_case.h`, and 63/64 in
`composed_refresh.h`; the last missed line is the display-export function's
closing brace. Full branch coverage is not claimed. Local build/test/gcov and
reconstruction evidence is under `artifacts/v24-composed-*`. Earlier native
profiles and the previous Debug conformance profile were preserved before tests.
No generated build artifacts or private desktop captures are included in Git.

## Next hardware handoff

Please return a complete decoder image/source hash and installed readback,
local known-byte loader and the supported envelope/profile. If the first decoder
accepts GM01 or AR03 rather than CP23, agree an explicit extracted-component
fixture and expected observations; do not silently reinterpret this packet.
Record ingress/decode/presentation/drop/core counters, expected image/reference
hashes and release/drain observations, with a named operator and safe-stop plan.
A local FPGA fixture needs no network endpoint and no 30 fps qualification.

The Windows-networked test additionally needs compatible host/ESP carriage,
assigned endpoint/port/source binding, explicit bounded packet/frame ownership
and a passed loopback path. The current branch audit still supplies no new
deployable custom image or endpoint, so there is no defensible calendar ETA.
Existing JPEG/AV can receive a separate short regression once the receiver is
confirmed ready; that test does not qualify CP23.

After the independent frame passes, add HD22/HUD reference-state conformance,
key/P/recovery sequences and controlled capture/encode stage profiling. The
33.33 ms encoding budget and sustained 30 presentations/s still need measurement.
No new FPS, quality, bitrate, latency or hardware duration is claimed here.
