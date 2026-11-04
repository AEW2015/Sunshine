# Receiver readiness for hardware testing

Date: 2026-11-04. This is a source/document audit only. No receiver, installed
application, FPGA image, or live stream was probed or changed.

## Decision

Fresh receiver-side update relayed by the user on 2026-11-04: existing JPEG/AV
is the only available hardware path; there is no deployable FPGA-only GM01
fixture image, live custom GM01 receiver or assigned custom network port.
The receiver agent is beginning a v22 app-only regression, first confirming the
connected device/current identity and then installing the app with the FPGA
unchanged. Post-update identity, readiness and counter baselines are still
pending here. This is the receiver team's report, not a Windows device probe.
Do not start a sender during that update window.

Hardware work has three distinct entry points: the existing JPEG/AV control,
an FPGA-only functional custom fixture, and a Windows-to-MoonBub custom stream.
An FPGA-only fixture does not need the network endpoint if the receiver team
can inject it locally into a complete functional decoder image. The published
evidence reviewed here does not establish that image either. Component hardware
tests may have their own narrower readiness gates and are not video playback.

**The first controlled custom one-frame functional test is not ready to start
on the evidence reviewed.** The published material does not establish a
complete functional decoder bitstream, a matching tested host/ESP lab endpoint,
or an agreed lab ownership and safe-stop procedure/readiness window. This is a
readiness-of-evidence finding, not a claim that a physical device was inspected
and found to lack an image.

**The first functional frame does not require 30 fps throughput qualification.**
Full-path throughput and the limiting stage remain unknown, which blocks the
later rate ladder and 30 fps qualification, not by itself a controlled
one-frame correctness test. No ETA is established by these documents.

**A short test using the existing JPEG/AV path is a separate possibility, not a
readiness finding.** No current device or installed-image readback was made, so
present JPEG/AV readiness is unknown. The published v20 README calls the prior
firmware JPEG-only and says no hardware had been programmed in that snapshot;
the coordinated note labels the ESP app/FPGA identifiers as historical and not
a live probe. Before a short JPEG/AV window, the current image, receiver state,
sender/endpoint compatibility, counters, and explicit run ownership still need
to be confirmed for that window. This audit does not authorize or initiate one.

## Prerequisites for the first controlled frame

1. **Complete functional decoder and matching lab endpoint are not evidenced.**
   The supplied receiver plan reports an exact inverse/reconstruction component
   and built-but-unflashed v22 ESP app, but does not establish a complete working
   decoder bitstream or a tested ESP endpoint that accepts the host's actual
   known-frame bytes. The v23 publication adds Python packet dispatch and shared
   analysis; it explicitly does not establish native endpoint enablement or
   FPGA integration. A matching host/ESP lab path must be tested before the
   fixture.
2. **Agree the bounded lab contract and safe stop.** Before this one-frame test,
   both sides need the exact fixture/profile and packet path, endpoint/address,
   expected acceptance/decode/reference/display/release observations, bounded
   ownership, and who stops/drains the session if an outcome is ambiguous. A
   lab-only contract may explicitly disable resume/reconnect and require a safe
   stop/reset after failure. Full production negotiation or reconnect support
   need not be invented as a prerequisite when that narrower safe contract is
   jointly agreed. Existing MSV1/AV ports do not establish a custom endpoint.
3. **Model-state evidence must include modeled drain transitions.** The 1,725
   message histories alone omit drain events and complete expected ownership
   states. Add explicit, clearly labeled model ingress/read/decode-drain and
   publication events plus expected states for the lab ownership checks. These
   are model events, not prior physical captures; requiring physical drain
   captures before the first functional hardware frame would be circular.

SR01 encoding is not evidenced in the Windows encoder, but is not a blocker for
a GM01 known-frame fixture if both ends explicitly select and support GM01 and
exclude SR01 from the lab capability/profile.

The newest inspected v24 receiver study adds an offline CP23 profile/reset
agreement prototype, including fail-closed behavior for lost GO_ACK and explicit
model inputs for persistent epoch and drain/write/vblank signals. This advances
the modeled safe-stop/recovery evidence, but does not establish those signals as
an installed endpoint, physical drain, or tested host/ESP/FPGA one-frame path.

## Separate prerequisites for 30 fps qualification

The rate ladder and 30 fps claim require full-path performance evidence that the
one-frame test does not: FPGA-only full decoder/presentation measurements,
followed by concurrent Wi-Fi, queue, QSPI, SDRAM and scanout service with
frame-correlated initiation intervals, occupancy and backlog. Complete custom
throughput and the limiting stage are unknown in the reviewed sources. A
successful single frame would establish functional progress only, not sustained
throughput. Keep the proposed 29.9 distinct presentations/s and other quality,
gap and fault limits as later qualification gates, not prerequisites for the
first frame.

Once the first-frame prerequisites above are evidenced and a coordinated lab
window is set, start with one deterministic frame and reconcile packet
acceptance, exact reconstruction/reference acknowledgement, display geometry
and release at both ends. Any later key/P/promotion/recovery sequence needs its
own agreed safe behavior. Proceed to throughput tests only after the separate
performance prerequisites and test window are ready. The proposed 30 fps gate
is not an achieved result.

## Source pins and evidence

- Windows plan: `tools/gamebub/30FPS-DEVELOPMENT-PLAN-20261104.md` in the
  current `C:/ai/sunshine-gamebub` checkout. It explicitly says unchecked gates
  are unverified and that no fixture should start before both sides implement
  the same contract.
- Coordinated receiver note: `tools/gamebub/MOONBUB-DEV-NOTE-20261104.md` in
  that checkout. It distinguishes the Windows-reported encoder work from live
  custom streaming and labels existing hardware references as not a live probe.
- Receiver-supplied "Coordinated MoonBub / Sunshine 30 fps plan", dated
  2026-11-04 and supplied in this conversation.
  It records the receiver's reported v22 unflashed app and reconstruction-only
  FPGA component, missing source publication, absent drain events, and G0-G4
  gates. These are supplied claims, not independently probed device state.
- Published receiver v20 handoff: MoonBub branch
  `handoff/gamebub-app-codec-v20-20261103`, exact commit
  `27a4dde6a7e2ea4fab09d892551ef542f05c8965`; `README.md` and
  `docs/custom-codec-prototype-v20-2026-11-03.md`. README does not provide
  evidence of a complete custom decoder bitstream or physical 30 fps result;
  it describes the installed firmware state for that snapshot as MSV1 JPEG.
- Integrated receiver study: MoonBub branch
  `study/gamebub-integrated-codec-v23-20261104`, exact commit
  `507ceb54c97e6a19b8bb21f5ab416dd3eb671e18`; file
  `docs/custom-codec-prototype-v23-2026-11-04.md`. Its Python packet/profile
  and shared-analysis results are offline evidence. The document explicitly
  says there is no native Sunshine/ESP32 endpoint, complete hardware schedule,
  physical scanline test, or sustained physical 30 fps result.
- Freshness check: `git ls-remote --heads origin` on 2026-11-04 found v20
  unchanged at `27a4dde6a7e2ea4fab09d892551ef542f05c8965`, v22 unchanged at
  `463b9279870d6654f00d21a87aed9d4fff6fa623`, and v23 unchanged at
  `507ceb54c97e6a19b8bb21f5ab416dd3eb671e18`. It also found new branch
  `study/gamebub-codec-v24-comparison-20261104`, fetched as a remote-tracking
  ref without checkout/reset, exact commit
  `4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`. Its
  `docs/custom-codec-prototype-v24-2026-11-04.md` reports software codec
  comparisons and a functional CP23/JA23/RS24 reset/profile model. It explicitly
  leaves physical decoder fit/throughput and an installed recovery service
  unestablished; this update does not change the first-frame readiness finding.
- Also inspected: MoonBub branch `study/gamebub-joint-codec-v22-20261104`,
  exact commit `463b9279870d6654f00d21a87aed9d4fff6fa623`; its
  `docs/30fps-implementation-handoff.md` and v22 progress document provide
  component/integration evidence and identify unclosed physical-throughput
  gates. They do not establish current live hardware state.

The source refs above were fetched as remote-tracking refs in the isolated
artifact repository without checkout/reset. Installed service/device state is
**unknown** from this audit.

## 2026-11-04 addendum: latest published receiver studies

A fresh `git ls-remote --heads origin` in the no-checkout MoonBub artifact
repository found no v25+ handoff. The latest versioned sources remain v24
(`4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`), v23
(`507ceb54c97e6a19b8bb21f5ab416dd3eb671e18`), and v22
(`463b9279870d6654f00d21a87aed9d4fff6fa623`). It also found v21 display-cache
study `de8b9e78754880a7309d56f1137f0edc8f43e4a2`. V21 explicitly describes
itself as a Python study/specification that installs no native endpoint; its
CB21 carriage is an offline fixture format. V24's CP23/JA23/RS24 evidence
remains software/model evidence: it does not provide RTL, a fitted physical
decoder, an installed recovery service, or physical throughput results.
Neither study supplies fresh installed-device evidence. The readiness decision
above is unchanged.

**First functional custom hardware test:** not yet evidenced as startable. An
FPGA-only local fixture needs a complete functional decoder image, local
injection of known-frame bytes, expected decode/display/release observations,
and an agreed owner and safe-stop procedure; it does not require a network
endpoint. A Windows-to-MoonBub test additionally needs a compatible custom
sender and host/ESP receiver endpoint with an assigned port, tested using the
actual known-frame bytes, plus a mutually agreed bounded profile, observations,
ownership, and safe-stop/reset procedure. A single frame does not require
throughput qualification; the 30 fps claim still needs subsequent full-path
measurements. Current installed device/image and the prior JPEG/AV demo's status
remain unverified here. No ETA can be inferred from the published sources.
