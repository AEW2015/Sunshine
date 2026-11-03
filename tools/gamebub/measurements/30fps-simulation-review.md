# 30 fps memory-path simulation review

Simulation-only investigation dated 2026-11-02; this branch does not modify the
Sunshine service or the production encoder. At 100 MHz, replay of one full
720×480 JPEG output through the receiver's existing SDRAM controller took
47.49 ms without scanout and 88.76 ms with the existing LCD fetch and memory
arbitration. An isolated 8×8 transpose prototype reduced those times to 27.62
and 53.10 ms respectively, still exceeding the 33.33 ms frame budget in the
scanout test. The transpose does not implement burst writes. These are
behavioral RTL simulations with a functional SDRAM model and saturated trace
input, not hardware FPS or whole-pipeline measurements.

The source, pixel-conservation checks, assumptions and XSim transcripts are in
the Moonbub fork branch `study/30fps-sim-20261102`, report
`docs/30fps-throughput-simulation.md`. The existing physical observations in
[handheld fixture bring-up](handheld-fixture-bringup.md) and
[first live game diagnostic](handheld-live-game-test-01.md) remain independent:
they demonstrate individual displayed frames and visible game updates, not
sustained 30 fps. Higher fixture-rate tests reported sequence errors; the cause
is not yet established.

The host itself also has work before 30 fps. The separate
[desktop capture probe](dxgi-desktop-probe.md) reports lower host/localhost
rates in its tested configuration; it is not a controlled moving-game or
physical receiver benchmark. Next measure capture, scale, JPEG encode, sender
queue/packet pacing, receiver ingress and FPGA presentation separately while
the receiver team tests a burst-write memory path. Preserve the existing
authenticated Sunshine/Moonlight behavior; the current JPEG sender remains an
experimental standalone test mode.
