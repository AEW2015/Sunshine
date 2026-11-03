# Mass Effect combat JPEG sizes

**Offline software encode; 1493 frames at 25 samples/s. JPEG cap: 49,152 bytes (48 KiB), inclusive.**

| Pillow quality | Mean bytes | p95 bytes | Max bytes | Over cap | Over-cap rate |
|---:|---:|---:|---:|---:|---:|
| 35 | 15993 | 19964 | 22270 | 0/1493 | 0.00% |
| 50 | 18949 | 24179 | 26943 | 0/1493 | 0.00% |
| 65 | 22562 | 29410 | 32569 | 0/1493 | 0.00% |
| 75 | 26444 | 34968 | 38599 | 0/1493 | 0.00% |
| 80 | 29564 | 39497 | 43594 | 0/1493 | 0.00% |
| 85 | 34050 | 45957 | 50497 | 17/1493 | 1.14% |
| 90 | 41713 | 56944 | 62340 | 503/1493 | 33.69% |
| 95 | 58550 | 80681 | 87884 | 1078/1493 | 72.20% |

The cap applies to JPEG payload bytes only. MSV1 framing, UDP/IP overhead, timing, network transmission and receiver behavior are excluded.

Source SHA-256: `defff415bc1fdff6e18a70b0a0fbbddebb0429c5c0b8b5d5d04d8283bb315d3b`. Canvas: 720×480, centered 720×405 viewport with black letterbox. Encoder: Pillow baseline JPEG, 4:2:0, no restart markers, progressive scans or optimized Huffman tables. See `README.md` for the complete source and method caveats.
