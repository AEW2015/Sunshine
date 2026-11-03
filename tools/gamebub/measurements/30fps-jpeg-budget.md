# JPEG bandwidth needed for the 30 fps target

This is an **offline host encoding study**, not a receiver or Wi-Fi measurement.
It encodes the same 300 successive Xonotic gameplay samples, from seconds
10–20 of the pinned recording in [xonotic-source.json](xonotic-source.json), at
720x480 with the source proportions preserved. Each image was encoded as
baseline 8-bit 4:2:0 JPEG and checked against the receiver's current test
profile. The physical FPGA has not been tested with every quality below.

The mean rate is the mean JPEG size plus MSV1 chunk headers, multiplied by
30 frames/s and eight bits/byte. It excludes UDP/IP/Wi-Fi overhead, retries,
audio and input. The p95-frame rate is the rate that would serialize that
size of frame in 1/30 second; a pipeline can redistribute time across frames,
but that has queue and latency consequences. These are estimates for this
footage, not achievable network throughput.

| JPEG quality | Mean JPEG bytes | Mean MSV1 Mbps at 30 fps | p95-frame Mbps for 1/30 s | Mean RGB content PSNR |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 7,532 | 1.88 | 2.12 | 21.87 dB |
| 5 | 9,176 | 2.29 | 2.73 | 24.14 dB |
| 10 | 12,353 | 3.09 | 3.92 | 27.54 dB |
| 15 | 15,122 | 3.78 | 4.92 | 29.48 dB |
| 20 | 17,506 | 4.37 | 5.73 | 30.63 dB |
| 35 | 23,467 | 5.86 | 7.83 | 32.95 dB |
| 50 | 28,276 | 7.06 | 9.50 | 34.30 dB |
| 65 | 33,983 | 8.48 | 11.43 | 35.65 dB |
| 75 | 39,891 | 9.95 | 13.42 | 36.94 dB |

PSNR is the arithmetic mean of per-frame RGB PSNR over the picture area,
excluding black borders, compared with the scaled input before JPEG. It is an
objective error measure, not a perceptual quality judgment. The encoder's
quality value is not comparable across different encoders. At the confirmed
0.5 Mbps isolated-fixture setting, quality 1 still requires approximately 3.8
times that MSV1 rate on average for these samples; 0.5 Mbps was not established
as the physical link's maximum. Physical throughput and decoding at quality 1
remain unverified. The priority is to locate the sequence errors and measure
the ESP32/Wi-Fi/QSPI/FPGA path rather than select a lower quality by this table.

For context, the ten quality-75 live desktop captures in the prior **1 fps**
handheld diagnostic averaged 23,816 MSV1 bytes per frame. If those same ten
sizes occurred at 30 fps, their mean would be 5.72 Mbps; the largest would need
9.62 Mbps to serialize in 1/30 second. Ten slow captures are not representative
30 fps gameplay and cannot establish a bandwidth requirement for every game.

The exact summaries are [qualities 20–75](xonotic-quality-budget.json) and
[qualities 1–20](xonotic-quality-extremes.json). Reproduce from `tools/gamebub`
after the source download in [xonotic-loopback.md](xonotic-loopback.md):

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python quality_budget.py --clip artifacts/media/Xonotic-0-8-2-gameplay.webm --output artifacts/budget-normal.json --samples 300 --skip 300 --fps 30'
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python quality_budget.py --clip artifacts/media/Xonotic-0-8-2-gameplay.webm --output artifacts/budget-extreme.json --samples 300 --skip 300 --fps 30 --qualities 1 5 10 15 20'
```

Use new output paths for each run. These commands do not transmit video.
