# Host and sender JPEG encoder comparison

**Offline full-clip byte comparison:** 1,493 frames at 25 fps.

| Quality | Identical JPEGs | Different JPEGs | Host size range | Sender size range | Sender minus host bytes |
|---:|---:|---:|---:|---:|---:|
| q80 | 1,493/1,493 | 0 | 6,027–43,594 | 6,027–43,594 | 0–0 |
| q90 | 1,493/1,493 | 0 | 6,027–62,340 | 6,027–62,340 | 0–0 |

Both functions emitted byte-identical JPEGs for every sampled frame in this run. This directly checks encoder output; it does not exercise sender quality adaptation, packetization, transmission, receiver or display.

Source SHA-256: `defff415bc1fdff6e18a70b0a0fbbddebb0429c5c0b8b5d5d04d8283bb315d3b`. Host encoder SHA-256: `94b42a1e7e81dab0aebad59472fe177a078760ef595a3d6b1e079fe6ff788bfa`. Sender encoder source SHA-256: `abbfe5021cdf60ab5908aae0583fcef40231869a0a25b7919eb238d9801a44d6`.
