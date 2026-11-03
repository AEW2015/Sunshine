# Exploratory Windows desktop capture timing

On this machine, a short exploratory test captured a 1920x1080 primary desktop
while the native build was running. Pillow `ImageGrab.grab()` took a mean of
43.05 ms, median 41.86 ms, and maximum 61.03 ms across 10 grabs. These values
include capture but exclude the sender's subsequent resize and encoding.

A separate temporary GDI `StretchBlt`/32-bit DIB prototype captured and scaled
the same desktop directly to 720x405 RGB. Across 40 attempts it took a mean of
25.01 ms, median 24.62 ms, p95 29.51 ms, and maximum 33.26 ms. The test
checked API success and converted pixels to an image, but did not validate
visual fidelity, cursor behavior, exclusive full-screen games, multiple monitor
layouts, DPI changes, protected content or device loss. The two tests were not
interleaved and build load varied, so the results are exploratory, not a
controlled improvement or a claim of 30 fps streaming.

The prototype was not added to the sender. Sunshine's existing DXGI capture
path remains the stronger integration candidate; it needs an isolated build,
game-specific capture validation and real receiver measurements before a
capture backend can be selected for the dedicated product.
