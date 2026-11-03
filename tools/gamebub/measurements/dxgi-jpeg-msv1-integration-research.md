# DXGI capture to standalone JPEG/MSV1 sender: integration research

## Recommendation

Keep the Game Bub sender as a separately built and launched test executable. Do
not change Sunshine's installed executable, service registration, default CMake
configuration, or normal GameStream capture path. The first viable native
vertical slice should use a standalone DXGI Desktop Duplication capture loop,
copy each acquired desktop texture into an owned CPU buffer, release the DXGI
frame, then hand the copied frame to a bounded latest-frame JPEG/MSV1 pipeline.
Reuse the existing MSV1 format contract and test vectors. Keep capture, encode,
and UDP send behind a distinct tool target and build directory.

This is a proposed design, not implemented here. A second process can still
compete with an already-running Sunshine instance for Desktop Duplication
resources, D3D device time, and display bandwidth. Do not run a parallel
capture soak against a valued Sunshine session. Start with recorded-frame
tests, then use a disposable test machine/session or test display for live
capture. Building the new target does not require installing it or replacing
the running service.

## What the checkout currently does

### Capture

- `tools/dxgi.cpp` is only a DXGI factory/adapter/output enumerator. It does
  not call `DuplicateOutput`, capture pixels, or encode frames.
- The Windows production backend lives in
  `src/platform/windows/display_base.cpp`, `display_ram.cpp`,
  `display_vram.cpp`, and `display.h`. `platf::display()` selects
  Desktop Duplication (`display_ddup_*`) for the `ddx`/default backend and
  selects either RAM or VRAM based on the requested memory type
  (`display_base.cpp`, around lines 1024–1058).
- `duplication_t::next_frame()` releases any previous acquired frame before
  calling `AcquireNextFrame`; its status mapping includes timeout and
  access-lost/reinit. `release_frame()` calls `ReleaseFrame()` and handles
  access loss (`display_base.cpp`, lines 150–215). The outer capture loop also
  paces snapshots and releases the duplication snapshot after push callbacks
  (`display_base.cpp`, around lines 270–355). A new implementation must keep
  that acquire/copy/release order and recover from mode/device changes.
- For the CPU path, `display_ddup_ram_t::snapshot()` copies the desktop texture
  into a staging texture, maps it, copies `height * RowPitch` bytes into the
  allocated image, then unmaps (`display_ram.cpp`, lines 304–342). Supported
  capture formats are BGRA/BGRX (`display_ram.cpp`, around lines 409–419), so
  JPEG conversion must handle channel order and row pitch rather than assuming
  tightly packed RGB.
- `platf::img_t` has raw pointer, dimensions, pixel pitch, row pitch and an
  optional `steady_clock` timestamp (`src/platform/common.h`, lines 530–547).
  The RAM subclass owns/deletes the allocation (`display_ram.cpp`, near its
  `img_t` definition). The VRAM subclass instead owns D3D textures, render
  targets, keyed mutex and a shared encoder handle (`display_vram.cpp`, near
  `img_d3d_t`); it is not a CPU JPEG byte buffer and adds GPU synchronization
  and device-sharing work. RAM is the straightforward first bridge to CPU JPEG.
- Sunshine's async capture thread has a 12-entry shared image pool. It reuses
  an image only when its `shared_ptr` use count indicates no consumer is
  holding it, and queues shared image references to listeners
  (`src/video.cpp`, around lines 1604–1699 and 1708 onward). The API contract
  requires capture callbacks to be synchronized and called from the capture
  thread (`src/platform/common.h`, lines 701–741). A standalone sender should
  use its own explicit bounded latest-frame queue rather than depending on
  Sunshine's private queues or retaining pooled buffers after they are reused.

### Existing Game Bub sender and packetizer

- `tools/gamebub/stream_sender.py` is an independent Python sender. Its live
  desktop source is `PIL.ImageGrab.grab()`; clip sources use `host.clip_frames`.
  Both become 720×480 RGB through `host.canvas`, then go to `VideoPipeline`
  (`stream_sender.py`, around lines 15–21 and 397–415). It does not use the
  Sunshine DXGI backend.
- `VideoPipeline` owns separate raw and encoded latest-frame slots and uses
  encoder and sender workers. Old slot content is replaced instead of growing
  an unbounded queue (`tools/gamebub/pipeline.py`). Its frame object holds an
  owned PIL image plus local monotonic timestamps. This is a useful policy
  model for a native bridge, not a capture implementation.
- The Python encoder is Pillow JPEG and validates the receiver's expected
  baseline 4:2:0 profile (`tools/gamebub/msv1.py`, `encode_receiver_jpeg`).
  `send_frame()` packetizes and paces UDP. The Python environment therefore
  requires Pillow; PyAV is used by clip decoding. Python's JPEG function is
  currently the tested sender encoder, not a native Sunshine JPEG API.
- Native `src/gamebub/msv1.{h,cpp}` is only a packet serializer. It borrows an
  immutable JPEG span, computes CRC-32, emits 40-byte MSV1 headers with up to
  1024 JPEG bytes per datagram, and performs no JPEG validation, capture,
  network send, or session negotiation. Its source is included only when
  `SUNSHINE_GAMEBUB_EXPERIMENTAL=ON` (`cmake/prep/options.cmake` and
  `cmake/compile_definitions/common.cmake`); default is OFF. It relies on
  Boost CRC. The serializer's caller must keep the JPEG storage alive through
  packet construction and must separately validate it.

## Proposed standalone shape

1. Add a new Windows-only executable target under `tools/gamebub/` with its
   own `main`, options, output directory, and explicit opt-in build flag. Do
   not add it to service startup, service install, or package install rules.
2. For the initial implementation, use a small standalone DXGI/D3D11 capture
   adapter rather than linking or calling private Sunshine service/session
   internals. It should select a named monitor, own its D3D device and
   `IDXGIOutputDuplication`, handle timeout/access-lost/recreate, copy mapped
   rows into an owned BGRA buffer, and always unmap/release before publishing
   that buffer. Keep cursor composition and rotations explicit decisions; do
   not silently claim parity with Sunshine's cursor/color/HDR handling.
3. Normalize/crop/scale and convert BGRA to the exact sender RGB canvas, then
   use a bounded latest-only queue. Queue capacity should be explicit (one
   waiting raw frame and one encoded frame, matching the lab policy) and old
   frames should be dropped/replaced rather than accumulated. Shutdown must
   stop capture, release acquired frames/resources, and join workers.
4. Encode the immutable 720×480 RGB canvas using the tested Pillow encoder in
   a Python bridge for the first end-to-end experiment, or select and validate
   a native JPEG implementation against the receiver's exact JPEG parser and
   fixture before replacing Pillow. The checkout does not expose a standalone
   C++ receiver-profile JPEG encoder; FFmpeg is a project dependency, but an
   FFmpeg MJPEG encoder is not proven byte/profile-equivalent by existing
   tests. Avoid making JPEG encoding depend on Sunshine service globals.
5. Feed validated JPEG bytes to `msv1::packetizer_t` (or the Python reference
   `send_frame`), enforce the negotiated/test frame byte bound before
   packetization, and send through a separate test socket. Treat ingress
   feedback as ingress only; it does not establish receiver presentation.

An IPC boundary is a practical option if capture stays native and encoding or
sender logic stays Python: a named-pipe/shared-memory transport with a fixed
header, dimensions, pixel format, row pitch, sequence, and monotonic capture
timestamp. Use owned/copy-complete buffers and bounded slots. A raw 720×480
BGRA frame is about 1.32 MiB; at 30 fps that is roughly 39.6 MiB/s before IPC
overhead, so benchmark copies and do not choose a pipe based only on simplicity.
Shared memory reduces copies but needs explicit ownership/generation and
shutdown rules.

## Dependencies and build isolation

- Reusing `platf::display()` would pull in Sunshine platform initialization,
  configuration/global state, utility and logging code, Windows capture
  sources, and the selected build's FFmpeg/D3D dependencies. It is not currently
  packaged as a small reusable capture library. Directly linking all of
  `video.cpp` or starting the Sunshine executable is unnecessary for the
  standalone sender.
- A standalone DXGI/D3D11 capture source needs the Windows SDK DXGI/D3D11
  headers/libraries and the existing UTF/display enumeration helpers only if
  desired. CPU JPEG can use the existing Python Pillow runtime, or a separately
  declared native JPEG dependency. MSV1 packet serialization can reuse the
  optional native source and Boost CRC; socket/session logic still must be
  implemented in the tool.
- Keep the target opt-in and build in a new `cmake-build-gamebub-*` directory.
  The installed binary/service should not be overwritten, reconfigured, or
  restarted as part of build/test. Do not add the target to install rules until
  intentionally productized.

## Existing evidence and required tests

Already available:

- `tests/unit/test_gamebub_msv1.cpp` checks native packet bytes/bounds when
  the experimental option is enabled. `tools/gamebub/test_msv1.py` checks the
  Python format/validation and `test_stream_sender.py` covers sender policies.
- `tools/gamebub/measurements/native-msv1-build.md` records a prior isolated
  native build and test run: 862 tests, 851 passed and 11 skipped. It also
  records a separate default-OFF check that did not compile `msv1.cpp`. This
  is protocol groundwork evidence only, not an integrated sender or playback
  test.
- `tools/gamebub/measurements/desktop-capture-probe.md` and
  `dxgi-desktop-probe.md` document exploratory GDI/DXcam tests. They explicitly
  do not establish Sunshine DXGI reuse, game/full-screen correctness, device
  loss recovery, or 30 fps operation. The third-party DXcam test also recorded
  a cleanup exception.

For a proposed native target, add tests before live capture:

- Pure unit tests for option bounds, row-pitch/channel conversion, orientation,
  canvas geometry, timestamp domains, latest-frame replacement, sequence
  handling, oversize behavior and packetizer lifetime assumptions.
- Recorded raw-frame fixtures that compare output size, pixel layout and
  deterministic JPEG bytes/profile against the Python reference. If JPEG bytes
  differ, validate both with the firmware parser and document profile
  equivalence rather than assuming it.
- A fake capture source for timeout, access lost, mode change, shutdown,
  queue-full and slow-encoder paths. Verify resource release on each branch.
- Live test only on a disposable Windows session/display: confirm selected
  output, cursor and color behavior, fullscreen game capture, refresh pacing,
  access-lost recovery, frame-age/drop counters, CPU/GPU cost and receiver
  ingress/presentation independently. Record whether Sunshine was running;
  do not infer display presentation from sender completion or ACK.

No native capture/JPEG/MSV1 sender integration or tests were added as part of
this read-only research note. The installed service was not touched.
