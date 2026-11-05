# Windows / MoonBub morning handoff — 2026-11-05

Windows development branch: `AEW2015/Sunshine`,
`gamebub/windows-jpeg-retry-20261103`. Pull the final morning commit; the
04:09 checkpoint is `730c7f13`. Installed Sunshine and the handheld were not
replaced, restarted or flashed by this development work.

## What Windows has measured

The [30-minute localhost AV study](measurements/localhost-av-native-30fps-30m-20261105.md)
sent and accepted **53,998 / 54,000** video slots at 720×480, native 30 fps,
Q25, an 8 Mbps cap and a 400 µs hybrid tail: **29.994 sent fps** including
drain. Two encoded frames were replaced; no partials, skipped slots, repeated
source timestamps, pending ACKs or invalid datagrams were recorded.

All **172,184** sent synthetic-audio blocks decoded at the local peer. Three
publisher-queue evictions account for three sequence gaps; two blocks remained
queued at STOP. Why the queue filled is not established. Input remained live.
These are localhost software results: RF, QSPI, FPGA presentation, physical
audio, DAC buffering/drift and end-to-end latency remain unverified.

The JPEG/MSV1 and AV v1 wire contracts are unchanged. The candidate adds
explicit wait/tail selection, source binding, capture through actual STOP,
and a native CFR clip reader. Legacy clip sampling stays available and remains
the default for matched controls. At nominal 30 fps the old sampler repeated
3,000 source timestamps in 9,000 slots; that run is not unique-motion evidence.

## Prompt for the MoonBub agent

> Please coordinate the next **JPEG/MSV1** hardware check with Windows using
> the [morning matrix](measurements/overnight-test-matrix-20261105.md).
> Reconfirm installed app/FPGA identities, build50 or its actual replacement,
> overlap, queue size, placement, expected source IP, fresh trace epoch and
> starting receive/decode/present/drop/queue/core counters. Do not flash merely
> for this host pacing comparison. Verify fresh camera coverage through STOP.
>
> Last addresses were sender `192.168.0.47`, receiver `192.168.0.157`, MSV1
> UDP 5533 and AV v1 UDP 5534; validate current readiness. Start with matched
> 30-second 720×480 / 20 fps / Q25 / 4 Mbps **legacy-source** controls,
> input-only AV, audio and Windows gamepad injection off. Change only sleep
> versus hybrid600 waiting. Use fresh verified IDs; proposed ranges are
> 2,014,200–2,014,799 and 2,014,800–2,015,399, not reservations on the device.
>
> Preserve each failure's incoming and active frame IDs, expected/observed
> offsets, admission/core status, queue drops/high-water and lost-trace counts.
> Match receiver outcomes with host frame/send logs and outbound capture;
> Windows capture proves observation at its capture point, not RF departure.
> Never subtract clocks across machines. Reconcile every send and verify
> STOP/power-save restoration before a longer run or rate increase.
>
> A later 30 fps capacity probe can select native CFR source / hybrid400 /
> 8 Mbps explicitly. Treat that as a new workload, not a causal comparison
> against the 20 fps control. Qualify video first, then audio and controller
> coexistence separately. Report actual presented FPS and duration, not the
> configured rate. Keep unfamiliar failure reasons and missing observations
> unknown until evidence identifies them.

## Custom codec remains a separate gate

CP23/HC22/HD22 remains selected; CP25 was not adopted and no custom UDP port
was assigned. Windows has exact independent key/four-LEGACY-HUD encoding and
an opt-in [budgeted key path](measurements/cp23-budgeted-key-20261105.md).
The 60-source study still cap-rejects 26 frames; accepted-frame encoding plus
independent validation averages about 35 ms. This is not 30 fps custom playback.

The bounded [same-process replay](measurements/cp23-same-process-sequence-20261105.md)
checked 7,200 rows and all source retirements, preserving exact hashes and
admission while reducing inclusive wall time about 27.3%. Repeated scenes and
43.3% cap rejection remain explicit. Host tests are 548 Python (five optional
skips) and 173 native. The bounded audio-eviction trace passed unit and controlled
stall validation without changing the AV wire format.

The latest fetched MoonBub feature tip remains
`dfc7dbdc63e1af5e669e3219bb7bb4974c176f5a`; it still documents incomplete
CP23 decoder/loader work. Its older published v27 device report does not
establish current runtime identity. The last operator-reported image here was
v30/build50; a fresh receiver identity check is required for the morning test.

Before a custom hardware trial, provide a matching complete decoder, arbitrary
payload loader, source/image hashes, parser-to-presentation coverage and safe
ownership/recovery evidence. Earlier envelope/base/HUD component checks or a
ROM-fed KEY image do not establish that complete path. Keep custom payloads
off the legacy JPEG endpoint and do not identify them as H.264.
