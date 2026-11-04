# Windows JPEG capacity and retry validation, 2026-11-03

The candidate is on `gamebub/windows-jpeg-retry-20261103`, based on
`5215204317986b1eec7e4fb051a81cd04606afbd` plus working-tree changes. It retains
the active host's capture recovery, pacing and feedback behavior. The installed
Sunshine service was not replaced or restarted. No integrated Sunshine JPEG,
audio or Windows controller mode is enabled by these changes.

## Implementation and regression evidence

The sender has an optional local JPEG byte limit and one optional lower-quality
retry. Capacity rejection is distinct from ordinary codec/format failure. An
initial encode above the protocol's 262,144-byte limit can now reach the retry;
the final candidate must still satisfy the strict JPEG validator and configured
capacity. No JPEG is truncated and MSV1 packet bytes are unchanged.

The pipeline passes capture metadata to the encoder so it can check the original
age deadline before encoding, before retry, and after encoding. It cannot cancel
an already running codec call. A successful retry reduces subsequent adaptive
quality without undoing more conservative concurrent feedback pressure.

All **200 regression tests passed**, including pinned Rust receiver parser and
Python reassembler integration tests. The combined coverage run plus documented
CLI entry checks reached **100% statement and branch coverage**: 1,998 statements
and 648 branches, with no misses or partial branches. Ruff check and format
checks passed. These are lab tests, not a full Sunshine build or stock-client
playback compatibility test.

A deterministic 720x480 noisy RGB input initially exceeds 256 KiB at quality 95;
quality 75 fits. The regression proves the retry produces a strictly validated
JPEG and that the real pipeline sends its complete bytes and CRC over localhost.
Other cases cover custom capacity, failed/disabled/minimum-quality retries,
invalid output, expired deadlines, concurrent quality changes and CLI forwarding.

Validation artifacts in `tools/gamebub/artifacts`:

- `retry-final-regressions.txt`
- `retry-coverage-report.txt`
- `retry-cap-soak-20261103-provenance.json`

Use the [laboratory setup](../README.md) and its pinned reference/dependency
instructions. From `tools/gamebub`, the regression command is:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'MOONBUB_REFERENCE=C:/ai/moonbub-reference py.exe -3.11 -m uv run --locked python -m unittest -q'
```

## Measurement scopes

The ten-minute localhost run uses repeated prerecorded Xonotic gameplay and an
experimental 49,152-byte JPEG capacity. That capacity has not been selected for
the physical receiver. The source hash and license are in
[xonotic-source.json](xonotic-source.json).

The separate physical comparison retains the deployed 262,144-byte limit with
retry disabled, quality fixed at 25, a 5 fps target and a 2 Mbps MSV1 cap. Its
operator-reported starting receiver counters are 2,809 received/decoded/presented
and 282 dropped. Firmware is the overlap/dimension-boundary candidate built
2026-11-03 (exact hash not supplied), FPGA v9 serialized with overlap disabled,
and a 32-slot queue reported empty with zero packet drops since session restart.

Localhost ingress cannot establish physical Wi-Fi, QSPI, FPGA decode, display
FPS or game-to-photon latency.

## Ten-minute capacity-limited localhost soak

| Measurement | Result |
| --- | --- |
| Duration | 600.296 seconds including shutdown/grace |
| Canvas / target | 720x480 / 30 fps; source fitted to 691x405 without distortion |
| Scheduled / submitted / skipped | 18,000 / 18,000 / 0 |
| Encoded / complete sends / reference completions | 17,999 / 17,998 / 17,998 |
| Achieved reference ingress rate | 29.9819 fps |
| Capacity-triggered retries | 59; 58 succeeded and one remained oversized |
| Other frame disposal | One waiting JPEG replaced |
| Invalid datagrams / reply errors | 0 / 0 |
| JPEG bitrate / MSV1 datagram bitrate | 8.504 / 8.841 Mbps |
| Encoded quality range / final quality | 45..84 / 75; configured initial quality 90 |
| Chosen JPEG bytes p50 / p95 / maximum | 35,163 / 44,745 / 49,142 |
| Successful encode/validation ms p50 / p95 / maximum | 2.411 / 2.939 / 18.905 |
| Host post-retrieval-to-final-send age ms p50 / p95 / maximum | 29.395 / 37.853 / 64.296 |
| Logger records / drops / I/O errors | 72,115 / 0 / none |

The rejected frame was ID 16054: its quality-69 retry was 49,430 bytes, above
the 49,152-byte guard. No packets from that rejected frame were sent. This is
safe capacity enforcement, but the run did not deliver every scheduled frame.
The other unsent scheduled frame was a replaced waiting JPEG. The
local reference acknowledged complete ingress, not decode or presentation.

The JPEG bitrate includes successfully encoded frames, including the waiting
JPEG that was replaced; MSV1 bitrate counts actually sent datagram bytes. Neither
includes UDP/IP or Wi-Fi overhead. Quality numbers are encoder settings, not a
perceptual quality score. The source is prerecorded gameplay repeated across
the run, not live desktop capture or ten minutes of unique source content.

Thirty process-memory samples at 15-second intervals were collected partway
through the run, from 15:20:16 to 15:27:31 UTC. Private bytes ranged from
47,013,888 to 49,434,624; first/last were 49,074,176 / 48,975,872. This covers
the sender and reference peer together, excludes startup, and does not prove
absence of longer-term leaks. Regression checks ran concurrently during part
of the soak; this is not an isolated performance comparison.

Additional ignored local artifacts:

- `retry-cap-soak-20261103.jsonl`
- `retry-cap-soak-20261103-summary.json` (contains final logger integrity)
- `retry-cap-soak-20261103-analysis.json`
- `retry-cap-soak-20261103-metrics.json` (exact full-log quantiles)
- `retry-cap-soak-20261103-memory.jsonl`

From `tools/gamebub`, with fresh output paths:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked python reference_loopback.py --reference-repo C:/ai/moonbub-reference --clip artifacts/media/Xonotic-0-8-2-gameplay.webm --loop --frames 18000 --fps 30 --mbps 20 --quality 90 --min-quality 20 --max-jpeg-bytes 49152 --jpeg-retry-quality-drop 10 --max-age-ms 200 --log artifacts/retry-cap-soak-20261103.jsonl > artifacts/retry-cap-soak-20261103-summary.json'
```

## Physical comparison reproduction

The physical run uses the same repeating source helper and parameters as the
previous 32-slot run, with new IDs. After checking the receiver's accepted host
and counters, save this script in `tools/gamebub` and run it there under the
documented MSYS2/UCRT64 Python environment. Choose new frame IDs and log paths
for a repeat; `run` refuses to overwrite an existing frame log.

```python
import json
from pathlib import Path
from types import SimpleNamespace

from reference_loopback import loop_clip
from stream_sender import run

clip = Path("artifacts/media/Xonotic-0-8-2-gameplay.webm")
args = SimpleNamespace(
    target="192.168.0.157",
    port=5533,
    source_port=55534,
    start_frame_id=3617,
    frames=1500,
    fps=5,
    mbps=2,
    max_age_ms=200,
    quality=25,
    min_quality=25,
    max_jpeg_bytes=262144,
    jpeg_retry_quality_drop=0,
    packet_timing=True,
    clip=clip,
    desktop_backend="imagegrab",
    desktop_filter="bilinear",
    log=Path("artifacts/handheld-xonotic-5fps-5m-retry-candidate-20261103.jsonl"),
)
print(json.dumps(run(args, loop_clip(clip, args.fps)), indent=2))
```

This uses decoded prerecorded video, not ImageGrab or live Desktop Duplication;
`source_backend` is recorded as `provided_iterator` in the sender log.

## Five-minute physical sender result

| Measurement | Result |
| --- | --- |
| Source / destination | 192.168.0.47:55534 to 192.168.0.157:5533 |
| Duration / frame IDs | 300.220 seconds / 3617..5116 |
| Canvas / target / fixed JPEG quality | 720x480 / 5 fps / 25 |
| Submitted / encoded / completely sent | 1,500 / 1,500 / 1,500 |
| Skipped / suppressed / pending feedback | 0 / 0 / 0 |
| Accepted / rejected feedback | 1,485 / 15 |
| Heartbeats / unmatched feedback | 1,397 / 19 |
| Final received / dropped counters in feedback | 4,294 / 297 |
| Known-baseline received / dropped delta | +1,485 / +15 |
| Independently reported decoded / presented delta | +1,485 / +1,485 |
| Application-queue packet drops / high-water | 0 this session / 26 of 32 slots |
| Last receiver-completed frame | 5116 |
| Host sent FPS / receiver ingress FPS | 4.996 / 4.946 |
| JPEG / MSV1 datagram bitrate | 0.783 / 0.814 Mbps, below the 2 Mbps cap |
| JPEG bytes p50 / p95 / maximum | 19,118 / 25,561 / 33,088 |
| Host post-retrieval-to-send age ms p50 / p95 / maximum | 100.630 / 131.661 / 171.235 |
| Consecutive host packet-send gaps ms minimum / p50 / p95 / maximum | 4.293 / 4.982 / 5.194 / 5.946 |
| Logger records / drops / I/O errors | 8,900 / 0 / none |

The sender's automatic counter-delta total is 1,484 completed frames because its
first feedback establishes a baseline after the first completion. The independent
operator-supplied pre-run baseline gives the full +1,485 delta. Do not add these
two counts together. Feedback establishes ingress only. The operator subsequently
reported independent receiver totals of 4,294 received, decoded and presented,
and 297 dropped: each of the three successful stages increased by 1,485, while
drops increased by 15. These account for all 1,500 outcomes. This is receiver-
counter evidence of 4.946 presented fps across the host run duration; it does
not measure presentation intervals or game-to-photon latency. The reply did
not independently confirm visible motion for this run.

The application queue reported zero packet drops since session restart and a
high-water mark of 26/32. Application-queue overflow is therefore not supported
as the cause of this run's 15 frame losses. This does not rule out loss before
that queue, reordering, protocol rejection, timeouts or another receiver stage.
The handheld remained on FPGA v9 serialized mode; newer candidates were not
installed for this run.

Receiver-rejected feedback IDs:
`3630, 3874, 3878, 3880, 3882, 3885, 4187, 4199, 4511, 4816, 4818, 4820, 4822, 4824, 4826`.
Every corresponding host send completed within its deadline. The host log does
not establish packet arrival timing or the reason for receiver loss.

The earlier 32-slot run reported 1,487 accepted and 13 rejected responses from
1,500 sends. The new run has a 1.00% rejection rate versus 0.87% previously.
These sequential runs used different receiver firmware and uncontrolled Wi-Fi;
the two-frame difference does not establish a regression or an improvement.
The JPEG byte and MSV1 byte totals match the previous run exactly, supporting
that the prerecorded source and fixed-quality output were comparable.

Do not raise the physical frame rate yet. Match these IDs to the receiver's
per-frame failure reason, first expected/observed offsets, datagram arrival
timestamps and QSPI/decode trace. Start with frame 3630 and the cluster
3874..3885. Distinguish sequence, CRC, timeout, capacity and FPGA failures;
collect network-stack/driver drop counters where available. The host already
retains every sent offset/timestamp for these IDs. Host send completion and
spacing do not prove delivery or locate a loss before the application queue.

Physical artifacts under `tools/gamebub/artifacts`:

- `handheld-retry-baseline-20261103.json`
- `handheld-xonotic-5fps-5m-retry-candidate-20261103.jsonl`
- `handheld-xonotic-5fps-5m-retry-candidate-20261103-summary.json`
- `handheld-xonotic-5fps-5m-retry-candidate-20261103-analysis.json`
- `handheld-xonotic-5fps-5m-retry-candidate-20261103-metrics.json` (includes packet
  offsets/timestamps for all 15 rejected-feedback IDs)
