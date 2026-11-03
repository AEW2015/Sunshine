# Latest fixed-quality moving-footage one-hour localhost soak

On November 3, 2026, the standalone sender repeatedly replayed the pinned
Xonotic source described in [xonotic-source.json](xonotic-source.json) to the
pinned MoonBub Python reference at revision
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52` on localhost. The 1024x600 source
was scaled without distortion into the 720x480 canvas and encoded as baseline
4:2:0 JPEG. Settings supplied at launch were 30 fps target, 20 Mbps MSV1 cap,
200 ms host age deadline, and fixed quality 75. These launch settings and sender
revision are operator-recorded; the older loaded sender did not log all of
them. Its latest sender-code commit at startup was `dc5a760b`. The source
recording repeats, and development, tests and other host activity were not
controlled, so this is not one hour of unique gameplay or an isolated benchmark.

The 3,600.307-second run included final feedback grace. Of 108,000 target slots,
two were skipped. The pipeline submitted and encoded 107,998 frames, replaced
516 waiting JPEGs, and sent **107,482** complete frames. The reference
reassembled **107,482**, or **29.854 fps** over the reported duration, with
zero invalid datagrams or reply errors. There were no incomplete sends, pending
feedback, reported pipeline error or log error. All 107,998 encodes used
quality 75. The separately returned sender summary reported 430,446 written log
records and zero dropped records; the JSONL summary alone lacks final logger
metadata.

Mean encoded JPEG payload was 9.515 Mbps, and sent MSV1 bytes averaged
9.831 Mbps over the reported duration. These exclude UDP/IP/Wi-Fi overhead,
audio and input. For complete sends, host-assigned timestamp-to-final-send
age had sampled median 37.644 ms and p95 55.961 ms, with exact maximum
145.407 ms. Encoded queue age had sampled median 0.210 ms and p95 11.532 ms,
with exact maximum 46.166 ms. Percentiles use nearest rank on a reproducible
uniform 100,000-observation reservoir out of 107,482; maxima include the full
population. Timestamps follow source retrieval and exclude earlier source and
capture wait; they are not display latency. Sparse process private-memory spot
checks were roughly 47–49 MB and cannot prove the absence of a leak.

The pinned local reference reports its invalid-datagram count in the feedback
`dropped_frames` field; that is not a physical dropped-frame counter and does
not count every abandoned incomplete frame. Logs, the sender summary and
analyzer output remain under ignored local `artifacts/xonotic-latest-1h*` files.
No physical Wi-Fi, ESP32, QSPI, FPGA, display, audio, or glass-to-glass latency
was tested. Reproduce with the [reference harness](../README.md), the pinned
source and a new log filename: `--loop --frames 108000 --fps 30 --mbps 20
--max-age-ms 200 --quality 75 --min-quality 75`.
