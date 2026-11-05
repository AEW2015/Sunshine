# Localhost native-CFR 30 fps video and synthetic audio, five minutes

Run: `artifacts/overnight-long-soak-20261105/audio-video-native-30fps-5m-0335`. The companion [JSON](localhost-av-native-30fps-5m-20261105.json) includes the summary SHA-256 and source hashes. The launcher selected `clip_selection=native` for the saved clip at 30 fps, with an 8 Mbps cap, Q25, hybrid pacing and a 400 μs spin tail. Input-only AV and quiet synthetic PCM ran against localhost reference peers. No hardware-in-the-loop, physical audio, or RF validation was performed.

## Video

The sender submitted and encoded 9,000 frames, sent 8,999, and received matching localhost reference completion and ingress feedback for all 8,999. One encoded frame was replaced. There were zero source timestamp repeats, skipped slots, invalid datagrams, reply errors, or pending feedback. Encoded payload was 175,783,552 bytes; application wire bytes were 182,799,501, about 4.87 Mbps under the configured 8 Mbps cap.

## Audio and input

The synthetic 48 kHz input accepted 14,428,800 source frames, equivalent to 300.6 seconds of modeled samples. It published 28,746 ADPCM blocks: 28,743 sent and received, with 3 queued at close. Stale blocks, queue evictions, PCM drops, capture errors, and peer sequence gaps were all zero. The partial resampler tail was 146 frames. The precise callback waiter used no spin and reported no missed schedule periods; its callback maximum gap was 15.6273 ms, with 2 late intervals.

Input-only AV sent 9,776 packets with zero invalid packets, stale packets, or timeouts. STOP was sent and observed; cleanup reported no errors.

## CPU and comparison scope

The harness process used 67.875 CPU seconds across synthetic audio encoding and all local reference/video/AV peer work in that process. The video sender process used 171.609 CPU seconds; its sender thread used 18.531 CPU seconds. These figures have different scopes and do not isolate pure encoder cost.

The earlier legacy-resampler combo run is separate evidence: it sent and received 8,997 of 9,000 frames and reported 3,000 repeated source timestamps. The native run reported zero repeats. Keep the run counts separate; neither provides HIL decode or display evidence.

No receiver MSI acceptance is inferred from the simulator. The synthetic audio run does not establish production WASAPI behavior, physical playback, DAC buffering, audio drift, or acoustics. The bitrate setting is a cap, not an achieved target.
