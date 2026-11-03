# Moving game-footage host and localhost measurements

These runs use the first 30 seconds of [Xonotic gameplay on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Xonotic_0-8-2_gameplay.webm),
recorded by Drummyfish with Xonotic developers' game content, GPL version 3 or
later. The original file URL, license, 48,552,136-byte size and SHA-256 are in
[xonotic-source.json](xonotic-source.json). The original 1024x600, 30 fps input
has square pixels and is not exactly 16:9; the sender preserves its proportions
in a 691x405 viewport centered within the 720x480 canvas, with black borders.
The measured JPEG stream uses 8-bit YCbCr 4:2:0, baseline JPEG, quality 75.

Both runs used a 30 fps target, 20 Mbps MSV1 datagram cap, 200 ms host age
deadline, and 20..75 quality range. A Python reference reassembler from MoonBub
commit `75f8497b6ffefadd8c0403728b93ccfbbfa02f52` ran as a localhost UDP peer
and acknowledged each complete frame. The Windows native Sunshine build ran
concurrently and its CPU load was not controlled. These are host/localhost
measurements only: no Wi-Fi, ESP32, FPGA, display or end-to-end latency was
measured. The 300 ms final feedback grace period is included in each duration.

| Host clock | Duration | Captures submitted | JPEGs encoded | Peer accepted | Replaced raw / encoded | Sender wire bitrate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Windows GetTickCount64 | 30.344 s | 900 | 899 | 841 (27.72/s) | 1 / 58 | 9.16 Mbps |
| Windows QueryPerformanceCounter | 30.323 s | 900 | 899 | 863 (28.46/s) | 1 / 36 | 9.45 Mbps |
| High-resolution clock, one JPEG validation | 30.330 s | 898 | 897 | 875 (28.85/s) | 1 / 22 | 9.62 Mbps |
| Reproducible reference harness | 30.327 s | 900 | 899 | 880 (29.02/s) | 1 / 19 | 9.68 Mbps |

All reference runs had zero malformed packets, zero unacknowledged completed
frames, zero dropped log records and JPEG quality 75 throughout. In the first
two runs, mean encoded frame size was 40,372 bytes (p95 53,547; max 58,722). With the
high-resolution clock, encode duration was p50 4.49 ms and p95 5.95 ms; host
capture-to-last-datagram age was p50 51.84 ms, p95 78.39 ms and max 115.15 ms.
These are not display latency. The prior clock reported 15.625 ms resolution,
while `perf_counter` reports 0.1 microseconds. The results are separate runs
under changing build load, so the FPS difference is not a controlled estimate
of the clock change's impact.

The third run encoded 897 frames at quality 75; two pacing slots were skipped,
one raw capture and 22 waiting encoded frames were replaced. The mean encoded
JPEG was 40,356 bytes, p95 53,547 and max 58,722. Host completion age was p50
49.02 ms, p95 73.04 ms and max 181.56 ms. This path validates each actual JPEG
once, retains the verified immutable bytes, and packetizes them without repeating
software decode. Unmarked external JPEG bytes are still checked before sending.
Because load and capture samples differ, the run does not establish a causal FPS
improvement; it does confirm receiver-reference compatibility under this setup.

The fourth run used the checked-in `reference_loopback.py` command below. It
encoded 899 frames at quality 75, with 880 received and no malformed packets.
Host completion age was p50 46.93 ms, p95 72.04 ms and max 112.25 ms; sender
queue age was p50 0.37 ms and p95 19.16 ms. No physical playback is implied.

The source may be downloaded into ignored local artifacts for repeat testing:

```powershell
curl.exe -L --fail --output artifacts\media\Xonotic-0-8-2-gameplay.webm 'https://upload.wikimedia.org/wikipedia/commons/b/b9/Xonotic_0-8-2_gameplay.webm'
Get-FileHash artifacts\media\Xonotic-0-8-2-gameplay.webm -Algorithm SHA256
git clone --no-checkout https://github.com/AEW2015/moonbub.git C:\ai\moonbub-reference
py -3.11 -m uv run --locked python reference_loopback.py --reference-repo C:\ai\moonbub-reference --clip artifacts\media\Xonotic-0-8-2-gameplay.webm --log artifacts\xonotic-repeat.jsonl --frames 900 --fps 30 --mbps 20 --quality 75
```

Clone into a new path or point `--reference-repo` at an existing clone. The
harness reads the exact pinned revision through Git and verifies its source
hash before loading it. It binds only an ephemeral localhost receiver; use a
fresh log filename. Timings vary with machine load and later code changes.

The two detailed JSONL logs remain in ignored local artifacts, named
`stream-reference-xonotic-20261102.jsonl` and
`stream-reference-xonotic-perfclock-20261102.jsonl`; the third run is
`stream-reference-xonotic-single-validate-20261102.jsonl` and the fourth is
`xonotic-repro-20261102.jsonl`. The reference peer is a
host test harness, not a physical receiver.
