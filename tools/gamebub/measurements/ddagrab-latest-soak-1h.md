# Latest Desktop Duplication one-hour localhost soak

On November 3, 2026, the latest standalone sender at startup captured the live
Windows desktop using the experimental `ddagrab` backend, scaled it into the
720x480 canvas, encoded baseline 4:2:0 JPEG at fixed quality 75, and sent it
to the pinned MoonBub Python reference on localhost. The target was 30 fps,
a 20 Mbps MSV1 cap, and a 200 ms host age deadline. The desktop content was
uncontrolled, and the backend may repeat unchanged frames. No image frames
were saved. User activity, brief log inspections and development could share
the host; this is not an isolated benchmark or a fresh-game-frame measurement.

The run lasted 3,600.494 seconds including feedback grace. Of 108,000 target
slots, 70 were skipped. The remaining **107,930** frames were submitted,
encoded, sent and reassembled by the reference: **29.976 fps** over the
reported duration. The sender reported no replacements, incomplete sends,
remaining feedback, pipeline error or logging error. The reference reported
zero invalid datagrams and reply errors. The separately returned sender summary
reported 431,722 written records and zero dropped records; the JSONL summary
alone lacks that final logger metadata. Quality was 75 for every encode.

Average JPEG payload was 6.663 Mbps and MSV1 datagrams 6.929 Mbps, excluding
UDP/IP/Wi-Fi overhead, audio and input. Host-assigned timestamp-to-final-send
age for complete sends was sampled median 33.438 ms and p95 39.217 ms, with
exact maximum 134.905 ms. Encoded queue age was sampled median 0.182 ms and p95
0.266 ms, with exact maximum 10.259 ms. Each percentile used nearest rank on a
reproducible 100,000-observation uniform reservoir out of 107,930 sends; maxima
cover the full population. The host timestamp follows frame retrieval and
excludes any earlier capture wait or source-image age; it is not display
latency. Sparse private-memory spot checks were roughly 78–84 MB and cannot
prove the absence of a leak.

The log, sender summary and analyzer output remain in ignored local
`artifacts/ddagrab-latest-1h*` files. No physical Wi-Fi, ESP32, QSPI, FPGA,
display, audio, or glass-to-glass latency was exercised. For reproduction use
the [Desktop Duplication reference command](dxgi-desktop-probe.md) with
`--frames 108000 --quality 75 --min-quality 75` and a new log filename.
