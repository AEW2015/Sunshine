# HD22 baseline and v25 profile gate — 2026-11-04

The Windows baseline now decodes HD22 RAW, COPY and canonical SPAN_XOR patch
packets to private exact RGB565 words. COPY and SPAN require the exact immutable
reference geometry/content tag; every result must match its reconstructed tag.
Geometry, lengths, CRC, span ordering, bounds, endpoints and canonical gaps are
checked before returning output. No bank, receiver, ACK or display is published.

Eight native regressions include independent Python struct/zlib/hashlib byte
oracles for all three modes, corruption/truncation, exact reference preservation
and malformed canonical spans. Seven additional retained source goldens provide
full current/reference word arrays: five RAW and two SPAN_XOR. That source corpus
contains no COPY golden; COPY has a separate independent unit oracle.

## Reproduce the source-word checks

The source pin remains MoonBub `4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`,
`experiments/python-game-gap-span-study/results.json`, exact raw SHA256
`2657a35912ca2b33b68f6ea75e705c0b2a88c8c5a8d4067fb8f85faecbe84971`.
The exporter reads Git objects without checking out or executing reference code.
It verifies stored/raw hashes, caps decompression and rejects extra/truncated
streams, validates word geometry and exclusively creates a new output directory.

From the candidate checkout:

```powershell
tools/gamebub/.venv/Scripts/python.exe tools/gamebub/prepare_hd22_fixtures.py --reference-repo tools/gamebub/artifacts/moonbub-30fps-study --output-dir tools/gamebub/artifacts/hd22-fixtures-20261104
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'bash tools/gamebub/build_v20_conformance.sh'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub-v20/gamebub-v20-conformance.exe --hud-delta-contract tools/gamebub/artifacts/hd22-fixtures-20261104'
```

The native replay compares all 26,880 reconstructed words and exact source tags,
and checks that reference storage is unchanged. `GAMEBUB_HD22_FIXTURES` selects
that export for the real-command Python tests. This is patch conformance, not
whole HC22/CP23 reference-state, joint publication, transport or physical playback.

## Verification

Verification: 121 native GameBub tests pass, including eight new HD22 tests.
The Python suite completes 393 tests with five existing skips, including six
exporter and two real-command HUD replay tests. Debug command replay also
passes, and all 20 original encoder golden cases remain byte-exact. Formatter,
Python lint and whitespace checks pass; the corrected native test build is clean.

Exporter statement/branch coverage reaches 100% across its tests and a real
hash-pinned CLI export. Native source-line hit unions reach 81/81 lines in
`hud_delta.h` and 40/40 in `hud_delta_case.h`; compiled branch graphs remain
separate and full branch coverage is not claimed. Evidence is retained under
`artifacts/hd22-*`, including prior profile backups. Exported words, source
objects, executables and private runtime logs are not committed.

## New v25 source and coordination requirement

A fresh source audit found
`study/gamebub-motion-codec-v25-20261104` at
`3d881382f022e95808f72cea2f2842a73343544f`. Its GM25/HD25/HU25 media use CP25
and JA25 envelopes incompatible with the tested CP23/JA23 and HC22/HD22 baseline.
The published motion/coding savings and frame-rate projections come from Python
studies on retained footage. They do not provide a complete custom FPGA image,
native receiver endpoint/port, calibrated transport/drain or physical 30 fps.
The existing JPEG firmware/bitstream artifacts are not v25 implementations.

We have requested the receiver team's first hardware profile. Windows keeps the
tested CP23 baseline until that choice and its contract are coordinated. This
checkpoint neither selects CP25 for deployment nor sends it through JPEG/AV.
HD22 baseline tests remain useful for reproducing the current reference model;
they do not imply compatibility with HD25.

## Concrete next hardware request

Please identify the first decoder profile: CP23/HC22/HD22 or CP25/GM25/HD25.
Return the complete image/source hash and installed readback, exact local
fixture/loader command, expected decode/display/ACK hashes and counters, and
the owner/safe-stop procedure. If only a component decoder is ready, name that
scope and agree a component fixture rather than claiming a complete-frame pass.

The first local FPGA fixture needs no network and no 30 fps qualification.
The checked-in CP23 independent-refresh bytes are ready for a compatible decoder.
Windows-networked testing additionally needs a matching live media implementation,
assigned receiver carriage/endpoint, loopback and bounded ownership/recovery.
There is still no defensible date for that custom path from the published source
alone. Existing JPEG/AV can have a separate controlled test when ready.

### New receiver diagnostic evidence

The refreshed AV branch at `4a927ab36963a3dab7ee4bf0cef363fe4260f4a9` publishes
`docs/V24-DIAGNOSTIC-REGRESSION-20261104.md` and coordinated progress. Its app-only
v24 diagnostic UF2 passed build/package gates but is unflashed and physically
unqualified; the retained record leaves v22/build50 installed with the demo
stopped. Those are published historical observations, not fresh device readback.
The next application window can run a 20-second 5 fps JPEG control after its
operator installs/verifies the candidate and confirms source binding/counters;
then a short 15 fps interval can test diagnostic overhead. Audio remains separate.

The separate private KEY/tag FPGA diagnostic checked 518,400 samples, its tag
and 48,203 ingress bytes in simulation. Its isolated OOC synthesis reports
negative 2.961 ns setup slack at 10 ns and has no routed board image or connected
restricted CSR command yet. This is not a complete HUD/scanout or custom UDP
path. Fix validation-path timing, establish board/interface/resource gates and
add the bounded identity/idle-guarded CSR loader before its first board test.
This component diagnostic can precede full-frame streaming and 30 fps.
The FPGA owner can also evaluate a separately documented, timing-closed slower
diagnostic clock if board/interfaces permit it; 100 MHz is not a prerequisite
for one functional frame. The current OOC result proves neither that option nor
board timing, and a slower functional test would not qualify 30 fps.

Next work depends on the shared profile decision: complete HC22/HUD transaction
and joint-state replay for CP23, or separately pin and port the v25 decoder and
goldens if the team selects CP25. Continue encoder-stage profiling independently;
no new FPS, bitrate, latency or hardware duration is claimed by these tests.
