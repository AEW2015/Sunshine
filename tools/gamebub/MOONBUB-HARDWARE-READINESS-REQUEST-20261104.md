# Request to schedule the first hardware window

Current receiver-side report: JPEG/AV is the only available hardware path, and
a v22 app-only regression is underway with the FPGA intended to remain unchanged.
For that immediate control test, provide the fresh post-update identity,
receiver/source binding and counter baseline before Windows sends anything.
The custom-path requests below apply to later work; no custom port is assigned.

Please report which path is currently ready, separating built artifacts from
what is installed on the handheld:

1. Existing MSV1/JPEG video and AV v1 control: a short regression/control test.
2. FPGA-only custom GM01 fixture injected locally: no network endpoint needed.
3. Windows-to-MoonBub custom GM01 fixture: requires matching tested endpoints.

We do not need to meet the 30 fps timing target before the first functional
custom frame. We do need a complete functional decoder for that path, a known
compatible lab contract, bounded ownership and a defined safe stop. The latest
published material reviewed by Windows does not establish that readiness yet.
Please give the missing implementation or artifact, not a projected FPS result.

For the path you propose, supply:

- Firmware/FPGA source commits, artifact hashes and installed-image identifiers.
  State whether the FPGA image is a full decoder or only a component self-test.
- Supported profile: GM01/CP02 with AR03 and required HP01/HR01 patches, coded
  720x480 and active 720x405, permitted maps and 49,152-byte whole-frame cap.
  Exclude unsupported SR01 explicitly; it is not needed for a GM01 test.
- Identify the actual outer packet/profile. Windows is still pinned to the
  v20 lab contract; CP23/JA23/RS24 models require joint review and explicit
  compatibility agreement, not assumed compatibility with bare AR03/GF03.
- For networking, the exact contract hash, endpoint/port, actual accepted sender,
  session/epoch/frame setup and capacity/credit rules. Existing JPEG UDP5533
  and AV UDP5534 do not establish a custom endpoint. Verify addresses rather
  than assuming historical 192.168.0.47 / 192.168.0.157 are current.
- For local FPGA injection, the fixture-loader procedure and expected packet,
  reference and displayed-output hashes. Network gates do not apply to this
  isolated path.
- Explicit modeled drain/ownership events and expected states, implemented
  receiver drain conditions, and what happens after missing/unknown replies.
  A bounded lab safe-stop with no automatic resume is acceptable if jointly
  agreed; do not claim production reconnect/reset support that is absent.
- Starting accepted/decoded/presented/drop, queue and core counters; retained
  frame IDs, failure reasons, timestamps and the location of continuous logs.

Windows has exact encoder/wire conformance, frame-local analysis reuse, and
packet-permit bookkeeping under offline fault models. These are not a live
custom sender or a physical-drain proof. For a networked window, both sides
must first pass the same lab contract and the host must complete its actual
loopback sender checks. Do not infer readiness from the model executable alone.

Once ready, agree a window and one sender/serial owner. Begin with one known
frame, verify geometry, exact reconstruction/reference ACK and resource release,
then a short key/P/promotion/recovery sequence. Throughput and longer 30 fps
qualification follow that functional gate. Preserve the existing working image
and logs; coordinate any flash/core reload or active-session change beforehand.

For later rate tests, retain packet-permit turnaround and credit-starvation
intervals as well as QSPI bandwidth. A cap-sized 49,152-byte frame uses 49 GF03
fragments at 1,008 payload bytes, or 1,470 fragments/s at 30 fps. With the pinned
five DATA permits, sustained full-window flow needs roughly 5/1470 seconds
(3.40 ms) average permit turnaround; jitter and other service can still stall
it. This is a derived window budget, not measured receiver capability. Do not
enlarge the window unilaterally; agree and version any capacity change.

Also agree the assembly timeout and its clock origin before reusing an old
JPEG pacing preset. The pinned GF03 software reassembler defaults to 150 ms
from assembly start. A cap-sized frame alone needs 2.62 Mbps payload rate to
fit that interval, before packet overhead, credit waits or scheduling jitter.
The old JPEG 0.7 Mbps / 3000 ms fixture settings therefore cannot be assumed
valid for custom GF03. Choose a compatible payload/rate or jointly configure a
longer lab timeout; retain unknown ownership safely on timeout.
