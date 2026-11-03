# Exploratory encode throttling under overload

A temporary experimental pipeline policy kept one encoded JPEG waiting and
avoided encoding newer raw frames until that slot cleared. It remained
transport-independent and was never enabled in the sender. The uncommitted
policy was discarded after this test because it increased frame age and
partial sends.

Two sequential 25-second localhost runs used the same Xonotic footage, 30 fps
target, 2 Mbps MSV1 cap, fixed JPEG quality 20, and 200 ms host age deadline.
A separate one-hour soak and other host activity ran concurrently. This was one
trial per policy, in fixed order; it is exploratory, not a controlled estimate
of their performance difference. Both peers were the pinned Python receiver
reference, not the physical handheld.

| Measure | Existing eager encoder | Experimental throttle |
| --- | ---: | ---: |
| Frames encoded | 748 | 372 |
| Complete frames accepted | 301 | 286 |
| Waiting raw / encoded frames replaced | 1 / 447 | 378 / 0 |
| Failed frame sends | 0 | 86 |
| Host-assigned timestamp-to-final-send median / p95 | 119.47 / 153.64 ms | 164.59 / 192.78 ms |
| Encoded queue age median / p95 | 17.61 / 48.35 ms | 64.32 / 78.27 ms |
| Combined-process CPU time | 24.25 s | 21.14 s |

The throttled failures comprised 62 zero-byte refusals and 24 partial frame
sends. Both reference runs reported zero invalid datagrams and zero log
drops; that does not establish how the physical receiver handles incomplete
frames. CPU time included clip decoding, sender and reference, not just JPEG
encoding. The source-image age and displayed latency were not measured, and
fixed quality means quality adaptation and recovery were not tested.

The temporary harness and logs are ignored local artifacts named
`encode_throttle_benchmark.py`, `encode-throttle-{baseline,throttle}-25s.jsonl`
and `encode-throttle-comparison-25s.json`. Reproducing the exact experiment
requires the discarded temporary policy; the active pipeline does not expose
it. Future work should only reconsider throttling with a demonstrated freshness
and recovery policy, and a controlled test before hardware use.
