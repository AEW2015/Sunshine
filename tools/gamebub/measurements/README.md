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
