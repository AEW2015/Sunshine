# One-hour moving-footage localhost soak

The standalone sender at fork commit `f0614a5f` repeatedly opened the pinned
Xonotic source described in [xonotic-source.json](xonotic-source.json). The
1024x600 clip was scaled without distortion into the 720x480 canvas; output
was 8-bit baseline 4:2:0 JPEG. The target was 30 fps, a 20 Mbps MSV1 rate cap,
200 ms host age bound, and JPEG quality range 20..75. The receiver was the
hash-checked MoonBub Python reference at `75f8497b6ffefadd8c0403728b93ccfbbfa02f52`
on the same Windows machine. Code changes, tests, local experiments and other
host activity ran concurrently; this is not an isolated performance trial.

The run lasted 3,600.317 seconds including final feedback grace. Of 108,000
target slots, 42 were skipped; the pipeline submitted 107,958 frames, replaced
one raw frame and 1,205 waiting JPEGs, encoded 107,957, and sent 106,751
complete frames. One additional frame was partially sent and exceeded its
host deadline. The reference reassembled **106,751** frames, 29.650 fps over
the reported duration, with zero invalid datagrams and reply errors. Sender
quality was 75 for 107,805 encodes; after the partial send it fell to 70 and
recovered through 71–74. The sender reported no pending feedback, pipeline
exception or log error, and wrote all 321,462 event records.

Average JPEG payload was 9.511 Mbps and MSV1 datagrams 9.749 Mbps, excluding
UDP/IP/Wi-Fi overhead, audio and input. For complete frames, host-assigned
timestamp-to-final-send age had sampled p50 42.844 ms and p95 64.421 ms, with
exact maximum 164.835 ms. Encoded queue age had sampled p50 0.266 ms, p95
15.940 ms, and exact maximum 58.374 ms. Percentiles use nearest rank on a
reproducible uniform reservoir of 100,000 out of 106,751 observations; maxima
cover all observations. The host timestamp follows source retrieval, so these
are neither source capture nor display latency. Spot checks of the process's
private memory were approximately 44–51 MB; sparse samples cannot prove the
absence of a leak.

The JSONL, sender summary, and analyzer output remain in ignored local
`artifacts/xonotic-post-hardening-1h*` files. The clip repeats and the run used
the code loaded at startup, not later fork changes. No physical Wi-Fi, ESP32,
QSPI, FPGA, display, audio, or actual playback latency was tested.
