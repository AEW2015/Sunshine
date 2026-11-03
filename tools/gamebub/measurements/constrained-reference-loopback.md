# Quality backoff under a constrained localhost sender rate

This host-only test sent the first 150 frames of the pinned Big Buck Bunny
animation from [bbb-source.json](bbb-source.json), encoded as 720x480 4:2:0
baseline JPEG and sent over localhost to the MoonBub Python `Reassembler` at
commit `75f8497b6ffefadd8c0403728b93ccfbbfa02f52`. The harness acknowledged
complete frames and counted parser errors. This is not Wi-Fi throughput, FPGA
decode, displayed playback, moving game footage, or end-to-end latency.

Settings: 30 fps target, 2 Mbps MSV1 datagram pacing cap, 200 ms host age limit,
quality 20..75. The 5.375-second run includes the sender's 300 ms feedback grace
period. All 150 frames were encoded; 51 waiting encoded frames were replaced,
and 99 were sent and accepted (18.42 accepted frames/s using the full reported
duration). The reference parser reported zero malformed packets. JPEG quality
reached the minimum 20; 125 encodes were at quality 20 and 10 at 75, with the
remaining 15 at values between. Payload encoded: 1,547,428 bytes; MSV1 bytes
actually sent: 1,011,799 (1.51 Mbps over the reported duration). Host age at
completion had p50 94 ms, p95 125 ms and maximum 125 ms, subject to the host's
approximately 16 ms clock resolution. No claim about image quality is made.

This deliberate sender rate cap is a model of offered traffic; it does not
simulate wireless loss, receiver busy responses, or the other system's QSPI
backpressure. Per-frame JSONL is in ignored local
`artifacts/stream-reference-congested-20261102.jsonl`, not committed.
