# Audio eviction trace validation — 2026-11-05

## Controlled receive stall

The localhost fault run used the production AV sender and audio worker with synthetic PCM, a saved clip, gamepad disabled, and no WASAPI or hardware. One owned AV socket `recvfrom` call was delayed once after ACTIVE and video readiness. The measured QPC interval was **121.2878 ms**, below the 500 ms input lease.

The worker recorded eight successful queue evictions during that interval. Their sequence IDs, **191–198**, exactly matched the peer's missing audio sequence IDs. All eight trace publish timestamps fell within the pause; the bounded trace had zero overwritten records. This demonstrates that the trace identifies evictions caused by this explicit receive stall. It does not establish why unrelated gaps occurred in an earlier run.

STOP was sent and observed, AV input timeouts and capture errors were zero, and the 30 fps video target completed with 300 submitted, sent, and accepted frames, zero replacements, and a complete session summary. The run is localhost sender/ingress evidence only; it says nothing about RF reception, receiver decode, playback, or acoustics.

Artifact directory: `tools/gamebub/artifacts/overnight-long-soak-20261105/audio-stall-10s-native-30fps-8mbps-20261105`. The fault wrapper source is archived there and has SHA-256 `1acad86ecf2c4a6fb6d0cd7c6643f4848d65e8526e24a386a080cf4920ce8fb0`.

## Unfaulted five-minute trace run

The positive five-minute localhost run completed with the trace enabled. It submitted 9,000 video slots; 8,999 were sent and accepted, with one replacement and no repeated source timestamps. Audio published 28,744 blocks: 28,742 sent, none stale or evicted, and two queued at close. The peer received all sent audio packets with no sequence gaps. Captured PCM totaled 14,427,840 frames; capture errors and AV input timeouts were zero. STOP was sent and observed. Both logs stayed below 64 MiB with no dropped log events.

This steady run validates trace availability and normal-run accounting. Since it had no queue evictions, it does not independently exercise the eviction-to-gap correlation; the controlled stall does that. Neither run retroactively explains the three sequence gaps in the earlier 30-minute soak, where the eviction trace was not present.

## Regression evidence

The focused `test_live_audio` run passed 9 tests. Root also reported completed runs of 548 full Python regressions, 5 optional Python regressions, and 173 native regressions. These counts are reported provenance; no tests were run while preparing this report.

Machine-readable values and artifact paths are in [audio-eviction-trace-validation-20261105.json](audio-eviction-trace-validation-20261105.json).
