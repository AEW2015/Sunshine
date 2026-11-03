# Game Bub optimization and validation backlog

This is a proposed backlog, not a list of completed features or tests. Priorities
assume a fixed 720x480 canvas at 30 fps, 16:9 content with black bars, a single
controller, and the receiver's current JPEG/MSV1 test profile. Preserve stock
Sunshine behavior in any optional integrated mode. Measure before and after on
the same source and machine; reject changes that harm the receiver profile.
The audio/session protocol and physical receiver behavior still need agreement.

Each item lists a deterministic unit or component test; performance and
hardware claims additionally need the measurements at the end. Timing is not
a reliable unit-test assertion on shared machines.

## First: bounded streaming pipeline

1. **Overlap capture, encode and send** with independent workers and bounded
   handoffs. Test: controlled worker gates show capture continues during send,
   only the latest waiting frame survives, and shutdown joins every worker.
   `pipeline.py` is connected to clip/desktop capture and MSV1 in the standalone
   test sender; Sunshine integration and physical-network measurement remain.
2. **Drop stale video before encoding.** Test: inject a fake clock and expired
   frames, assert no encoder call and correct drop count, including boundary age.
3. **Drop expired encoded frames before sending.** Test: a slow fake encoder
   advances the clock; no bytes are emitted for a frame past its deadline.
4. **Limit in-flight data.** Test: a stalled fake socket and producer burst do
   not exceed the configured frame and byte bounds, and never deadlock.
5. **Avoid retransmitting an obsolete frame.** Test: a newer frame arriving
   during a blocked send replaces the waiting frame without altering the frame
   currently in flight; simulate interrupted sends and recovery.
6. **Pace packets without bursts.** Test: fake clock/socket verify spacing,
   a scheduler pause does not accumulate burst credit, and a frame that cannot
   finish before deadline stops. Existing `test_msv1.py` tests single-frame
   pacing; extend it for the streaming scheduler.
7. **Respond to backpressure.** Test: receiver busy/dropped feedback stops or
   reduces offered work, delayed or unrelated feedback cannot acknowledge a
   newer frame, and missing feedback times out. Confirm exact semantics with
   the receiver team before changing the protocol. The test sender now lowers
   quality for busy/dropped responses and limits silent peers to recovery probes;
   physical behavior and receiver-policy agreement remain to be validated.
8. **Adapt quality with hysteresis.** Test: scripted congestion reduces quality
   within allowed bounds, sustained headroom raises it slowly, transient loss
   does not oscillate, and oversize frames are dropped or re-encoded within
   the age budget. The experimental sender now uses fast backoff and requires
   30 headroom observations with accepted feedback to recover one quality step;
   tune against real receiver measurements.
9. **Honor the receiver frame limit.** Test: exactly-at-limit and over-limit
   payloads, incomplete sends, and repeated oversize frames; never send a frame
   that exceeds negotiated memory.
10. **Minimize copies and allocations.** Test: frame ownership remains valid
    until send completes and reused buffers cannot corrupt in-flight frames;
    compare allocation counts and CPU separately in a benchmark.

## Capture, scale and encode

11. **Use Sunshine's DXGI capture path** for the integrated host. Test: a fake
    capture source supplies frames, timeout, device loss and size changes;
    recovery restores the fixed canvas without leaking resources. A preliminary
    [desktop capture probe](measurements/desktop-capture-probe.md) identifies
    existing ImageGrab overhead but does not select a backend.
12. **Keep scaling efficient.** Test: wide, tall, tiny and 16:9 inputs preserve
    proportions and black bars. Existing clip-path bilinear tests cover a solid
    frame; add moving-detail visual comparison on real hardware.
13. **Avoid scaling duplicate frames unnecessarily.** Test: duplicate identity
    or timestamps allow reuse only when source and target configuration match;
    changed frames and resize invalidate cached content.
14. **Evaluate GPU scaling versus CPU.** Test: reference frames produce the
    correct viewport and bounded pixel error; measure GPU/CPU utilization,
    transfer overhead and quality before choosing.
15. **Use a fast baseline JPEG encoder.** Test: inspect real bitstreams for SOF0,
    dimensions, YCbCr 4:2:0, required standard Huffman tables, quantization
    tables and no restart markers; decode deterministic fixtures independently.
16. **Avoid redundant validation in a production hot path only if justified.**
    Test: malformed or unsupported encoder output is detected at the chosen
    validation boundary; retain exhaustive validation in tests and bring-up.
17. **Enforce one encoder instance per worker and bounded reconfiguration.**
    Test: quality changes affect the next complete frame and cannot mix tables
    or dimensions across frames; injected encoder errors release resources.
18. **Measure CPU contention and thread placement.** Test: workers start,
    stop, and honor configured limits under a fake executor; measure affinity
    and priority experimentally rather than assuming they improve latency.
19. **Retain deterministic patterns.** Test: fixed inputs yield pinned geometry,
    color regions, frame ID patch and receiver-compatible bitstreams; exact
    JPEG hashes are asserted only for a pinned encoder/version.

## Transport and recovery

20. **Keep MSV1 framing receiver-compatible.** Test: golden datagrams, boundary
    chunk lengths, byte order, CRC, timestamps and frame-ID wrap against the
    pinned receiver parser. Existing `test_receiver_integration.py` covers
    valid frames and several malformed/recovery paths; extend as needed.
21. **Recover from dropped, duplicated and reordered chunks.** Test: parser
    never presents a partial frame and accepts the next valid SOF according to
    the receiver's actual recovery contract.
22. **Handle network failure and reconnection.** Test: socket errors, unreachable
    peer, restart, sequence rollover and old-session packets cannot wedge the
    sender or admit stale input.
23. **Keep telemetry cheap and bounded.** Test: counters distinguish capture,
    encode, stale, congestion and receiver failures; logs use bounded storage
    and aggregation does not block the media workers. The standalone sender
    now queues JSONL records to a separate writer with memory and file bounds;
    records can be dropped and final stdout reports logging failures.
24. **Negotiate a versioned dedicated session.** Test: unknown versions and
    unsupported capabilities fail cleanly, and stock Moonlight never receives
    JPEG labeled as H.264. Exact handshake remains to be agreed.
25. **Provision a fixed trusted device without a password prompt.** Test:
    reject unknown or replayed peers, release resources on failure, and verify
    reconnect/key rotation. Design the actual authentication with the peer;
    current MSV1 test traffic has no authentication.

## Audio and synchronization

26. **Capture and encode host audio** once the receiver selects its codec and
    format. Test: sample rate/channel conversion, silence, partial blocks,
    capture restart and encoded-format constraints with known signals.
27. **Keep audio bounded and continuous.** Test: queue age/size limits, overflow,
    discontinuity signaling, underflow and recovery with an injected clock.
28. **Schedule audio independently of video.** Test: slow or dropped video
    cannot block timely audio, and audio congestion cannot grow video latency.
29. **Synchronize clocks.** Test: modeled drift, reordering, reset and wraps
    converge without unbounded buffers; specify receiver clock and recovery
    before implementation. Validate audible and visible synchronization on device.

## Controller and Windows integration

30. **Translate each of the 12 button bits** to the chosen Xbox-style flags.
    Existing `test_msv1.py` checks each bit and all 4,096 button combinations
    through the logical adapter; add receiver-owned golden button vectors.
31. **Handle simultaneous presses and releases.** Test: full snapshots preserve
    chords, repeated packets are idempotent, neutral releases all buttons,
    and unknown bits follow the agreed protocol policy.
32. **Release on disconnect, timeout or session change.** Test: held inputs
    become neutral exactly once and old packets cannot reassert them. A timeout
    must match the receiver heartbeat so an idle held button is not released.
    The laboratory logs a neutral state after 500 ms silence and rejects a
    same-frame snapshot after timeout; this does not inject or solve reordering.
33. **Create one Windows virtual controller.** Test: inject a fake Sunshine
    gamepad backend and assert allocation, updates, neutralization and cleanup;
    separately check actual Windows game visibility with a real driver.
34. **Handle driver unavailable or allocation failure.** Test: clear status,
    no crashes or repeated allocations, video-only mode remains usable, and
    no changes are made to the existing installed Sunshine service.
35. **Keep input independent of video.** Test: controller updates continue
    under video backpressure and packet loss, according to the agreed feedback
    cadence and session rules. Current MSF1 embeds buttons in video feedback;
    an independent cadence requires coordination.
36. **Map only physical controls.** Test: A/B/X/Y, D-pad, L/R and Start/Select
    map correctly; no invented analog sticks or triggers, and Home remains
    local unless the team agrees otherwise.

## Evidence required beyond unit tests

- Host benchmarks: detailed moving gameplay and a disclosed synthetic or
  animation baseline; record duration, canvas, quality distribution, encoded
  bytes, FPS, CPU/GPU, drops, queue age and source/license. Compare identical
  inputs with warm-up and repeat runs.
- Receiver integration: actual ESP32 Wi-Fi and FPGA/QSPI, inspect decoded and
  displayed frames separately from ingress ACK, measure bitrate, failures and
  duration. Exercise weak Wi-Fi and reconnect.
- End to end: measure input-to-game and capture-to-display latency with a
  suitable external or synchronized method; report median and tail, resolution,
  FPS, quality, bitrate and test duration. Never infer playback from an ACK.
- Windows gamepad: verify controller enumeration and every button in Windows
  and representative games, including disconnect while held. Record backend,
  driver version and any licensing requirements.
- Compatibility: run native Sunshine tests and stock Moonlight connection tests
  in the isolated candidate without replacing or restarting the installed service.
