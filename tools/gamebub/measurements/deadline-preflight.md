# Sender deadline preflight tests

The sender checks the complete frame's ideal MSV1 serialization time against
its remaining age deadline before sending the first packet. It includes all
chunk headers and any existing pacer delay. If the frame cannot fit even in
ideal conditions, it sends zero bytes; it still aborts a partially sent
frame if the scheduler or socket is delayed after preflight. JPEG validation
and frame-ID checks occur before this decision. This is host behavior only;
receiver recovery from actual loss or incomplete frames remains necessary.

Two pinned-reference localhost tests used the Xonotic source described in
[xonotic-source.json](xonotic-source.json), at 720x480, 30 fps target and
fixed quality. They do not measure Wi-Fi or FPGA performance:

* **Impossible deadline:** 150 target slots, quality 75, 0.5 Mbps MSV1 cap,
  100 ms age bound. In 5.289 seconds the reference received zero complete
  frames and zero invalid datagrams. The sender wrote zero wire bytes, with
  149 encoded frames and one skipped slot. The feedback gate suppressed 119
  frames after no replies arrived. This tests no-wire behavior under these
  inputs, not network stability or quality adaptation.
* **Sustained overload:** 1,800 target slots, quality 20, 2 Mbps MSV1 cap,
  200 ms age bound. In 60.374 seconds the sender encoded 1,800 frames,
  replaced 1,083 waiting encoded frames, and the reference reassembled 717;
  there were no invalid datagrams or reply errors. Sent MSV1 traffic averaged
  1.689 Mbps; encoded JPEG payload averaged 4.168 Mbps. The pipeline stayed
  bounded by replacing stale work. This test does not imply 30 fps playback.

The JSONL and summary files remain in ignored local `artifacts/` as
`preflight-impossible-5s*` and `preflight-congestion-60s*`. Short regression
tests additionally exercise deadline feasibility, an already-delayed pacer,
early timer wakeups, and an injected late scheduler wakeup. The last can still
lead to an actual partial frame, and the receiver must handle it.
