# Sampled Mass Effect clip scaler comparison

Input: `mass-effect-2600.mp4`, SHA-256 `cf79e7bef47b242005eff912c9da40404aadcd3fb4154c7fd1a84ab95ecfd311`, 360 decoded frames (container reported 448) at 747/25 fps; sampled 24 uniformly.
Each path produces a 720×480 canvas with 720×405 content and 37/38 black top/bottom rows.
Pixel errors compare C++ optimized area output with existing host canvas paths; they do not rank perceived quality.

| Comparison | PSNR dB | MAE/channel | p50 abs error | p95 abs error | p99 abs error | Max abs error | Changed fraction |
|---|---:|---:|---:|---:|---:|---:|---:|
| Optimized area vs Pillow LANCZOS | 45.000 | 0.220 | 0 | 1 | 5 | 45 | 0.0890 |
| Optimized area vs PyAV/FFmpeg bilinear | 42.726 | 0.950 | 1 | 2 | 4 | 52 | 0.6267 |

| Canvas path | p50 ms | p95 ms | max ms |
|---|---:|---:|---:|
| C++ optimized area kernel | 9.942 | 12.452 | 13.229 |
| Pillow LANCZOS canvas | 11.568 | 13.135 | 16.180 |
| PyAV/FFmpeg bilinear canvas | 3.351 | 4.372 | 4.428 |

PSNR, absolute channel errors and CPU timings summarize only these sampled outputs and this host. C++ timing excludes helper process startup/raw-RGB pipe transfer; FFmpeg timing includes pixel-format conversion. No perceptual, end-to-end, live-capture or hardware claim is made.
See `README.md` for the exact source provenance and reproduction command. No video frames are stored in this report.
