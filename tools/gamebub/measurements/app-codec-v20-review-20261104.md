# V20 review and Windows/Sunshine development priorities

Reviewed2026-11-04 without switching either checkout, modifying installed
Sunshine or starting a hardware stream. Local changes were preserved.

Pinned sources:

- Sunshine [`3d49c6fe87753eb5b35d693991fdff0365e4bbbf`](https://github.com/AEW2015/Sunshine/tree/3d49c6fe87753eb5b35d693991fdff0365e4bbbf/tools/gamebub/v20).
- MoonBub [`27a4dde6a7e2ea4fab09d892551ef542f05c8965`](https://github.com/AEW2015/moonbub/tree/27a4dde6a7e2ea4fab09d892551ef542f05c8965/hardware/gamebub-v20).

Compared with the previously reviewed v11 Sunshine head3e225446, the new
Sunshine branch changes only documentation/profile/wire-contract files: four
files, no executable encoder or negotiated streaming implementation. MoonBub
has substantial Python models, fixtures and a portable C11 inverse reference.
These custom-codec v20 artifacts are separate from the older installed JPEG
FPGA images also described as v20/build50 in hardware reports.

## What is now concrete

The copied Sunshine wire/development JSON files are independently verified
byte-identical to the pinned MoonBub hardware kit. Hashes and limits are saved
in `artifacts/v20-handoff-audit-20261104.json`.

The [native-host task](https://github.com/AEW2015/moonbub/blob/27a4dde6a7e2ea4fab09d892551ef542f05c8965/hardware/gamebub-v20/TASKS.md)
requires mandatory exact RGB565 HUD patches before bounded base selection,
candidate source ownership, and actual build/admit/commit/discard semantics.
The development profile has four fixed requested rectangles and four legal
ROI/background scale maps:8/16,8/32,16/32,32/32. The complete AR03 frame cap
is49152bytes, including the61-byte header, variable body and final CRC; it is
not a new JPEG size limit. Mandatory regions must be agreed per application;
the demonstration rectangles are not automatic HUD detection or universal
WoW/Elden Ring layouts.

The kit reports20 isolated packet fixtures with exact pre-bank/id/tag state,
nine offline IT20 tile streams and a C11 inverse oracle. Its published34 tests
and101667 exact inverse blocks are retained upstream evidence; this review did
not independently rerun that full suite, RTL, native Windows compilation or
hardware playback. IT20 is an offline fixture format, not a runtime codec.

## Recommended work order

| Priority | Windows/Sunshine work | Acceptance evidence |
| --- | --- | --- |
| P0: usable existing path | Consolidate the product-rounding WASAPI audio worker, QPC scheduling, video and profile-selected controller into one reproducible finite-session launcher. Add source/capture/encode/send/feedback timing, stalled-source detection and explicit audio tail/drain reporting. | Audio-only, video-only and combined matched tests; reconcile every audio sequence and video outcome. Separate invalid FPGA snapshots from rejection and capture failures. |
| P1: v20 conformance executable | Import pinned profile/contracts and fixture hashes into an isolated native Windows target. Port wire serializers, parsers and lifecycle state first; use the C inverse as a verification oracle, not an assumed encoder implementation. | All20 packet fixtures with their declared pre-banks; exact reconstructed banks/tags/HUD output and AF03 bytes; malformed length/CRC/geometry/identity negatives cannot publish state. Run MSYS2/UCRT64 build and applicable sanitizer/overflow checks separately. |
| P2: native candidate encoder | Port mandatory patch preparation/validation, complete-byte reservation, bounded four-map attempts and commit/discard. Share valid analysis/cache work across attempts without hiding its cost. | Native-versus-Python comparisons on retained source inputs; every accepted frame has every requested patch and fits49152bytes. Unfit frames reject entirely. Tests cover all maps failing, stale commit, ID reuse before commit, external leases, source/callback failures and cache eviction. |
| P3: negotiated transport and recovery | Implement the FG19/PC18/QC18/GF03/AF03 ownership machine offline, then agree capability/profile and reset/rekey messages with receiver agents before live use. | Replay the1725 serialized FG19 messages, intentional loss and wrong-kind/slot/epoch replies; bounded memory, no fabricated credits or use-after-release, unknown outcomes retain ownership and stop until a defined recovery. |
| P4: measured integration | Profile native capture/scaling, patch prep, every losing build, encode/admission, packet pacing, queue age and reference promotion; coordinate actual ESP/FPGA service measurements. | Fresh moving gameplay, same source and settings, unique captured/decoded/presented IDs, p50/p95/p99 stage times, full HUD coverage, quality/error measures, wire/control/audio costs and recovery results. Only then integrate an explicitly named custom mode into Sunshine. |

Use `cmake-build-*` and the Windows MSYS2/UCRT64 wrapper for native targets;
keep the installed working service and ordinary Moonlight behavior intact.
New native regression tests must follow repository tests_common.h/Doxygen and
formatting requirements. Do not place custom AR03 under H.264 or JPEG IDs.

P0 can improve the actual product while P1/P2 are developed offline. The recent
15fps combined runs reached approximately11.27 and12.29 complete host sends/s,
not15 or30 presented frames/s. The WoW run sent audio only through284.26s of
a600s AV session, with0 reported capture errors, after which counters stalled;
WoW was subsequently observed closed. Treat silent/inactive loopback, device
changes and bounded worker shutdown as explicit tests, not inferred capture
success. Receiver audio rejection/unconfirmed counters and underruns also
remain high. Add per-block host sequence/gap evidence and coordinate receiver
device-lock/admission diagnostics before assigning the cause to host or QSPI.

Evaluate a shared pacing budget that protects timely audio and input while
bounding video bursts; test it in controlled comparisons. Preserve independent
input sequencing/lease and never let video backpressure hold a control pressed.
Do not label all unresolved audio outcomes as Wi-Fi loss, nor count invalid
snapshot zeros as actual playback counters. Any receiver scheduling change
needs its own versioned A/B test.

## Ownership rules the native port must preserve

- FG19 GRANT reserves the exact frame slot; it does not commit a candidate or
  publish a reconstructed reference.
- PC18 returns packet-buffer capacity only. It is not a decoded frame ACK.
- FINISHED frees the request-control token after its barrier, not frame storage.
- RELEASE follows actual ingress/read/decode drain. Do not free a bank still
  held by a reader or packet/DMA.
- Only AF03 confirms decoded reference publication, after complete CRC/body/
  epoch/frame/bank/tag validation. Keep display RGB565 HUD patches out of YUV
  prediction banks and canonical reference tags.

The laboratory limits are three sender transactions, two frame slots, five data
tokens and one control mailbox position (six total). Three framebuffer roles
are separately accounted. Lab epoch1 alone is not a reconnect/reset protocol.
Production capabilities and recovery remain explicitly unimplemented upstream.
Do not retrofit these messages into the current MSV1 endpoint without negotiation.

## Performance gates that change our plan

The [v20 results](https://github.com/AEW2015/moonbub/blob/27a4dde6a7e2ea4fab09d892551ef542f05c8965/docs/custom-codec-prototype-v20-2026-11-03.md)
project5.316Mbps forward data for the easier sample and11.376Mbps for the
complex sample at30fps, excluding grant/reverse/radio overhead and audio/input.
Those are arithmetic projections from short reused clips, not measured Wi-Fi
capacity. At2Mbps and30fps the gross video budget is8333bytes/frame before
transport overhead, versus mean complete bodies20583.56/44083.60bytes. Merely
selecting the new codec does not make the current2Mbps operating point30fps.

Mandatory HUD coverage improves but the complex sample's active-channel MSE
rises27.0335→34.0921. Exact HUD does not imply a lossless base. Background
quantization and admitted/dropped frames must be included in quality reports.
Unsig­naled receiver HUD reuse is not implemented; existing host caching still
transmits patches. Defer receiver patch reuse/deltas until a separately agreed
identity/generation/loss/refresh/reset contract and measurements justify it.

The inline-tag conditional mean service improves67.6298→62.8622ms, but all
native conditional profiles still miss33.33ms. FPGA decoder RTL, mapped
resource/Fmax, physical scanline timing and ESP/RF calibration are open gates.
Host optimization alone cannot qualify30 displayed fps while these remain open.
Preserve720x480 coded and720x405 active geometry. Do not silently replace the
primary goal with the lower-resolution diagnostic modes.

## First concrete implementation milestone

Deliver an offline `gamebub-v20-conformance` Windows executable and fixture test
runner, plus the consolidated existing JPEG/AV launcher. Prove native byte/state
conformance and reliable audio/input before adding a live custom endpoint.
Proceed through the paired A0–A10 acceptance gates; preserve the current JPEG
baseline until negotiated native/receiver modules qualify. No hardware flash,
installed service restart or whole-branch switch is needed for this milestone.
