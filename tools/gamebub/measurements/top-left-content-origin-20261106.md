# Explicit top-left content placement — 2026-11-06

`--content-origin top-left` anchors the fitted image at canvas (0,0).
`center` remains the default. Both modes use the same aspect-preserving scale
within 720x405 on a 720x480 RGB canvas. For the 1024x600 Xonotic clip, the image
is 691x405: top-left placement leaves 29 black columns on the right and 75 black
rows below. Source pixels are neither stretched nor cropped; this does not
change the receiver's own panel placement. Right shift remains zero in the
finite launcher.

The Python launcher, its child command, manifest and sender session log record
the selected origin. PowerShell exposes `-ContentOrigin top-left`. This is an
explicit processed-content change, so the requested 24 fps/5 Mbps/top-left run
is an operating-point test, not a bitrate-only comparison with earlier runs.

Validation before hardware transmission:

- 127 focused host/sender/launcher regressions passed in 14.795 seconds.
- All 553 tests in the tracked GameBub Python cohort passed, zero skips, in
  73.509 seconds; available pinned native/receiver integrations were enabled.
  Unrelated untracked controller work was excluded and preserved.
- Canvas placement: 11/11 executable statements and 4/4 branches covered.
  Launcher: 226/226 statements and 82/82 branches covered. Changed sender
  placement statements and validation branches are hit. Only existing bare
  entrypoints remain uncovered in the measured host/sender modules; no coverage
  exclusions were added.
- Tests compare every fitted source pixel between center and top-left, using
  both Pillow images and PyAV video frames. They verify output geometry,
  right/bottom padding, invalid-option rejection before resources, sender
  submission/logging and launcher propagation.
- The actual PowerShell wrapper dry-run forwards the top-left option without
  opening devices or networking. Ruff check/format and diff whitespace checks
  pass for changed files.

Raw results, coverage and dry-run manifest are under
`artifacts/top-left-origin-20261106/`. No native C++ source or dependency
declarations were modified. The installed Sunshine service was not replaced
or restarted, and the previously frozen candidate tag is retained.
