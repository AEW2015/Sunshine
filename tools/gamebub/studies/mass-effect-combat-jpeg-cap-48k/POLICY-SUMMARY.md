# Single lower-quality retry comparison

**Offline only:** 1,493 frames at native 25 fps; initial q90, one q80 retry when q90 exceeds 49,152 bytes. No frames were transmitted.

| Policy | Sent | Dropped | Chosen qualities | Sent JPEG p95 / max bytes | Encode-validation ms/frame mean / p95 | Total encode-validation ms |
|---|---:|---:|---|---:|---:|---:|
| Drop-only | 990 | 503 (33.69%) | q90: 990 | 47493 / 49138 | 1.480 / 1.899 | 2,209 |
| One same-frame retry | 1,493 | 0 (0.00%) | q80: 503, q90: 990 | 46878 / 49138 | 1.942 / 3.241 | 2,900 |

The retry ran on 503 initial oversize frames and fit 503 at q80. It eliminated 503 drops in this sample. Total host encode-validation time increased by 31.2% in this run. Timings include Sunshine host JPEG inspection and software decode validation; they do not predict Windows frame deadlines.

The 48 KiB cap applies to JPEG bytes only; framing and transport overhead are excluded. See `README.md` for source, canvas, encoder profile and limitations.
