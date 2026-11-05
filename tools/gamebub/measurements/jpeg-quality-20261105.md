# Saved-clip JPEG size and software PSNR — 2026-11-05

This deterministic offline study encoded 60 unique native-decoded Xonotic frames
at JPEG qualities 20, 25, and 30 using the production `host.canvas` and
`msv1.encode_receiver_jpeg` path. It then decoded each JPEG to RGB8 with Pillow
and measured channel-wise PSNR. No timing was recorded.

The source is `Xonotic-0-8-2-gameplay.webm`, 48,552,136 bytes, SHA-256
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`. Native
PTS spans 7,000–1,974,000 μs, with no resampling or loop. The decoded source
geometry is 1024×600. Production canvas fitting scales it to 691×405 at
`x=14, y=37` on a 720×480 canvas. The host implementation rounds resized
dimensions with Python `round`: `round(1024 × 0.675) = 691` pixels. PSNR is
reported for the exact scaled content rectangle (excluding all letterbox), the
720×405 viewport (rows 37:442, including its 14-pixel left and 15-pixel right
side bars), and the whole canvas.

| JPEG quality | JPEG bytes / 60 frames | App UDP payload demand at 20 / 30 fps | Scaled content PSNR min / p5 / median | Active viewport PSNR min / p5 / median | Whole canvas PSNR min / p5 / median |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 1,097,759 | 3.045 / 4.568 Mbps | 28.804 / 29.030 / 30.420 dB | 28.942 / 29.168 / 30.544 dB | 29.585 / 29.811 / 31.144 dB |
| 25 | 1,233,242 | 3.420 / 5.130 Mbps | 29.708 / 29.986 / 31.417 dB | 29.847 / 30.118 / 31.537 dB | 30.493 / 30.762 / 32.154 dB |
| 30 | 1,353,939 | 3.755 / 5.632 Mbps | 30.384 / 30.726 / 32.243 dB | 30.522 / 30.860 / 32.368 dB | 31.176 / 31.510 / 32.982 dB |

The active viewport and whole-canvas PSNR are higher because those regions
include letterbox pixels; the scaled-content figure isolates the encoded image
pixels. The app-payload rates include JPEG bytes plus one MSV1 header per 1,024-byte
payload chunk. They are nominal demand estimates from this 60-frame sample at
20 or 30 fps, not achieved bitrates or a capacity result. Exact per-frame JPEG
and app-payload byte counts, timestamps, and per-frame PSNR values are in the
[machine-readable summary](jpeg-quality-20261105.json).

PSNR describes Pillow software-decode RGB8 error against the production canvas.
It is not FPGA-decoded-pixel evidence or a human visual assessment. The study
does not change the selected JPEG profile, sender quality, or hardware settings;
it does not establish sustained delivery or receiver presentation at either
nominal rate.
