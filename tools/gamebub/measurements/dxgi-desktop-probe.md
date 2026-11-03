# Exploratory DXGI desktop capture probe

This was a separate third-party **DXcam 0.3.0** Python experiment, not Sunshine's
capture implementation and not the Game Bub sender. It ran after the ten-minute
soak, in an ignored isolated virtual environment with Python 3.11.9, NumPy
2.4.6, Pillow 13.0.0 and PyAV 18.1.0. No package was added to the fork's
dependencies. The DXGI primary output was Intel UHD Graphics at 1920x1080.

Over 300 requested capture/scale/encode attempts, the DXcam one-shot API
reported 300 fresh desktop updates and zero `None` returns. The run took
11.642 seconds, about 25.77 completed attempts per second; the desktop was not
a controlled moving game scene. Copying each fresh 1920x1080 RGB image took
p50 4.342 ms and p95 6.005 ms. Pillow bilinear scaling to 720x405, pasting
into 720x480, and saving JPEG quality 75 took p50 32.405 ms and p95 39.145 ms
(max 360.878 ms including first-use costs). This exploratory encode used
baseline/4:2:0 settings but did not run the sender's strict bitstream validator.
No packets or receiver were involved; numbers are not display latency.

A separate single-desktop-image scaling microbenchmark, 150 iterations after
10 warm-ups, compared Pillow RGB bilinear resize and PyAV RGB-to-RGB bilinear
conversion. Pillow measured p50 21.080 ms and p95 27.843 ms; the PyAV path,
including constructing a video frame from the RGB array, measured p50 28.937 ms
and p95 34.237 ms. The resulting pixels differed; visual quality on moving
gameplay was not evaluated. The PyAV test process printed an ignored COM
`Release` access-violation exception during DXcam cleanup even though it exited
zero. This warning is a reason not to treat the third-party probe as a tested
capture backend for the product.

Another 110-iteration static-desktop resize run, after ten warm-ups per filter,
measured Pillow bilinear p50 14.775 ms/p95 16.869 ms and BOX p50 10.776 ms/p95
14.762 ms. BOX's mean absolute per-channel pixel difference from bilinear was
about 1/255 on that one image, with much larger maximum differences. NEAREST
was faster but had substantially larger pixel differences. These fixed-order,
single-image microbenchmarks do not prove visual equivalence or predict moving
game performance. The standalone sender now offers the **opt-in** BOX desktop
filter (`--desktop-filter box`); its default remains bilinear. Actual Sunshine DXGI integration, device
loss, fullscreen behavior and visual quality remain untested.

As a separate end-to-end **host/localhost ingress** check, the current Pillow
ImageGrab sender was run sequentially for 300 target slots per filter against
the pinned Python reference receiver at a 20 Mbps MSV1 cap and 200 ms age bound.
For bilinear, 169 frames were accepted over 10.365 s (16.31 fps), 131 slots
were skipped, wire bitrate was 3.46 Mbps, and host age was p50 109.06 ms/p95
121.48 ms. For BOX, 180 frames were accepted over 10.392 s (17.32 fps), 120
slots were skipped, wire bitrate was 4.20 Mbps, and host age was p50 113.41
ms/p95 144.51 ms. Quality stayed at 75; both runs had no invalid datagrams or
dropped log records. These sequential runs used whatever was on the live
desktop, not identical prerecorded content; they do not establish a reliable
filter speedup or equivalence. They include the sender and localhost peer, not
DXcam, Wi-Fi or physical playback. Both leave substantial work to reach 30 fps.

A separate November 2026 exploratory probe used PyAV 18.1.0's FFmpeg
`ddagrab` filter, D3D11 readback as BGRA, the existing `canvas()` libswscale
path, and `encode_receiver_jpeg()` at quality 75 (including its JPEG
validation). With the active desktop at 1280x720, it produced 301 frames in
10.022 seconds (30.03 fps), with median scaling plus encoding of 16.52 ms,
maximum 40.91 ms, and mean JPEG size 29,863 bytes. The source was the live
desktop, not controlled footage; `dup_frames=1` permits repeated frames, and
this does not establish 30 fresh game frames per second. No packetization,
Wi-Fi, receiver or display was involved. The pipeline is a probe, not a
supported sender backend. Device loss, game capture behavior, and sustained
performance need testing. The separate attempt to use `scale_d3d11` at 720x405
failed to create its output texture; the reason was not established.

Reproduce from `tools/gamebub`: save the following as `artifacts/dxgi-probe.py`,
then run `C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c
'py.exe -3.11 -m uv run --locked python artifacts/dxgi-probe.py'`. This captures
the desktop but does not save the images or send them to a receiver.

```python
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import av
from host import canvas
from msv1 import encode_receiver_jpeg

source = "ddagrab=framerate=30:dup_frames=1:draw_mouse=0,hwdownload,format=bgra"
with av.open(source, format="lavfi") as capture:
    start = time.perf_counter()
    work_ms, sizes = [], []
    for frame in capture.decode(video=0):
        before = time.perf_counter()
        jpeg = encode_receiver_jpeg(canvas(frame), 75)
        work_ms.append((time.perf_counter() - before) * 1000)
        sizes.append(len(jpeg))
        if time.perf_counter() - start >= 10:
            break
    elapsed = time.perf_counter() - start
    print(f"frames={len(work_ms)} seconds={elapsed:.3f} fps={len(work_ms) / elapsed:.2f}")
    print(f"work_ms_median={statistics.median(work_ms):.2f} max={max(work_ms):.2f}")
    print(f"jpeg_mean_bytes={statistics.mean(sizes):.0f}")
```

The experimental `--desktop-backend ddagrab` is now available in the standalone
sender. In a subsequent run of the actual sender and pinned localhost reference
receiver, 293 of 300 target slots were submitted, encoded, sent, and reassembled;
seven capture slots were skipped and the reference reported no invalid datagrams.
The sender duration was 10.318 seconds including final feedback grace, and its
reported send rate was 28.40 fps, 6.96 Mbps of MSV1 traffic, with quality 75
throughout. The desktop content was uncontrolled and `ddagrab` may repeat
unchanged frames. This result exercises host capture, encoding, packetization,
and localhost ingress only, not the physical Wi-Fi, QSPI, FPGA, or display.
Capture-device loss exits with an error; automatic reinitialization remains work.

Reproduce with a pinned MoonBub reference clone and a new log filename:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python reference_loopback.py --reference-repo /c/ai/moonbub-reference --desktop --desktop-backend ddagrab --frames 300 --fps 30 --mbps 20 --max-age-ms 200 --quality 75 --min-quality 20 --log artifacts/ddagrab-reference-new.jsonl'
```
