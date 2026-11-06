# V37 hybrid600 Sequence windows — 2026-11-06

Saved run IDs **3,004,000–3,004,749**, .47:60461 → .157:5533. No new transmission.

[Machine-readable records](v37-hybrid600-sequence-windows-20261106.json) preserve exact timestamps, pcap frame numbers, CRCs, hashes, gaps and receiver context.

## Frame identity and whole-frame integrity

| Incoming frame | Header capture_us | JPEG bytes | Captured chunks | Expected / actual JPEG CRC32 |
| --- | ---: | ---: | ---: | --- |
| 3,004,035 | 1793988652586409 | 22,248 | 22 | `9c18cc7d` / `9c18cc7d` |
| 3,004,411 | 1793988667623340 | 16,663 | 17 | `819d2db1` / `819d2db1` |
| 3,004,542 | 1793988672866950 | 16,424 | 17 | `8f007c31` / `8f007c31` |
| 3,004,543 | 1793988672903899 | 15,922 | 16 | `d2969db8` / `d2969db8` |
| 3,004,572 | 1793988674065163 | 17,058 | 17 | `790aeed8` / `790aeed8` |
| 3,004,580 | 1793988674386113 | 16,826 | 17 | `0b2bbfb1` / `0b2bbfb1` |

Each of the six frames is complete, has increasing captured chunk order and passes its whole-JPEG CRC. Expected CRC is the value declared in the captured MSV1 headers; actual CRC is recomputed over the reassembled compressed JPEG. These are not decoded-pixel checks or claims about RF arrival or receiver admission.

## Requested packet records

Lengths below are JPEG chunk payload bytes; add 40 bytes for the MSV1 header. Send times are host monotonic seconds sampled after the send API. Npcap times are Unix seconds. No clock domains are subtracted.

### Frame 3,004,035

Receiver reported expected **1,024**, observed **4,096**; active assembler ID and per-stage history were not retained.

| Offset | Payload bytes | Host send API s | Npcap Unix s | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1,024 | 1483734.9627505 | 1793988652.620253000 | 686 |
| 1,024 | 1,024 | 1483734.9650630 | 1793988652.622552000 | 687 |
| 2,048 | 1,024 | 1483734.9677354 | 1793988652.625186000 | 688 |
| 3,072 | 1,024 | 1483734.9701472 | 1793988652.627608000 | 689 |
| 4,096 | 1,024 | 1483734.9728000 | 1793988652.630300000 | 690 |

### Frame 3,004,411

Receiver reported expected **6,144**, observed **7,168**; active assembler ID and per-stage history were not retained.

| Offset | Payload bytes | Host send API s | Npcap Unix s | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 5,120 | 1,024 | 1483750.0125925 | 1793988667.670121000 | 7,915 |
| 6,144 | 1,024 | 1483750.0152294 | 1793988667.672759000 | 7,916 |
| 7,168 | 1,024 | 1483750.0176792 | 1793988667.675193000 | 7,917 |

### Frame 3,004,542

Receiver reported expected **6,144**, observed **7,168**; active assembler ID and per-stage history were not retained.

| Offset | Payload bytes | Host send API s | Npcap Unix s | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 5,120 | 1,024 | 1483755.2403980 | 1793988672.897940000 | 10,511 |
| 6,144 | 1,024 | 1483755.2426183 | 1793988672.900158000 | 10,512 |
| 7,168 | 1,024 | 1483755.2449445 | 1793988672.902446000 | 10,513 |

### Frame 3,004,543

Receiver reported expected **1,024**, observed **2,048**; active assembler ID and per-stage history were not retained.

| Offset | Payload bytes | Host send API s | Npcap Unix s | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1,024 | 1483755.2663707 | 1793988672.923918000 | 10,525 |
| 1,024 | 1,024 | 1483755.2685832 | 1793988672.926126000 | 10,527 |
| 2,048 | 1,024 | 1483755.2709069 | 1793988672.928394000 | 10,528 |

### Frame 3,004,572

Receiver reported expected **13,312**, observed **14,336**; active assembler ID and per-stage history were not retained.

| Offset | Payload bytes | Host send API s | Npcap Unix s | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 12,288 | 1,024 | 1483756.4749043 | 1793988674.132448000 | 11,148 |
| 13,312 | 1,024 | 1483756.4771441 | 1793988674.134669000 | 11,149 |
| 14,336 | 1,024 | 1483756.4796384 | 1793988674.137176000 | 11,150 |

### Frame 3,004,580

Receiver reported expected **6,144**, observed **7,168**; active assembler ID and per-stage history were not retained.

| Offset | Payload bytes | Host send API s | Npcap Unix s | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 5,120 | 1,024 | 1483756.7873790 | 1793988674.444912000 | 11,307 |
| 6,144 | 1,024 | 1483756.7896351 | 1793988674.447157000 | 11,308 |
| 7,168 | 1,024 | 1483756.7918842 | 1793988674.449411000 | 11,310 |

## Duration, pacing and packet gaps

Actual video sender lifetime including feedback drain: **30.3740074 seconds**. The source-slot window was 30 seconds. Pacing was explicitly hybrid, actual backend `windows-high-resolution`, effective tail 600 µs, fallback calls 0. MSV1 application wire rate was 3.298211878 Mbps; encoded rate was 3.938816713 Mbps and includes replaced frames. UDP/IP/Wi-Fi and AV traffic are excluded from those rates.

Full-to-full gaps below include only adjacent 1024-byte JPEG payload chunks within one frame, excluding boundaries/short tails. Percentiles use nearest rank. The JSON also retains all-within-frame, short-tail and frame-boundary distributions.

| Clock / observation | Samples | Median ms | p95 ms | p99 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Host post-send API | 10,827 | 2.3441 | 3.3575 | 4.5947 | 7.1564 |
| Npcap interface | 10,827 | 2.3330 | 3.3180 | 4.6600 | 7.9460 |

## Capture coverage and reconciled outcomes

Capture was active before AV/media, covered all 622 sent frames and exact STOP, and reached natural finite finalization with no forced stop. It recorded 15,112 packets received/captured and **zero capture drops** on Wi-Fi; both logger drop counts were 0. The prior full-run check reconstructed all 622 frames from 12,070 outbound MSV1 datagrams with valid JPEG CRCs and increasing within-frame chunk order.

STOP is captured at pcap frame 14,642, Unix `1793988681.599370000`. AV/media ended `2026-11-06T18:11:21.600031Z`; capture finalized `18:13:21.856794Z`. Its post-STOP tail was 119.125 seconds. Capture point is Windows Npcap, not RF.

Host: 750 encoded = 622 complete + 128 replaced, zero partial/skipped; 622 = 616 accepted ACKs + 6 rejected, zero pending. Receiver-reported final totals 1129/1129/1129/7 reconcile with increases 616/616/616/6. Application queue drops were 0; the 26/32 peak is cumulative, not run-specific. Core faults/overflows/underruns/transport overflows were 0; STOP restored power saving to 1 with zero errors.

All 20 requested chunks are present at the host capture point. The six frame-rejection outcomes are known; receiver active ownership and each packet's fate after that observation remain unknown. No Busy cause, radio loss location, socket receipt or admission decision is inferred from absent stage history.

Pcap SHA256: `f187025b2aadf6eb1185b132427ec40951931f73827a9d95b0db28dcdcb9e88a`. Raw evidence: `artifacts/hardware-25fps-hybrid600-v37-20261106-3004000/`. The JSON records source/export hashes and all receiver-scope limitations.
