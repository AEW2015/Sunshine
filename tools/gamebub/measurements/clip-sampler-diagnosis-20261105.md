# Clip sampling diagnosis for 30 fps video tests

The completed legacy combo run at `artifacts/overnight-long-soak-20261105/audio-video-30fps-5m-0309` used the existing resampling sampler. Its sender submitted and encoded 9,000 video frames, sent and received feedback for 8,997, and recorded 3 encoded replacements, zero skipped slots, zero pending feedback, and zero invalid datagrams or reply errors. The sender's source timestamp telemetry counted 3,000 repeats. The run also sent 28,747 synthetic audio blocks. These counts describe that run; they do not qualify its motion as 9,000 unique native source frames.

## Source PTS evidence

PTS values below are in microseconds. The first 12 `source_sample` records in the legacy run are:

`7000, 40000, 40000, 107000, 140000, 140000, 207000, 240000, 240000, 307000, 340000, 340000`

The corresponding first 12 entries in the earlier native 60-frame source manifest (`measurements/jpeg-quality-20261105.json`) are:

`7000, 40000, 74000, 107000, 140000, 174000, 207000, 240000, 274000, 307000, 340000, 374000`

The legacy stream repeats the preceding PTS at output indices 2, 5, 8, and 11 in this prefix. Its total telemetry reports 3,000 repeats in 9,000 samples. The native manifest contains 60 unique decoded frames, with PTS origin 7,000 μs and end 1,974,000 μs. This points to sampler behavior in the test input path; it is not evidence of a receiver or transport issue.

## Test selection

Keep the legacy sampler selected for the first 20 fps hardware comparison so that the established control path remains the comparison baseline. For 30 fps motion qualification, select the native CFR path only when the stream's nominal rate matches the sender rate and its rational PTS cadence passes the source-tick and half-period checks. The new native 30 fps combo run is separate evidence and should be reported independently from the completed legacy run; do not blend their counts.

Both runs and the source manifest are lab evidence only. The legacy combo used synthetic audio and localhost reference peers; neither run establishes physical receiver decode, display presentation, audio playback, or RF behavior.
