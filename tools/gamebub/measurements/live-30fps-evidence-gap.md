# Host evidence needed for 30 fps Game Bub streaming

The current evidence does not demonstrate 30 fps live Windows game capture to
the physical handheld. The standalone MSV1 JPEG sender is not the installed
Sunshine service or standard Moonlight negotiation. The native Sunshine MSV1
serializer work is not a completed capture/encode/transmit path.

The strongest existing host/localhost test repeated prerecorded Xonotic
footage for ten minutes: 17,886 complete frames reached the local reference
receiver in 600.302 seconds (29.795 fps), with no invalid datagrams. It
reported 9.499 Mb/s JPEG payload and 9.813 Mb/s MSV1 bytes, excluding UDP/IP
and Wi-Fi. It did not include live game capture, the physical receiver or
display. See [the full soak](xonotic-soak-10m.md).

The physical test of a live game targeted 1 fps; 9 complete frames were sent
in 9.640 seconds, and the operator saw the image update. The capture-to-final-
send host-age p95 was 680.2 ms. This did not independently count displayed
frames, measure glass-to-glass latency or test 30 fps. See
[the handheld test](handheld-live-game-test-01.md).

A separate third-party DXcam experiment completed 300 desktop capture/scale/
encode attempts in 11.642 seconds (~25.77/s) on an uncontrolled desktop; it
was neither Sunshine's capture code nor a physical stream. Cleanup produced an
ignored COM exception. Sequential ImageGrab localhost tests reached 16.31 fps
with bilinear and 17.32 fps with BOX, but their live inputs differed, so these
are not controlled quality or filter comparisons. See [the probe](dxgi-desktop-probe.md).

## Companion receiver simulation update

The Moonbub study has since replayed 300 game-derived JPEG inputs through a
behavioral QSPI-to-display model, at 29.981 presentations per second across
299 intervals, with a 37.507 ms maximum modeled arrival-to-swap age. The
inputs contain 299 distinct images because source resampling repeated one.
This roughly ten-second run used precompressed footage and assumed complete
compressed frames were already available at the receiver. It did not measure
capture or encode on this Windows host, live Sunshine, real Wi-Fi, target CPU,
or the physical display. See [the receiver study](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/fpga/experiments/throughput30/burst/gameplay-study/README.md).

A separate ESP32-S3 emulator test receives one synthetic JPEG over a virtual
localhost-only UDP path using the unchanged receiver logic; packets are
ACK-paced. An additional one-frame functional bridge now connects the emulated
receiver to a Verilator FPGA model and checks all 345,600 output pixels; its
simulators have no shared clock. Neither test measures live capture, sender
goodput or game-to-photon latency. See [the emulator study](https://github.com/AEW2015/moonbub/blob/study/30fps-sim-20261102/fpga/experiments/throughput30/burst/esp-emulator-study/README.md).

## Next host-side checks

1. On the Windows test system, capture the actual game at 30 fps for several
   minutes, with repeatable fast motion, text, particles and scene changes.
   Capture frame ID, monotonic capture start/end, scale, encode, sender enqueue,
   first/last packet send, source/encoder configuration and dropped-frame reason.
   Count distinct captures, not repeated API returns. Record the display and
   active capture GPU; do not assume the laptop uses the RTX for capture or
   that any particular encoder was selected.
2. Compare optimized capture/scale/encode candidates at equal resolution,
   sampling, quality and packet budget, retaining the stock fixed-Huffman JPEG
   validator. Test windowed and fullscreen transitions. Keep dependency changes
   and third-party probes isolated from the installed Sunshine service.
3. First run the exact sender to a local reference receiver with a fixed input
   trace, then to the handheld. Log received, CRC-complete, FPGA-decoded and
   actually-presented IDs independently; an ACK or receive completion is not
   proof of display. Include paced packet overhead, device buffer constraints,
   Wi-Fi jitter and a separate audio/control budget if implemented.
4. Report aggregate output FPS over a full 60-second interval, dropped and
   repeated IDs, capture-to-send frame age percentiles, actual bitrate and
   queue high-water marks. Cross-device age needs clock synchronization or a
   physical measurement; host age is not game-to-photon latency. Record actual
   environment and source hashes. A favorable short or prerecorded localhost
   test is not a substitute for the real capture-to-display chain.

These are planned tests; no new Windows or hardware measurement was made for
this note. Do not interrupt the installed Sunshine instance during diagnostics.
