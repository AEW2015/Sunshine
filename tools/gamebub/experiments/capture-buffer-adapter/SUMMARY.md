# Synthetic canvas scaler comparison

All paths produce 720×480 RGB with 720×405 content and 37/38 black top/bottom rows.
PSNR and absolute channel error compare implementation outputs; they are not perceptual-quality scores.

| Pattern | Comparison | PSNR dB | MAE/channel | Max abs error | Changed channel fraction |
|---|---|---:|---:|---:|---:|
| gradient | C++ bilinear vs Pillow LANCZOS | 67.253 | 0.012 | 1 | 0.0122 |
| gradient | C++ bilinear vs PyAV/FFmpeg bilinear | 67.213 | 0.012 | 1 | 0.0124 |
| gradient | C++ area vs Pillow LANCZOS | 65.749 | 0.017 | 1 | 0.0173 |
| gradient | C++ area vs PyAV/FFmpeg bilinear | 66.597 | 0.014 | 1 | 0.0142 |
| gradient | C++ area vs C++ bilinear | 71.064 | 0.005 | 1 | 0.0051 |
| gradient | C++ optimized area vs double reference | 79.384 | 0.001 | 1 | 0.0007 |
| gradient | C++ optimized area vs Pillow LANCZOS | 65.935 | 0.017 | 1 | 0.0166 |
| gradient | C++ optimized area vs PyAV/FFmpeg bilinear | 66.627 | 0.014 | 1 | 0.0141 |
| gradient | Pillow LANCZOS vs PyAV/FFmpeg bilinear | 64.797 | 0.022 | 1 | 0.0215 |
| edge | C++ bilinear vs Pillow LANCZOS | 52.887 | 0.036 | 17 | 0.0059 |
| edge | C++ bilinear vs PyAV/FFmpeg bilinear | 46.092 | 0.051 | 32 | 0.0026 |
| edge | C++ area vs Pillow LANCZOS | 52.886 | 0.036 | 17 | 0.0059 |
| edge | C++ area vs PyAV/FFmpeg bilinear | 46.092 | 0.051 | 32 | 0.0026 |
| edge | C++ area vs C++ bilinear | 91.475 | 0.000 | 1 | 0.0000 |
| edge | C++ optimized area vs double reference | 91.475 | 0.000 | 1 | 0.0000 |
| edge | C++ optimized area vs Pillow LANCZOS | 52.887 | 0.036 | 17 | 0.0059 |
| edge | C++ optimized area vs PyAV/FFmpeg bilinear | 46.092 | 0.051 | 32 | 0.0026 |
| edge | Pillow LANCZOS vs PyAV/FFmpeg bilinear | 50.087 | 0.046 | 32 | 0.0069 |
| checker1 | C++ bilinear vs Pillow LANCZOS | 16.494 | 25.881 | 100 | 0.6667 |
| checker1 | C++ bilinear vs PyAV/FFmpeg bilinear | 16.457 | 26.123 | 100 | 0.6675 |
| checker1 | C++ area vs Pillow LANCZOS | 49.705 | 0.684 | 4 | 0.6783 |
| checker1 | C++ area vs PyAV/FFmpeg bilinear | 46.599 | 0.926 | 6 | 0.6776 |
| checker1 | C++ area vs C++ bilinear | 16.651 | 25.220 | 99 | 0.6783 |
| checker1 | C++ optimized area vs double reference | 67.461 | 0.012 | 1 | 0.0117 |
| checker1 | C++ optimized area vs Pillow LANCZOS | 49.779 | 0.672 | 4 | 0.6667 |
| checker1 | C++ optimized area vs PyAV/FFmpeg bilinear | 46.634 | 0.914 | 6 | 0.6661 |
| checker1 | Pillow LANCZOS vs PyAV/FFmpeg bilinear | 54.089 | 0.254 | 2 | 0.2535 |
| stripes4 | C++ bilinear vs Pillow LANCZOS | 21.713 | 14.912 | 50 | 0.6875 |
| stripes4 | C++ bilinear vs PyAV/FFmpeg bilinear | 22.065 | 11.763 | 49 | 0.3789 |
| stripes4 | C++ area vs Pillow LANCZOS | 27.059 | 7.846 | 27 | 0.6887 |
| stripes4 | C++ area vs PyAV/FFmpeg bilinear | 27.492 | 4.697 | 31 | 0.3131 |
| stripes4 | C++ area vs C++ bilinear | 23.721 | 7.069 | 47 | 0.1887 |
| stripes4 | C++ optimized area vs double reference | 62.446 | 0.037 | 1 | 0.0370 |
| stripes4 | C++ optimized area vs Pillow LANCZOS | 27.058 | 7.849 | 27 | 0.6875 |
| stripes4 | C++ optimized area vs PyAV/FFmpeg bilinear | 27.492 | 4.701 | 31 | 0.3164 |
| stripes4 | Pillow LANCZOS vs PyAV/FFmpeg bilinear | 27.002 | 7.795 | 27 | 0.6937 |

The 1-pixel checkerboard is above output Nyquist. Its low cross-path PSNR reflects different alias/filter/phase outcomes and is expected for this stress pattern. Four-pixel stripes also expose filter behavior. Smooth gradient differences are small; hard-edge maxima depend on the scaler. These controlled patterns do not show which output looks preferable in gameplay.

Synthetic inputs are not gameplay footage. No capture, JPEG, runtime throughput, display, receiver, or perceptual acceptance is tested. See `README.md` for exact reproduction commands.
