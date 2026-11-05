# Localhost synthetic audio and video soak, five minutes

Run: `artifacts/overnight-long-soak-20261105/audio-stress-precise-5m-0256`. The companion [JSON](localhost-av-audio-5m-20261105.json) includes source hashes and the summary hash. This used localhost peers, saved-clip video at 20 fps with a 4 Mbps cap and Q25, and deterministic quiet signed16 stereo PCM through the production resampler and IMA encoder. The synthetic callback backend used precise waiting with a zero spin tail. No physical audio endpoint, WASAPI, gamepad, DAC, capture, or hardware was used.

## Audio accounting

Over 300.805 seconds, the synthetic source accepted 14,428,800 input frames at 48 kHz, equivalent to 300.6 seconds of modeled source samples. It published 28,746 encoded blocks: 28,744 sent and received, with 2 queued at shutdown. There were no stale blocks, queue evictions, PCM drops, capture errors, or peer sequence gaps; received sequence numbers ran from 0 through 28,743. STOP was sent and observed, with no cleanup errors.

The callback log recorded 30,061 callbacks, a maximum interval of 13.6528 ms, zero late intervals, and zero missed schedule periods. The precise waiter made 30,060 native calls, with no fallback, runtime failure, or spin. A 146-frame partial resampler tail remained unpublished at shutdown.

These measurements describe this synthetic source and its wait loop. They do not establish WASAPI behavior, DAC buffering, receiver playback, audio drift, or acoustic output. The simulator reported no received packet rejection data; no MSI acceptance count is inferred.

## Video and input

Video submitted and encoded 6,000 frames; 5,928 were sent and accepted, with 72 replaced, zero skipped slots, zero invalid datagrams or reply errors, and no pending feedback. The source timestamp repeat counter was zero. Input-only AV sent 9,778 packets with no invalid packets, stale packets, or timeouts. STOP was sent and observed.

## Comparison with the earlier event-wait run

The preserved event-wait simulation at `audio-stress-5m-0233` accepted 9,399,360 source frames, equivalent to 195.82 seconds at 48 kHz over 300.796 seconds wall time, and sent 18,725 blocks. This precise-wait run accepted 14,428,800 source frames and sent 28,744 blocks over a similar duration. The earlier simulated source under-produced relative to its modeled 48 kHz cadence. This comparison does not establish why it under-produced and says nothing about production WASAPI.

## CPU scope and provenance

The harness process used 66.625 CPU seconds across synthetic encoding and local reference/video/AV peer work. The video sender process used 138.594 CPU seconds and its sender thread used 12.453 CPU seconds; these have different scopes and do not isolate pure encoder cost.

The source clip SHA-256 is `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`. The pinned reference revision was `75f8497b6ffefadd8c0403728b93ccfbbfa02f52`. Exact archived harness and synthetic backend snapshots, their hashes, and host source hashes are listed in the JSON and run manifest.
