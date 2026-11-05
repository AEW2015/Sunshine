# Windows/Sunshine update for MoonBub developers

Date: 2026-11-04

V27 control completed: [IDs 2,000,000–2,000,099 at 5 fps, quality 25, 2 Mbps](measurements/v27-control-5fps-20261104.md).
All 100 sends completed; the receiver confirms 98 received/decoded/presented
and two sequence failures. Frame 2,000,079 expected 20,480/observed 21,504;
2,000,084 expected 21,504/observed 23,552. Requested host offsets were all logged
sent, in order, roughly 5 ms apart; exact times are in the run report. Queue drops 0,
peak 23/32; core fault/overflow/underrun counters 0; no reboot observed. Sender is
stopped; no audio or controller ran. Loss/reordering location and continuous
optical motion remain unverified.

Earlier user status: v27 was installing. Hold sender traffic until its
post-reboot identity, receiver/source binding and fresh counters are ready.
V26 is the last verified application, installed around 6:38 p.m. America/Denver
on November 4 with runtime ELF verification and a subsequent USB identity check.
Earlier unflashed-version notes are historical, not a request to reinstall v26.

Profile decision: the receiver team retained CP23/HC22/HD22 for the first complete
fixture. The new v25 study at `3d881382` introduces incompatible CP25/JA25 with
GM25/HD25, which is not selected. No complete custom decoder/local loader is
reported; the ready AKD1 artifact is an earlier ROM-fed AR03/GM01/CP02 KEY
diagnostic and must not be described as CP23-capable.
The [new HD22 decoder/replay checkpoint](measurements/hd22-baseline-v25-gate-20261104.md)
adds exact reference-dependent patch decoding, not a live whole-frame receiver.

Current checks: 121 native GameBub tests pass; Python completes 393 tests with
five skips. Seven retained HD22 goldens match all 26,880 words, independent unit
oracles cover COPY, and the original 20 encoder golden cases remain exact.

Earlier published hardware evidence at MoonBub `4a927ab`: app-only v24 diagnostics were built
but unflashed; the FPGA private KEY/tag simulation passed, while its isolated
100 MHz timing, routed board/interface and restricted CSR-control gates remain
open. Windows can support a 20-second 5 fps JPEG diagnostic control once the
receiver operator confirms the installed candidate, binding and fresh counters.
That window is separate from custom-codec first-frame and 30 fps qualification.

First-frame follow-up: [Windows reconstructs the CP23 independent-refresh subset](measurements/v24-composed-refresh-20261104.md).
All twelve frozen outputs (three epoch variants of one static scene) reproduce
the full RGB565 image hash and exact JA23. Every mandatory HUD word also matches
the independently calculated source RGB565 value. The exact 5,166-byte CP23,
134-byte expected JA23 and source/hash manifest are checked in under
`tools/gamebub/fixtures/v24-independent-refresh*`.

Prior independent-refresh verification: 113 native GameBub tests passed; Python completed 385 tests
with five skips; all 20 encoder golden cases remain exact. This validates the
static independent-refresh subset in software, not a live sender or 30 fps.

Please provide a compatible complete FPGA decoder image/hash and local loader
for this fixture, with installed readback and decode/display/release evidence.
If the decoder accepts another envelope, agree an explicit component fixture
and label its narrower scope. This local check needs no network and no 30 fps
qualification. Windows-networked CP23, stateful HD22/HUD and live reference
publication remain unimplemented; the existing JPEG/AV ports are unchanged.

Host-control follow-up: [Windows now replays RS24 host phases and retries](measurements/v24-host-reset-20261104.md),
including all eight single-loss positions, lost GO_ACK and modeled reboot epochs.
Real packet/frame accounting tests retain owners after PC18/FINISHED. Drain is
still an explicit model input, and published traces have no owner snapshots.
Please provide full owner/drain/write/vblank transcripts and a deployable local
decoder fixture before we describe custom hardware testing as ready. A local
FPGA fixture can precede networking; a Windows test additionally needs the
compatible CP23 media sender and an agreed ESP endpoint/port.

Prior host-control verification: 97 native GameBub tests passed; the Python suite completed
383 tests with five skips; the 20 encoder golden cases still match. The new
host/replay headers reach full executable-line coverage across the native-test
and Debug CLI translation units; this is not full branch or physical coverage.

Previous wire checkpoint: Windows added offline RS24 wire conformance against
MoonBub `4025d355`: all 124 frozen controls reproduce exactly and 5,704
single-byte corruptions are rejected. This is syntax/byte verification only;
no live reset or CP23 media endpoint is enabled. See
[the checkpoint](measurements/v24-reset-wire-20261104.md) for reproduction and
the next state/ownership gates. The implementation/test counts below describe
the earlier encoder checkpoint, not the complete current tree.

Next coordination request: please freeze the CP23/JA23 profile and full reset
transcripts, including explicit packet/transport drain, candidate/reference
readers, late owners, repeated BUSY, lost GO_ACK and reboot identity. We will
port host transitions against those states before enabling media. A custom
hardware test still needs a complete compatible decoder and agreed endpoint;
the existing JPEG/AV demo does not satisfy that gate.

The Windows native custom-codec encoder is ready for joint protocol and
recovery work. Offline conformance passes; live custom-codec streaming and
30 fps hardware playback have not been established.

## Implemented and verified

- Native RGB8-to-YUV420 conversion, Q14 forward transform, quantization and
  CP02 raw/Rice coding, producing GM01 inner streams.
- Native HP01/HR01 encoding of exact RGB565 HUD patches.
- Complete AR03 construction with the 49,152-byte whole-frame cap, including
  headers, patch framing and CRC.
- Mandatory four-patch policy, ordered map search, candidate commit/discard,
  bounded reference readers and exact AF03 reference acknowledgement.
- All 20 frozen cases reproduce the expected inner, selected patch and
  complete AR03 bytes. Ten mandatory cases exercise 13 actual attempts,
  including three losing attempts. The other ten baseline cases retain
  partial HUD selections and do not qualify for mandatory HUD coverage.
- 42 native regression tests pass. The full Python suite completes 372 tests
  with five existing skips. Fixture normalizer/verifier focused tests reach
  100% statement and branch coverage; native coverage is below 100%.

Reference: MoonBub commit
`27a4dde6a7e2ea4fab09d892551ef542f05c8965`, with Sunshine handoff
`3d49c6fe87753eb5b35d693991fdff0365e4bbbf`.
Coded geometry remains 720x480, with a 720x405 active region.
Cases restore their exact precondition reference banks; they are isolated
conformance cases, not a continuous stream.

## Next coordination request

Please provide or confirm a versioned live contract and its golden transcripts
before we connect the encoder to a receiver endpoint:

1. Capability/profile negotiation for AR03/GM01/CP02 and HP01/HR01, including
   dimensions, mandatory HUD rectangles, permitted maps and frame-size limits.
2. Exact GF03/FG19/PC18 packet layouts, integrity checks, ports, timing units,
   frame/session identifiers and chunking limits, identifying which parts are
   currently implemented on the receiver.
3. Ownership and credit rules: retain separate accounting for data tokens,
   control completion, frame-slot release and decoded-reference publication.
   Our next offline gate must verify that FINISHED frees only its request
   control token, RELEASE follows actual drain, and validated AF03 confirms
   reference publication. Please confirm those semantics against your version.
4. Reset/rekey, reconnect and timeout behavior, especially lost feedback and
   unknown outcomes. We must not invent credits, reuse an owned buffer, or
   assume a reference was published after an ambiguous result.
5. Negative vectors/transcripts for loss, duplication, reordering, stale or
   wrong epoch, wrong slot/kind and delayed reference acknowledgement.

Windows will first implement offline transcript replay and localhost failure
tests, then benchmark capture/scaling and all encoding attempts. After joint
agreement, start hardware testing with a known fixture and a short low-rate
stream, correlating frame IDs with ingress, decode and presentation counters.
Increase rate only after measuring transport, queue and decoder service time.

## Current limits and evidence

The encoder emits GM01; SR01 decoding exists, but SR01 encoding is not yet
implemented. There is no persistent source-analysis/patch cache or live custom
endpoint. No new sustained FPS, bitrate, quality metric or end-to-end latency
is claimed by this fixture campaign.

The custom-codec work is separate from the installed JPEG FPGA image also
called v20/build50 and from the existing MSV1/JPEG and AV v1 paths. Do not send
AR03 under JPEG or H.264 identifiers. The installed Sunshine service and the
original checkout remain unchanged.

Windows candidate: `C:\ai\sunshine-gamebub`, branch
`gamebub/windows-jpeg-retry-20261103` in `AEW2015/Sunshine`. Use that development
branch for the source and reproduction tools. Generated fixture exports,
executables and raw local logs are separate artifacts and are not included in
the source commit; recreate fixtures with the linked development guide.

- [Build and reproduction guide](V20-DEVELOPMENT.md)
- [Detailed results and limitations](measurements/v20-native-encoder-20261104.md)
- Local final fixtures: `tools/gamebub/artifacts/v20-encoder-cases-20261104`
- Local campaign: `tools/gamebub/artifacts/v20-native-encoder-pin-validated-20261104.json`

Fixture manifest SHA256:
`4047c666d473149e184356a7d2d56be25c39fc0a6188b42f33a11777a58731c4`.
Pinned source-results SHA256:
`6542a1fe19735217fa17c0efa2dc18c68b28ef2cd88a8c5baf8534901c1fa94d`.
