# Receiver readiness for hardware testing

Date: 2026-11-04. This combines source audits with explicitly attributed user
reports. Windows has not probed or changed a receiver, FPGA image or live stream
as part of this readiness update.

## Decision

Latest operator update: v27/build50 is ready for legacy Test MJPEG at
`192.168.0.157:5533`, overlap active, queue32, recorder running, all starting
frame/queue counters zero. The 20-second Windows control has now finished:
IDs 2,000,000–2,000,099, 100 complete sends, 98 accepted feedback and two rejected
(2,000,079/2,000,084). Matching replies confirm `.47` source acceptance. The
receiver confirms 98 decoded/presented, two explicit Sequence gaps, zero queue
drops, peak 23/32 and no core faults/overflows/underruns or reboot. Host records
show all requested chunks sent in order; loss/reordering location and continuous
optical motion remain unverified. See [the run report](v27-control-5fps-20261104.md). The installation
hold below is historical; no sender remains running after the completed test.

Earlier user report on November 4: v27 was installing. Hold sender
traffic through that update and reboot. The last verified application is v26,
flashed at approximately 6:38 p.m. America/Denver on November 4; the user verified
its runtime ELF digest and a later USB check still identified v26. The digest
value was not supplied here. No v27 runtime verification or test baseline has
been reported yet. These reports supersede the historical unflashed-version
notes below; v26 does not need reinstalling.

The receiver team selected CP23/HC22/HD22 for the first complete custom fixture;
CP25 is not selected. It reports no complete decoder image or local loader for
either complete profile. Its ready AKD1 artifact is an earlier ROM-fed
AR03/GM01/CP02 KEY diagnostic, not a CP23-capable image. This distinguishes an
available component artifact from a deployed complete custom receiver.

After v27 installation, confirm its runtime identity, actual FPGA build and
Test MJPEG/source binding, then record fresh received/decoded/presented/dropped
and queue counters before the 20-second 5 fps video-only control. Installing a
new application does not by itself establish a new custom endpoint or profile.

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

## Later 2026-11-04 audit: v25 motion-codec study

A subsequent ref refresh found `study/gamebub-motion-codec-v25-20261104` at
`3d881382f022e95808f72cea2f2842a73343544f`. Its CP25/JA25 and GM25/HD25 formats
are incompatible with the current CP23/JA23 baseline. The reported compression
and quality changes are Python-study evidence, not an installed FPGA decoder,
loader, endpoint/port or physical 30 fps result. Old JPEG image artifacts do not
establish v25 implementation. The earlier no-v25 finding above is historical.

The first hardware profile now needs explicit coordination with the FPGA team.
Windows retains tested CP23 fixtures and adds offline HD22 exact-word checks;
it has not selected or enabled CP25. See [the profile gate and concrete request](hd22-baseline-v25-gate-20261104.md).
Hardware scheduling still requires a compatible complete image/local loader,
or both matching endpoints for a networked test. A local first frame can precede
networking and 30 fps; fresh installed-image/readback evidence remains absent.

The AV branch now also publishes `4a927ab36963a3dab7ee4bf0cef363fe4260f4a9`:
the app-only v24 diagnostics candidate passed build/package checks but is
unflashed. The retained v22/build50 demo had a reboot and changed configuration,
so its counters do not establish a clean 15 fps result. Its future application
regression window is separate from codec v24/v25 work.

The private AR03 KEY/tag diagnostic has simulated sample/tag evidence but its
isolated 100 MHz synthesis misses setup by 2.961 ns, with board routing/interface
and restricted CSR-control integration open. This identifies concrete first-board
gates beyond simply requesting an image. See [the updated diagnostic handoff](hd22-baseline-v25-gate-20261104.md#new-receiver-diagnostic-evidence).
