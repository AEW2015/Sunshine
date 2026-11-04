# Prompt for the MoonBub development agent

Continue MoonBub receiver/FPGA development toward **720x480, 30 unique displayed
frames/s**, preserving a centered 720x405 active 16:9 image. Keep 60 fps deferred.
Coordinate with the Windows agent using a shared, versioned contract.

Read the Windows handoff and current plan:

- https://github.com/AEW2015/Sunshine/blob/19cdd708/tools/gamebub/MOONBUB-DEV-NOTE-20261104.md
- Windows branch: `AEW2015/Sunshine`, `gamebub/windows-jpeg-retry-20261103`.
- Current plan: https://github.com/AEW2015/Sunshine/blob/gamebub/windows-jpeg-retry-20261103/tools/gamebub/30FPS-DEVELOPMENT-PLAN-20261104.md
  Pin the retrieved plan's commit in your reply; it is newer than the original
  handoff commit above.

Windows has a native GM01/CP02 encoder, HP01/HR01 patches, AR03 construction,
mandatory candidate policy and exact AF03/bank conformance. All twenty frozen
cases match bytes; ten mandatory cases exercise thirteen actual attempts.
There is no live custom transport yet. SR01 encoding is not implemented.
The reference MoonBub pin is `27a4dde6a7e2ea4fab09d892551ef542f05c8965`;
inspect newer work and state the exact version you propose to use.

Please carry out these tasks:

1. **Inventory the real implementation.** Identify exact firmware/FPGA commits,
   built versus installed images, custom decoder support and negotiated
   endpoints. Keep custom-codec v20 separate from the older JPEG image also
   called v20/build50. Do not flash hardware or alter a working session without
   coordinating the test window.

2. **Publish the live contract and golden transcripts.** Confirm or explicitly
   revise GF03/FG19/PC18/QC18/AF03 layouts, CRC coverage, ports, dimensions,
   frame cap, map/HUD profile, timestamp units, session/epoch/frame identities,
   capabilities and reset/rekey/reconnect. Identify implemented versus proposed
   behavior. Include the ownership transcript set and negative vectors for
   loss, duplication, reordering, wrong kind/slot/epoch/tag and delayed ACKs.
   Agree changes before either side adopts a different format.

3. **Prove ownership semantics.** Separate packet credit, request completion,
   frame-slot release and reference publication. FINISHED must not free frame
   storage; RELEASE follows ingress/read/decode drain; only validated AF03
   confirms the reference. Unknown outcomes retain ownership until defined
   recovery. Demonstrate bounded buffers and no read/DMA after release, stale
   publication, double release or fabricated credits.

4. **Measure FPGA-only throughput before blaming Wi-Fi.** Feed locally available
   valid custom frames and include coefficient decode, reconstruction, tags,
   patches, SDRAM and presentation work. Report sustained initiation interval,
   completion/presentation intervals, backlog and faults across easy and complex
   content. Thirty fps requires throughput of one frame per 33.33 ms; total
   latency can be longer only if real overlap sustains that rate. Isolate the
   limiting stage and optimize it without changing arithmetic or ownership.

5. **Measure concurrent receiver service.** With Wi-Fi active, trace frame IDs,
   socket/queue events, packet drops, queue peak, QSPI wait/transfer times,
   minimum credits, decoder admission/owning frame, reference ACK and actual
   presentation. Add explicit reasons and offsets for timeout, supersession,
   Busy and sequence failures. Keep bounded traces continuously captured so
   the first failing frame is retained. Report invalid snapshots separately
   from confirmed hardware errors.

6. **Coordinate staged hardware tests.** Begin with one known fixture, then
   key/P/promotion and controlled recovery, followed by video-only 60-second
   tests at 5/10/15/20/30 fps. Capture baseline/final counters and reconcile
   host IDs with accepted/decoded/presented outcomes. At 30 fps progress to
   five minutes, then thirty minutes. Add audio and controller only after
   video-only qualification. Freeze settings for comparisons and change one
   variable per experiment. Do not start an uncoordinated hardware stream.

The old 2 Mbps cap is not the 30 fps budget. At 49,152 bytes/frame, AR03 bodies
alone require 11.80 Mbps at 30 fps, before packet/control/audio overhead.
Measure concurrent useful capacity and choose a jointly agreed operating point;
do not assume isolated QSPI bandwidth or nominal Wi-Fi rates establish it.
Keep 720x480; do not substitute a lower resolution and call the primary goal met.

Reply with: exact versions and capability matrix; contract/transcript paths and
hashes; FPGA-only and concurrent stage timings; maximum verified sustained
presentation rate; the limiting stage; and the next safe coordinated test.
For every result report content, resolution, actual unique FPS, quality/map,
bitrate, latency method, duration, drops, queue peak and faults. Distinguish
simulation, isolated benchmark and physical playback. Mark unavailable evidence
unknown; do not infer success from encoder settings or accepted packets alone.
