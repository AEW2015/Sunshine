# App codec v11 review during the 12 fps JPEG soak

Reviewed Sunshine `handoff/gamebub-app-codec-v11-20261103` at
`3e225446645e81280fb12111adb58bdce5ec6e44`, with companion MoonBub at
`2951a1de18b1fa5aa2de2078f131c539e9aa44d5`. This is a read-only review;
the running sender, receiver, installed Sunshine service and hardware settings
were not changed. The current hardware soak remains baseline JPEG over MSV1.

## What changed

Relative to the previously reviewed Sunshine study head `8c086fc1`, the new
Sunshine commits add 104 README lines linking research results. They add no
executable Sunshine codec or live streaming mode. Switching the whole worktree
to this branch would also discard newer local sender fixes; it is not an
appropriate way to enable the research formats.

The companion studies implement actual Python codec bytes and tests:

- HG01 combines a GM01 temporal base with bounded exact RGB565 UI patches.
  Patches change the displayed image, never the reconstructed YUV anchor.
  Configured rectangles are priorities, not automatic HUD detection.
- BM01 tries block motion against an acknowledged reconstructed key. Real-window
  byte changes range from about +3.8% to -6.7%, with substantially more Python
  preparation work and small distortion changes. It is not a universal upgrade.
- The finite link study packetizes GM01/HG01 through GF02 and models GA01
  feedback, ownership, corruption and loss. An ACK binds epoch, frame ID and the
  outer body tag, including UI patches. Inner-base identity alone is insufficient.

These formats are neither JPEG nor conformant HEVC/AV1. Current JPEG/MSV1
hardware does not implement their decoding, reference lifecycle or feedback.
Do not transmit them under a JPEG or H.264 identifier.

## What the measurements establish

The link model assumes ideal 8 Mbps forward and reverse links, 160 Mbps QSPI,
10 ms feedback propagation, 60 Hz presentation and a 150 ms frame-age limit.
CPU stages use measured Python calls in a virtual service schedule. Acquisition,
native concurrent execution, physical DMA/CDC and panel scaling are unverified.

| Coded mode | Strict presentations per 60 scheduled IDs, two clips | Eventual presentations |
| --- | --- | --- |
| 720x480 GM base, 30 IDs/s | 54 / 54 | 55 / 56 |
| 720x480 exact UI, 30 IDs/s | 49 / 40 | 51 / 43 |
| 512x288 GM base, 30 IDs/s | 59 / 59 | 60 / 60 |
| 512x288 exact UI, 30 IDs/s | 58 / 58 | 59 / 59 |
| 512x288 exact UI, 20 IDs/s | 60 / 59 | 60 / 60 |

Strict windows last two seconds at 30 IDs/s and three seconds at 20 IDs/s;
eventual results include drain time. A trimmed diagnostic rate of 30 IDs/s
does not mean every frame passed the strict window. These are short software
experiments, not sustained hardware playback. Scheduling the same 60 source
frames more slowly also does not test live capture decimation.

As a capacity screen, stored second-clip totals for 512x288 adaptive UI imply
about 3.016 Mbps at 30 scheduled IDs/s, or 2.035 Mbps at 20, when all modeled
forward bytes including drain are divided by the capture window. Nominal IP/UDP
is included, RF/retries are not. GM-only 512x288/30 is about 1.700 Mbps on that
sample. These are offered-demand calculations, not a rerun at 2 Mbps; the UI
path has no demonstrated margin at the current cap.

The architecture's two physical output buffers and the link scheduler's three
metadata roles do not prove one consistent allocation. A third 720x480 RGB565
buffer raises the example 512x288 one-reference allocation to about 2.399 MiB
before scratch. Display-sized scaling, bandwidth and ownership need a concrete
implementation. This is not a claim about the board's total available memory.

The expected-output oracle reuses the same decoder implementation in another
instance. Its checks are useful, but shared parser/algorithm errors can agree;
an independently written decoder and golden vectors remain necessary.

## Next experiments to try

1. Finish the current 12 fps JPEG hardware run unchanged and correlate host
   deadlines, ACKs and packet times with receiver Busy and queue traces.
2. Offline, replay the custom codec model at the measured 2 Mbps operating point
   with measured jitter/feedback service. Retain strict and eventual delivery,
   p95/max age, key bursts, loss recovery and finite memory accounting.
3. Compare GM-only and bounded UI against receiver-compatible JPEG using the
   same source duration, timestamp-based frame selection and matched display
   area. Inspect scaled HUD readability; per-canvas PSNR alone is insufficient.
4. Before any hardware codec trial, specify a separately negotiated profile,
   native encoder/independent decoder, golden malformed/valid packets, reference
   ownership and scaler/memory design. Keep 720x480 JPEG as the hardware control.

There is no new v11 setting ready to enable on the existing JPEG FPGA. Reduced
resolution custom coding is a separate research path, not a verified replacement
for the agreed 720x480 target.

## Reproduction scope

The companion report lists 57 tests: hybrid 7, block 10, hybrid-link 20,
architecture 9 and independent audit 11. This review inspected source and stored
results. An isolated archive of the pinned companion commit passed all 9
architecture arithmetic tests and all 11 audit tests (20 total); these completed
in 0.025 and 0.570 seconds respectively. Commands, the source archive and logs
are preserved under `artifacts/v11-stdlib-tests-2951a1de-20261103/`. These checks
validate arithmetic and stored evidence, not live codec interoperability or
hardware performance. No codec benchmarks were rerun during the soak. The codec
results record Python 3.14.4, NumPy 2.5.4, Pillow 13.0.0 and PyAV 19.0.2. No
per-study dependency lock was found, so the current sender environment must not
be assumed equivalent. Architecture and audit checks use the standard library.

Primary companion evidence: `docs/custom-codec-prototype-v11-2026-11-03.md`,
`docs/gamebub-hevc-av1-fpga-plan.md`,
`experiments/python-game-hybrid-link-study/README.md`, its `model.py`, `adapter.py`,
`comparison.json` and `test_hybrid_link.py`, plus the hybrid and block study
implementations. Read them from the pinned commit above to avoid moving refs.
