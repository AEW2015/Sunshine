# Continuous sender, pinned reference receiver on localhost

The continuous sender transmitted the first 150 frames of the 1080p/30 Big
Buck Bunny animation described in [bbb-source.json](bbb-source.json), scaled
and letterboxed to 720x480. A localhost UDP harness loaded
`host/moonshine/protocol.py` directly from MoonBub commit
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52`, used its `Reassembler`, and
returned MSF1 accepted feedback for each complete frame. This is a host-process
test of ingress compatibility, not ESP32, QSPI, FPGA decode, display, or Wi-Fi.

All 150 frames were sent and accepted; the reference counted zero invalid
datagrams and no feedback remained pending. The run lasted 5.313 seconds,
including the sender's 300 ms final feedback grace period: reported send FPS
was 28.23 using that duration. JPEG quality stayed at 75, with 2,891,845
encoded bytes and 3,007,765 MSV1 bytes (4.35 and 4.53 Mbps over the reported
duration). Capture-to-last-datagram age was p50 47 ms, p95 47 ms, maximum
94 ms; encoded-queue age was p50 0 ms, p95 0 ms, maximum 16 ms. The host
clock in this run was coarse at approximately 16 ms granularity. These are
host/localhost timings, not glass-to-glass latency. The source is animation,
not the requested detailed moving game footage.

Settings: 30 fps target, 20 Mbps MSV1 rate cap, 200 ms host age deadline,
quality range 20..75. Packet rate excludes UDP/IP/Wi-Fi overhead. Detailed
JSONL was written to the ignored local `artifacts/stream-reference-20261102.jsonl`;
it is not committed. The test peer did not simulate feedback loss or busy status.
