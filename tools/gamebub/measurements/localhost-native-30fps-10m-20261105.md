# Localhost native-frame 30 fps soak, 10 minutes

Run: `artifacts/native-30fps-soak-20261105/600s-20261105T094534Z`. The source summary SHA-256 is recorded in the companion [JSON](localhost-native-30fps-10m-20261105.json). The run used the saved Xonotic clip at nominal 30 fps, an 8 Mbps cap, Q25, hybrid pacing with a 400 μs spin tail, and input-only AV traffic to localhost. It sent no audio or gamepad injection.

## Delivery and source

The sender submitted and encoded 18,000 frames; 17,997 were sent and accepted, with 3 encoded frames replaced. There were no skipped slots, invalid datagrams, reply errors, or pending feedback at shutdown. The receiver completed all 17,997 sends. Including drain, the measured send rate was 29.9797 fps over 600.306 seconds.

The saved source is 1024×600. The existing canvas transform scales it to 691×405 and places it at (14, 37) on the 720×480 canvas. The clip looped: the source log shows 5,490 frames from each of loops 0–2 and 1,530 from loop 3. Timestamps did not repeat consecutively, and each native frame was selected once per pass without resampling. The repeated passes revisit the same source scenes, so 18,000 transmitted frames are not 18,000 distinct scenes.

The 8 Mbps value is a cap, not the observed rate. Encoded payload totaled 351,114,954 bytes; application wire bytes totaled 365,096,357, or about 4.865 Mbps.

## CPU and memory samples

The process used 377.98 CPU seconds across the video sender and local reference/AV peer threads in the same process. The sender thread used 34.1875 CPU seconds, about 5.7% of one core across the video run. The process total and sender-thread figure have different scopes; this is not a direct comparison with a separate sender process.

There were 21 process-memory samples at roughly 30-second intervals. For the 19 samples at or after 60 seconds, working set was 52,420,608 bytes minimum, 59,133,952 median, 61,008,282 p95, and 61,767,680 maximum. Private bytes were 45,871,104 minimum, 51,769,344 median, 54,622,208 p95, and 55,046,144 maximum. These are sampled observations, not memory bounds. The localhost peer retained up to 256 control packets, and the finite run does not establish a steady-state heap bound.

## Scope and provenance

Input-only AV sent 19,535 packets with zero invalid packets, stale packets, or timeouts; STOP was sent and observed, with no cleanup errors. The run summary reports operational reconciliation. It does not establish hardware playback, RF behavior, physical receiver decode, display presentation, or audio acoustics.

Native profiling compilation overlapped part of the run, and a 5-second audio smoke also overlapped a portion. Treat these results as an operational localhost soak, not a clean comparative CPU or latency benchmark. The companion JSON records the source and reference revisions and SHA-256 hashes.
