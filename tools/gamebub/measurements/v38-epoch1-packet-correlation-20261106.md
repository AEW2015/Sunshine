# V38 epoch 1: trigger and unmatched-frame packet correlation

Saved-file analysis only; no further transmission. [Exact records](v38-epoch1-packet-correlation-20261106.json), [all 28 rejected IDs](v38-epoch1-matched-rejected-ids-20261106.txt), [full run summary](v38-epoch1-24fps-5mbps-720p-3008001-20261106.json).

## Run, source and capture

Actual sender duration **30.3811999 seconds**, MSV1 application wire rate **3.592175699419956 Mbps**, encoded rate **3.575081707026325 Mbps**. Wire excludes UDP/IP/Wi-Fi and AV, encoded includes replaced frames. Hybrid pacing used **windows-high-resolution**, requested/effective **600 us** tail, zero fallback/runtime failures.

720 target IDs 3,008,001-3,008,720: **718 encoded, 699 complete, 19 replaced, 0 partial, 2 skipped**. ACKs **670 accepted, 28 rejected, 1 unmatched (3,008,404)**. Complete rejected-ID list is linked above and embedded in JSON.

Converted clip SHA-256 **`9a369d9cbf06e4ddf3211bd1f9b185a1bb1e9d32073992d1d58f2e4570bef15f`**. Preparation: original 1024x600 Xonotic, SHA-256 `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`; crop **1024x576 at (0,12)** (12 rows top/bottom), Lanczos scale **1280x720**, SAR 1:1, libx264 **fast/CRF16/yuv420p**, video-only MP4 with faststart. Output **5,490 frames at 30 fps**,183 seconds, 236,464,457 bytes; all output and source frames decoded/count-matched before testing. Reproduction filter: `crop=1024:576:0:12,scale=1280:720:flags=lanczos,setsar=1`.

Run started at clip offset 0. Sender scaled live **1280x720 to 720x405 at (0,0)** in 720x480, padding 0 left / 0 top / 0 right / 75 bottom. The V37 control used original 1024x600 scaled691x405 at(0,0), padding29right/75bottom. Both host shifts were 0. **Source/scaling and app changed; this is not an isolated firmware comparison.** Local source H.264 is decoded on Windows; network MSV1 remains baseline JPEG Q25.

Wi-Fi Npcap interface 4 (`\Device\NPF_{B505491B-79C2-46D6-9030-5C95C2CA2B10}`), source 192.168.0.47:62353 to 192.168.0.157:5533. **16,221 captured/received,0 reported drops**, including pcap/dumpcap/flushed/ps_ifdrop 0. Capture covers exact STOP: frame 15,758, Unix 1793993585.762448000. Original pcap SHA and fresh tshark export were rechecked; all **699 complete JPEG CRCs** and contiguous increasing chunk orders passed again. Outbound capture is not RF/receiver receipt. Video/AV logger drops 0; no forced stop.

Host post-send times are monotonic seconds sampled after successful send API return. Npcap times are Unix seconds at the Windows interface. Each packet adds 40 MSV1 header bytes to the JPEG byte count below. Do not subtract across clock domains/machines.

## Frame 3,008,042

Header capture_us **1793993557061364**, JPEG **24,936 bytes**, **25 chunks**; declared/recomputed CRC32 **`5fd2b230`**, match.

| Offset | JPEG bytes | Host post-send seconds | Npcap Unix seconds | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 17,408 | 1,024 | 1488639.4847151 | 1793993557.142231000 | 944 |
| 18,432 | 1,024 | 1488639.4866436 | 1793993557.144153000 | 945 |
| 19,456 | 1,024 | 1488639.4884979 | 1793993557.146013000 | 947 |
| 20,480 | 1,024 | 1488639.4903401 | 1793993557.147862000 | 949 |

## Frame 3,008,404

Header capture_us **1793993572138906**, JPEG **18,205 bytes**, **18 chunks**; declared/recomputed CRC32 **`7058d110`**, match.

| Offset | JPEG bytes | Host post-send seconds | Npcap Unix seconds | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 15,360 | 1,024 | 1488654.5445345 | 1793993572.202049000 | 9369 |
| 16,384 | 1,024 | 1488654.5465374 | 1793993572.204071000 | 9372 |
| 17,408 | 797 | 1488654.5484047 | 1793993572.205897000 | 9373 |

## Frame 3,008,405

Header capture_us **1793993572192615**, JPEG **16,690 bytes**, **17 chunks**; declared/recomputed CRC32 **`fc400ae3`**, match.

| Offset | JPEG bytes | Host post-send seconds | Npcap Unix seconds | Pcap frame |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1,024 | 1488654.5555181 | 1793993572.213011000 | 9375 |
| 1,024 | 1,024 | 1488654.5575426 | 1793993572.214985000 | 9376 |

The next actually transmitted frame after 3,008,404 is **3,008,405**, established by pcap ordering. Last chunk to next SOF: host **7.1134000 ms**, Npcap **7.114000000 ms** (each clock independently).

## Receiver reconciliation

Operator reports 671 received/decoded/presented and 29 dropped, run deltas 670/670/670/29. **699 complete sends = 670 received + 29 dropped**. Queue drops 0,peak19/32,rejected_tails189; core completed671,drops25,faults/overflows/underruns0; STOP restoredPS1. Physical compact export passed 124 CRC/index checks. No explicit/compact disposition was retained for 3,008,404; its individual outcome remains unknown despite aggregate reconciliation. Sender remains stopped; camera finalized by receiver team.
