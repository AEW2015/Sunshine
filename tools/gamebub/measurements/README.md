# Host-only measurements — 2026-11-02

**No end-to-end playback was tested. The 30 fps streaming target has not been
achieved.** No Wi-Fi, ESP32, QSPI, FPGA, or display timing is present in these
results. All resolution values are the encoded 720×480 canvas with a 720×405
16:9 viewport. Output is baseline JPEG, 4:2:0, fixed encoder Huffman tables,
no restart markers, maximum 262,144 compressed bytes. These are local experiment
settings, not an approved FPGA profile. JPEG quality is an encoder setting, not
a measured perceptual quality score.

Host: Intel Core i7-10875H, 8 cores/16 logical processors; installed Sunshine
service kept running. The software pipeline uses CPU encoding, not the NVIDIA
GPU. Python 3.11.9, Pillow 13.0.0, libjpeg-turbo 3.2.0, PyAV 18.1.0.
Dependencies are in `../uv.lock`. Each reported benchmark ran without coverage
or another benchmark; unrelated applications and the working Sunshine service
were not stopped. These are single exploratory runs, without confidence intervals.

| Input | Duration, s | Encoded fps | Modeled complete fps | Encoded Mbps | Quality min/median/max | Encode + validate p95, ms | Host completion age p95, ms |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Big Buck Bunny 1080p/30 first 30 seconds | 30.009 | 23.73 | 23.49 | 5.438 | 20/68/75 | 7.56 | 57.68 |
| Synthetic moving bars/fine detail | 30.028 | 20.18 | 19.85 | 6.962 | 20/39/75 | 11.56 | 58.68 |
| Desktop, primary display | 10.082 | 12.80 | 0 | 1.338 | 20/20/75 | 6.25 | No completed frames |
| Synthetic, deliberately overloaded 0.1 Mbps model | 9.994 | 29.92 | 0 | 7.380 | 20/20/75 | 7.69 | No completed frames |

The first three runs configured a 20 Mbps model; the overload run configured
0.1 Mbps. All used target 30 fps, maximum age 66.7 ms, initial quality 75,
minimum quality 20. Bitrates are **encoded payload**, including dropped frames;
they are not Wi-Fi throughput. Modeled completed payload rates were 5.381 Mbps
for Big Buck Bunny and 6.836 Mbps for synthetic; both zero for desktop/overload.
Modeled serialization has zero packet overhead and no errors or feedback.
Host age includes capture/read, scale, encode, validation, and simulated serial
link wait. It is not glass-to-glass latency. Receiver latency is unknown/null.
JPEG encode/validate timings exclude input preparation; they include the local
JPEG syntax inspector and a software decode, so are not pure encoder timings.

Big Buck Bunny: 712 encoded, 705 modeled completions, 7 stale drops, and 188
skipped pacing slots. Encoded JPEG size averaged 28,647 bytes, maximum 51,091.
Median host completion age was 39.81 ms, maximum 66.77 ms. Windows scheduling
can overshoot the predicted deadline. No capture/codec/file failures occurred.

Synthetic: 606 encoded, 596 modeled completions, 10 stale drops, 294 skipped
slots. Desktop: 129 encoded, all stale, 171 skipped slots. Deliberate overload:
299 encoded, all stale, one skipped slot, quality reached its configured floor.
No run accumulated waiting-frame queues. JSONL files contain each attempted
frame and sparse cumulative counters; skipped slots are recorded separately.

The serial experiment waits for modeled serialization before capturing another
frame. This bounds memory but prevents overlap of input preparation/encoding
with transmission. Its fps therefore cannot be read as an encoder ceiling or
as a prediction of a pipelined hardware receiver. The overload run drops before
waiting for serialization, explaining its higher encoded fps despite zero
modeled completions. A later sender needs bounded overlap and real receiver
credits. The desktop source also requires a faster capture path, such as the
existing Sunshine DXGI path, before its latency is suitable.

A subsequent fixed-quality, host-only overlap experiment is described in
[pipeline-overlap.md](pipeline-overlap.md); it is not a network or playback test.

An additional 30.04-second clip run using explicit bilinear video scaling is
recorded in [bbb-bilinear.json](bbb-bilinear.json). It encoded 738 frames at
24.57 fps and completed 732 at 24.37 fps in the same zero-overhead 20 Mbps
link model, with 162 skipped slots and 6 stale drops. Quality started at 75
and adapted between 20 and 75; encoded payload averaged 6.35 Mbps. Median and
95th-percentile host completion age were 38.49 and 56.69 ms. This is neither
Wi-Fi throughput nor receiver or display latency. The earlier fast-scan run
used the same source and settings, but ran separately and produced 23.95
modeled completions per second; scheduling and adaptive quality differ between
runs, so the difference is not a controlled throughput comparison.

In a separate sequential stage profile, 110 decoded clip frames (after 10
warm-up frames) were each converted from 1080p to 720x405 RGB using the PyAV
default, explicit bilinear, and fast-bilinear modes in that order. Mean times
were 13.86, 3.08, and 9.00 ms respectively. This excludes clip decoding and
the rest of the pipeline. Bilinear changes the resampled pixels and visual
quality has not yet been assessed on detailed moving gameplay or the display.

Big Buck Bunny is an animation baseline with opening/title material, not detailed
moving gameplay. Its input hash, pinned mirror URL, license, and attribution
are in [bbb-source.json](bbb-source.json); reproduction commands are in
[the laboratory README](../README.md#repeatable-big-buck-bunny-input).
(c) copyright 2008, Blender Foundation / www.bigbuckbunny.org, CC BY 3.0.
Blender's download server returned HTTP 403, so the Renesas RZ mirror was used.

Raw summaries and JSONL logs in this directory preserve these runs. The Big Buck
Bunny run uses the selected-frame libswscale preprocessing path; the synthetic
and desktop baselines predate that clip-only optimization. Earlier exploratory
Big Buck Bunny runs with full-resolution RGB conversion are excluded from this
table; they remain locally under ignored `artifacts/` for debugging.

## Marker scan and desktop filter experiments

The host now searches compressed bytes for JPEG marker prefixes in native code,
instead of visiting every byte in Python. It retains marker ordering and restart
checks, frame-size limits, and software decoding. In two consecutive uninstrumented
300-iteration runs on the same 71 KB synthetic JPEG, median inspection fell from
6.86 ms to 0.28 ms; median encode plus inspection and decode fell from 11.11 ms
to 4.42 ms. These single-machine timings are not pure encoder measurements.

A new uninstrumented 30.026-second Big Buck Bunny run used the same clip,
720×480 canvas, 30 fps target, 20 Mbps simulated link, initial quality 75, and
66.7 ms deadline as the baseline above. It encoded 732 frames at 24.38 fps;
719 met the modeled deadline (23.95 fps), 13 were stale and 168 slots skipped.
Encoded payload was 5.714 Mbps; encode plus validation was 4.42 ms at p95.
JPEG quality ranged 20–75; simulated host completion age was 56.72 ms at p95.
Run-to-run load and adaptive quality vary, so the 23.73-to-24.38 fps comparison
is an observation from two runs, not a controlled estimate of a speedup.
See `bbb-fast-scan.json` and `bbb-fast-scan-frames.jsonl` for the full record.

For one 1920×1080 desktop image, median Pillow screen capture was 36.44 ms;
median Lanczos resize was 28.72 ms and bilinear was 13.29 ms. The bilinear image
had 39.73 dB PSNR relative to Lanczos on that one desktop image. This is a
single-image difference metric, not a game-quality evaluation. It can soften
text and detail. A separate 10.054-second desktop run with `--desktop-filter
bilinear` encoded at 15.91 fps and had 13.13 fps simulated completions, 28 stale
frames and 140 skipped slots. Quality reached its minimum 20; encoded payload
was 1.596 Mbps and modeled host completion age was 65.68 ms at p95. The desktop
contents and host load were not controlled across runs. See
`desktop-bilinear.json` and `desktop-bilinear-frames.jsonl` for details.

All of these remain host-only results, with serialized simulated transmission;
no receiver, Wi-Fi, QSPI, or display timing has been measured. Capture and
resizing still take too long for the 30 fps target on this machine. The next
practical work is a faster capture path and a bounded capture/encode/transmit
pipeline once real transport and feedback are agreed.

The initial transport-independent media/button core was measured separately on
the same CPU, using Python 3.11.9, 100,000 single-thread iterations, and reused
immutable payload objects. Mean time per video put/take pair was 1.37 µs, per
audio put/take pair 3.99 µs, and per button snapshot 1.02 µs. The test used a
72,000-byte video payload and 1,024-byte audio payload; it did not copy payloads,
capture audio, encode video, process Wi-Fi, or exercise concurrent contention.
These timings do not establish streaming or input latency.

## Remaining acceptance evidence

- Decoder-approved capabilities, a mutually versioned wire specification, and
  receiver acknowledgments; none are available yet.
- Sustained 720×480 at 30 displayed fps using detailed moving gameplay, with
  agreed JPEG profile/quality, complete payload and wire bitrate, dropped-frame
  counts, glass-to-glass p50/p95/max, and test duration.
- Real congestion, loss, reordering, stale credits, decoder reset, and reconnect
  recovery with bounded memory and bounded time to a good displayed frame.
- Native candidate build, Sunshine extension negotiation, stock Moonlight
  pairing/launch/input/codec compatibility, and video-only behavior.
- Only after those pass: measure whether 60 fps is feasible.
