# Margin10, original timing: five minutes with zero host shift

This follows the requested five-minute desktop test at the same5fps,
720x480, fixed quality25 and2Mbps MSV1 cap. The operator removed the previous
20-pixel host shift; `shift_right_px=0` is explicitly recorded. Source port55534,
200ms age deadline,262,144-byte JPEG guard and disabled retry were retained.
The receiver's margin10/original-timing/32-slot configuration was last reported
by the operator and was not changed by the host.

| Measurement | Result |
| --- | --- |
| America/Denver host window | 2026-11-03 15:01:03.881 to15:06:04.436 MST |
| UTC host window | 2026-11-03 22:01:03.881 to22:06:04.436 |
| Sender duration including startup/grace | 300.551 seconds |
| Source / destination | 192.168.0.47:55534 /192.168.0.157:5533 |
| Frame IDs / scheduled slots | 30100..31599 /1,500 |
| Submitted / encoded / completely sent | 1,500 /1,500 /1,500 |
| Partial / zero-byte sends / skipped slots / suppression | 0 /0 /0 /0 |
| Matched accepted / rejected feedback | 1,500 /0 |
| Heartbeats / unmatched / pending feedback | 1,153 /1 /0 |
| First / final received feedback | 101 /1,600 |
| First / final dropped feedback | 0 /0 |
| Independent final received /decoded /presented | 1,600 /5,310 /5,310 |
| Independent received /decoded /presented run delta | +1,500 /+1,500 /+1,500 |
| Frame drops /queue packet drops | 0 /0 |
| Queue peak /final occupancy | 24 of32 /0 |
| Core faults /core drops /overflows /underruns | 0 /0 /0 /0 |
| Complete host send rate | 4.991fps over full duration |
| Encoded JPEG / sent MSV1 bitrate | 0.833 /0.866Mbps, excluding UDP/IP/Wi-Fi |
| Encoded JPEG / MSV1 bytes | 31,296,679 /32,545,119 |
| Packet timing frames / datagrams | 1,500 /31,211 |
| Host packet gap ms min /p50 /p95 /max | 4.324 /4.980 /5.207 /13.096 |
| Logger records /lost /I/O errors | 8,656 /0 /none |

The first accepted response was for30100 and the last for31599. The automatic
completed-frame counter delta is1,499 because the first response establishes a
baseline after that completion. The preceding run ended at100 received/0 dropped;
the final1,600/0 and1,500 matched responses agree with1,500 new completions.
The operator subsequently confirmed final totals1,600 received,5,310 decoded
and5,310 presented, increasing each by1,500. This gives stage baselines100,
3,810 and3,810 from the supplied deltas; different counter reset scopes remain
separate. Frame and queue drops were zero, queue peak24/32 and final occupancy
zero; all reported core faults/core drops/overflows/underruns were zero.

Margin10 and timing preset0 remained applied. Receiver placement settings did
not change; the host shift changed from20 in the preceding short test to0 here.
The supplied receiver-side camera report describes no flashing and stable
placement, consistent with post-run samples. The host did not independently
monitor the handheld optically throughout the run. This passes the five-minute
5fps milestone for this configuration on independent stage counters and the
supplied camera observation; it does not establish the causal effect of the
shift change or a physical per-pixel calibration.

There were no capture errors, raw/encoded replacements or feedback timeouts in
the sender summary/log. The stream used the live primary desktop via FFmpeg
Desktop Duplication and can include repeated unchanged images or app switches.
It does not establish distinct-gameplay FPS, optical frame intervals or
game-to-photon latency. Host shift0 restores all720 canvas columns without
the experimental left strip or host-side right crop; panel placement remains
receiver controlled. No production source, installed service or receiver
configuration was modified by this test. No subsequent stream was started.

Artifacts under `tools/gamebub/artifacts`, prefix
`handheld-margin10-desktop-5fps-5m-30100-shift0-20261103`: `.jsonl`,
`-summary.json`, `-provenance.json`, `-packets.csv`, `-packet-report.json`,
`-analysis.json` and `-receiver-final.json`. Complete packet offset continuity and JPEG length were
checked; estimated packet UTC uses a host anchor, not receiver synchronization.
