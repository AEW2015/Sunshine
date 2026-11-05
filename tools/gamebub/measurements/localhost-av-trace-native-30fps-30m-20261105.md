# Localhost native 30 fps AV soak with eviction trace, 30 minutes

Run: `artifacts/overnight-long-soak-20261105/audio-video-native-30fps-trace-final-30m`. It completed operationally in 1,800.79 seconds, from 2026-11-05 12:07:46 to 12:37:47 UTC. The [JSON report](localhost-av-trace-native-30fps-30m-20261105.json) records the final summary hash, exact counters, bounded trace, memory samples and source provenance.

This was a localhost saved-clip/reference and AV-input-peer run with native 30 fps selection, Q25, an 8 Mbps video cap, hybrid pacing with 400 µs spin tail, and synthetic 48 kHz audio through the production resampler and IMA encoder. Gamepad injection and capture were off. These results do not establish RF delivery, FPGA presentation, physical audio, or playback.

## Video delivery and counters

The 54,000-slot target yielded 53,999 submitted and encoded frames plus one skipped slot. The sender transmitted 53,996; the localhost peer completed and acknowledged all 53,996. Three encoded frames were replaced before send. There were no partial frames, repeated source timestamps, pending feedback, invalid datagrams, or reply errors. The reference reported zero dropped frames. Send rate was **29.99252 fps over the sender's 1,800.31554-second duration**, or **29.98469 fps over the full 1,800.78581-second harness wall**. Application wire traffic was 1,095,677,851 bytes: **4.86883 Mbps over sender duration** and **4.86755 Mbps over full harness wall**, under the 8 Mbps cap.

The receiver status counter reports 53,995 frames since its baseline. Its first observed event was the baseline frame itself (`frame_id=27000000`, `received_frames=1`, `received_delta=0`), so 53,995 since-baseline plus that first frame equals the 53,996 peer-completed and acknowledged frames. No frame loss is inferred from this counter convention.

Packet timing was off. Full-packet gap distributions are unavailable.

## Synthetic audio and trace reconciliation

The synthetic source captured 86,427,840 frames, or 1,800.58 seconds at 48 kHz. It published 172,188 audio blocks: 172,185 sent, one evicted from the bounded publisher queue, and two queued at close. Accounting reconciles exactly. There were no stale drops, PCM drops, capture errors, trace clock errors, or trace overwrites. The local peer received all 172,185 sends with one sequence gap.

The peer gap was from sequence 161,677 to 161,679, so the missing sequence was **161,678**. The worker's single trace record names 161,678 as the evicted block; the IDs match exactly. The record has `new_sequence=161682`, `shutdown=false`, and no clock error. Its capture and publish metadata differ by 41.9122 ms. The surrounding AV send records show sequence 161,677 at QPC 1377239494982100 ns and 161,679 at 1377239511865300 ns, 16.8832 ms apart; the eviction publish timestamp is just before the latter send. This correlation accounts for this observed gap only. It does not identify why the bounded queue filled or establish a long AV stall.

Synthetic callback telemetry recorded 180,059 callbacks, five late intervals, one missed schedule period, and a maximum callback gap of 18.9898 ms. The precise callback waiter made no fallback or spin calls and reported no runtime or close failures. This describes the synthetic callback path, not WASAPI or physical audio.

AV input sent 58,585 packets with zero invalid or stale packets and zero lease timeouts. STOP was sent and observed with no cleanup errors. “Input” here refers to the AV protocol channel; gamepad injection was disabled.

## Logs, memory and CPU

The video log contained 41,506,193 bytes and the AV log 31,124,777 bytes. Both stayed below the 67,108,864-byte limit with zero dropped events.

The memory sampler recorded 61 grouped samples at 30-second intervals: one startup sample and 60 warm samples. No post-exit child samples or sampling errors were recorded. Values below are sampled observations, not memory bounds. Percentiles use linear interpolation.

| Process | Working set min / p50 / p95 / max | Private bytes min / p50 / p95 / max | Warm one-core CPU interval p50 / p95 / max |
|---|---:|---:|---:|
| Harness | 42,700,800 / 43,173,888 / 43,379,712 / 43,507,712 | 37,376,000 / 37,838,848 / 37,974,016 / 37,974,016 | 22.076% / 24.103% / 24.941% |
| Video sender process | 47,476,736 / 55,119,872 / 57,088,614 / 57,233,408 | 39,944,192 / 48,091,136 / 50,652,365 / 51,007,488 | 56.956% / 64.187% / 69.191% |

Harness-process CPU was 397.406 seconds and includes synthetic audio encoding plus local peers. Video-sender process CPU was 1,034.844 seconds; sender-thread CPU was 90.953 seconds. These scopes differ; thread CPU is a subset of sender-process CPU. Sender one-core interval CPU has 59 samples because its first sample had no prior child interval.

## Source provenance

The run began before commit `61fef798556c78bc2d4f4788400a14005e41f646`. All 15 raw source hashes in the run manifest match the Windows worktree bytes used by the run. Normalizing CRLF/CR line endings to LF, those source texts match the commit tree. This is a text-content comparison; raw Windows-file SHA-256 values are not represented as raw Git-blob hashes. The archived harness and synthetic backend snapshots match their recorded SHA-256 values. The source clip SHA-256 is `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.

Summary SHA-256: `56879fe28322e215c3b6c801d2e005e2db1caa6ec3bd5cd0f5767d95d6bcb7c5`. This is localhost software evidence only. It verifies no receiver hardware, RF delivery, QSPI, FPGA presentation, physical audio, DAC buffering, clock drift, or end-to-end latency.
