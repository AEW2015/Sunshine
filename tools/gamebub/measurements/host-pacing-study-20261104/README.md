# Windows pacing study and MoonBub correlation prompt

All new experiments in this study used **localhost only**. No handheld session,
audio, gamepad injection or installed Sunshine service was started or changed.
Production sender files remain unchanged. The high-precision wait below is an
artifact-only experiment, not the default or a deployed hardware change.

## Unchanged full-sender reproduction

The first 600 slots of the same saved Xonotic clip, offset zero, were sent to
the existing hash-checked Python transport reference at
`75f8497b6ffefadd8c0403728b93ccfbbfa02f52`. Settings: 720×480 canvas, 20 fps,
JPEG quality/minimum 25, 4 Mbps cap, 200 ms maximum age and packet logging.
Clip SHA-256:
`36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.

The unchanged sender produced 526 complete frames and 74 encoded replacements,
reproducing the recent hardware run's 525/75 outcome without Wi-Fi or FPGA.
This identifies a host-side throughput limitation; it does not explain the
hardware's two Sequence failures. The old Python transport reference does not
model v30, its queue, QSPI, FPGA admission or presentation.

## Isolating waits and sends

`wait_probe.py` sends a fixed valid Q25 JPEG through the unchanged `send_frame`
pacer and a measured socket wrapper to localhost. It measures requested wait,
wake overshoot, send-call duration and post-send deadline lateness. Four probes
run in sleep / candidate / candidate / sleep order, 80 frames and 1,440 packets
each. All 320 frames completed and were ACKed, with zero invalid datagrams.

In the two plain-sleep probes, median wake overshoot was 0.809 and 0.815 ms;
median socket-send duration was 0.020 and 0.021 ms. Median post-send gaps were
2.978 and 2.979 ms, versus a 2.128 ms nominal interval for a full 1,064-byte
MSV1 datagram at 4 Mbps. Waiting accounts for much more of the observed excess
than the socket send in these local measurements.

The experimental sleeper blocks until the last requested millisecond, then
busy-waits to its local deadline. Longer waits still delegate to the original
guarded sleeper, retaining its feedback-liveness checks. Packet pacing remains
relative to the preceding successful send; there is no catch-up packet burst.
Six deterministic tests cover short/zero waits, sleep-plus-tail, oversleep,
long-wait delegation and propagation of guarded-sleeper failure.

The candidate probes reduced median wake overshoot to approximately 0.0014 ms
and median post-send gaps to 2.152 and 2.154 ms. These are host measurements,
not NIC/RF timestamps. Probe logging and the local reference thread add overhead.

## Full-clip experiment

An artifact-only process adapter injected that sleeper into `stream_sender`'s
existing guarded wait callback. All other sender options stayed fixed, and
the same 600 source slots were encoded. Every slot's recorded encoded length
matched baseline; both encoded 11,959,521 bytes at Q25. Encoded payload hashes
were not recorded, so this is not a byte-for-byte encoded-stream assertion.

| Full localhost sender | Unchanged wait | Experimental spin tail |
|---|---:|---:|
| Encoded | 600 | 600 |
| Complete sends and accepted ACKs | 526 | 592 |
| Encoded replacements | 74 | 8 |
| Partial sends / skips / pending ACKs | 0 / 0 / 0 | 0 / 0 / 0 |
| Peer invalid datagrams | 0 | 0 |
| Duration including ACK drain | 30.377 s | 30.327 s |
| Complete-send fps including drain | 17.316 | 19.520 |
| MSV1 wire Mbps | 2.799 | 3.224 |
| Within-frame median gap | 2.984 ms | 2.158 ms |
| Within-frame p95 gap | 3.190 ms | 2.250 ms |
| Within-frame maximum gap | 4.572 ms | 3.849 ms |

Wire rates exclude UDP/IP/Wi-Fi overhead. Both loggers reported zero record
drops or write errors. The candidate still replaced eight frames, so this
does not qualify loss-free 20 fps, sustained throughput or 30 fps playback.

**CPU tradeoff:** the full candidate process consumed 14.828 CPU-seconds over
30.424 wall seconds, approximately 48.7% of one logical core. This includes
decoding, encoding, sender, logging and local peer threads. The original full
baseline did not capture process CPU, so it is not a measured CPU delta.
Probe CPU accounting was coarse; spin wall time is not equivalent to CPU time.
Concurrent AV input/audio and hardware playback were not exercised with the
candidate. No global Windows timer-resolution change was made.

Next host work: evaluate a lower-CPU precise wait and repeat controlled local
tests, including feedback/liveness and concurrent AV behavior, before enabling
an optional hardware pacing mode. Keep the default sender unchanged while
MoonBub correlates the two existing hardware failures. A hardware test must
identify the selected experimental wait explicitly and preserve the same clip,
v30/build50 configuration and recording coverage.

## MoonBub prompt

> Keep v30, build50, overlap and 32 slots unchanged; do not start another hardware
> run. Correlate the retained Sequence window for frames 2,013,421 and 2,013,422
> with the Windows packet records linked below. For 2,013,421, follow offsets
> 3,072, 4,096 and 5,120 through socket reception, enqueue, dequeue and assembly,
> including incoming and active frame IDs. Where is 4,096 last observed?
> For 2,013,422, determine whether SOF offset zero was received, admitted,
> rejected or absent before offset 1,024 reached an inactive assembler. Include
> nearby cleanup/reset events and queue occupancy. Match by frame ID, capture
> timestamp and offset; never subtract host/receiver monotonic clocks. Report
> trace gaps and unknowns explicitly. The host logged successful sends for all
> selected offsets and both SOFs. Localhost testing reproduced the host rate
> limit but did not reproduce the hardware Sequence failures. No receiver fix
> or new FPGA image is selected by this evidence.

[Exact hardware packet records](../v30-requested-packet-times-20261104.json) and
[reconciled hardware report](../v30-xonotic-20fps-4mbps-30s-20261104.md).

## Evidence and reproduction

`host-study-result.json` includes the environment, both full-run results,
full-run gap statistics and four wait-probe summaries. Source Python was 3.11;
use the existing GameBub lab `.venv` with PyAV/Pillow. The pinned MoonBub clone
must be present at `tools/gamebub/artifacts/moonbub-30fps-study` and the clip at
`tools/gamebub/artifacts/media/Xonotic-0-8-2-gameplay.webm`, as for prior tests.

Raw full-run JSONL and measured wait samples remain locally under
`tools/gamebub/artifacts/host-pacing-study-20261104/`: `baseline-video.jsonl`,
`candidate-video.jsonl`, `baseline-result.json`, `candidate-result.json`,
four `wait-probe-*.json` files and `wait-probe-summary.json`.

To reproduce without overwriting archived results, copy the four Python scripts
from this directory to a fresh direct child of `tools/gamebub/artifacts`.
From the repository root, first run the unchanged baseline with a fresh log:

```powershell
& tools/gamebub/.venv/Scripts/python.exe tools/gamebub/reference_loopback.py --reference-repo tools/gamebub/artifacts/moonbub-30fps-study --clip tools/gamebub/artifacts/media/Xonotic-0-8-2-gameplay.webm --log tools/gamebub/artifacts/NEW-STUDY/baseline-video.jsonl --frames 600 --fps 20 --mbps 4 --quality 25 --min-quality 25 --packet-timing --loop | Out-File -Encoding utf8 tools/gamebub/artifacts/NEW-STUDY/baseline-result.json
```

Run the copied `wait_probe.py`, then `candidate.py`, then `summarize.py`, each
with that same lab Python interpreter. Run `python -m unittest -v test_candidate`
from the copied script directory. Do not overlap benchmarks. Existing unchanged
MSV1 regression tests also passed: **27/27**. The spin-tail adapter remains lab
code, with no production configuration or deployed sender change.
