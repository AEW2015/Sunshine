# Ten-minute moving-game localhost soak

The standalone sender used the Xonotic game recording documented in
[xonotic-source.json](xonotic-source.json), repeatedly reopened with the
`reference_loopback.py --loop` option. Its 1024x600 source was scaled without
distortion into a centered 691x405 viewport within the 720x480 canvas. JPEG
was baseline 8-bit YCbCr 4:2:0, with configured quality 20..75 and a 30 fps
target. The peer was the hash-checked MoonBub Python reassembler at revision
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52` on the same machine.

The run lasted **600.302 seconds**, including 300 ms feedback grace. Of 18,000
scheduled slots, 30 were skipped; all 17,970 submitted frames were encoded,
84 waiting JPEGs were replaced, and **17,886** complete frames were accepted
by the reference peer: **29.795 fps** over the reported duration. The reference
reported zero invalid datagrams and zero ACK send failures. Sender quality
remained **75** on every encode. The 20 Mbps limit applies to MSV1 datagrams;
measured encoded payload was **9.499 Mbps** and sent MSV1 bytes were
**9.813 Mbps**, excluding UDP/IP/Wi-Fi overhead. Mean encoded JPEG size was
39,666 bytes, p95 51,435 and max 69,838.

Host encode duration was p50 3.917 ms and p95 4.864 ms. Capture-to-final-send
age was p50 **42.728 ms**, p95 **60.078 ms**, max 164.814 ms. Encoded queue age
was p50 0.271 ms and p95 11.574 ms. These are host timestamps, **not display or
glass-to-glass latency**. The logger wrote 53,743 records (5,845,856 bytes)
with zero dropped records or reported I/O errors.

Windows process memory was sampled every ten seconds for the single process
containing both sender and reference peer. After the first minute, sampled
private bytes ranged from 43,692,032 to 49,967,104; at 60.06 seconds the sample
was 46,841,856, and at 590.51 seconds it was 47,144,960. Sampled peak working
set was 56,016,896 bytes. This ten-minute observation found no large sustained
growth, but it cannot prove absence of longer-term leaks. Short regression tests,
package setup, and ordinary background activity ran concurrently, so this is
not an isolated performance benchmark.

The full JSONL and 60 memory samples remain in ignored local artifacts
`xonotic-soak-10m.jsonl` and `xonotic-soak-10m-summary.json`. To reproduce the
traffic, follow the source and harness setup in [xonotic-loopback.md](xonotic-loopback.md)
and use `--frames 18000 --fps 30 --mbps 20 --quality 75 --loop`. Monitor the
actual Python process separately for memory. The recording repeats; it is not
ten minutes of unique gameplay. This was **localhost ingress only**: there was
no physical Wi-Fi, ESP32, FPGA, display, or end-to-end latency measurement.
