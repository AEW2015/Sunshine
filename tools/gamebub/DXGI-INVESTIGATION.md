# Sunshine Windows capture investigation

The current Python sender's desktop path uses Pillow `ImageGrab`; a previous
1920x1080 host probe averaged 43 ms just for capture. No DXGI capture or
physical Game Bub playback performance has yet been measured for this fork.

The existing Sunshine implementation offers a path worth testing:

- `platf::display()` in `src/platform/windows/display_base.cpp` selects the
  desktop-duplication RAM backend for `mem_type_e::system` when capture is
  `ddx` or auto; auto can also fall back to Windows Graphics Capture.
- `display_t::capture()` in `src/platform/common.h` uses a captured-image
  callback and a separate image-pool callback. `alloc_img()` allocates a frame;
  `img_t` exposes dimensions, pixel pitch, row pitch and an optional
  steady-clock capture timestamp. The producer must respect ownership and
  callback threading rules, including timeouts and interruption.
- `display_ddup_ram_t::snapshot()` in `src/platform/windows/display_ram.cpp`
  obtains a duplicated desktop frame, copies GPU texture to a staging texture,
  maps it and copies into the RAM image. The RAM backend advertises 8-bit
  `B8G8R8A8_UNORM` and `B8G8R8X8_UNORM` capture formats. A JPEG adapter must
  respect row pitch, color ordering and image lifetime before scaling to the
  fixed viewport; it must not assume every image has tightly packed rows.
- The backend signals `reinit` for display size, format or duplication access
  changes. The isolated candidate must stop old producers, release resources,
  enumerate again, and avoid queuing old frames during reinitialization.

Suggested next implementation: an opt-in standalone capture probe that reuses
this platform interface with an isolated configuration, explicitly selects an
output, counts fresh captured frames and measures capture, copy, conversion and
JPEG stages. It must not start or reconfigure the installed Sunshine service.
Only after that works should a bounded JPEG sender be attached to this capture
source. Do not encode JPEG under Sunshine's existing `videoFormat` values:
`video.h` currently maps them to H.264, HEVC and AV1 and falls back to H.264 for
unknown values.

Required verification: deterministic pitch/color/letterbox tests; a fake
capture source for timeout, interruption, resize, access loss and recovery; and
manual tests of the selected real display, moving fullscreen/windowed games,
cursor visibility, display mode changes, sleep/resume and multi-GPU selection.
Check both throughput and frame age, distinguish new frames from repeats, and
measure the full path rather than only a `grab()` call. HDR and protected
content need explicit behavior rather than silent color or black-frame claims.

An exploratory third-party DXcam test and static CPU scaling comparison are
recorded in [dxgi-desktop-probe.md](measurements/dxgi-desktop-probe.md). They
are not benchmarks of Sunshine's capture code, and the third-party test printed
a COM cleanup access-violation warning in one run.
