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
