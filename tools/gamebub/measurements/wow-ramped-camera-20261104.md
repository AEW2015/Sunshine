# WoW camera ramp — 2026-11-04, America/Denver

The `wow` profile keeps virtual right-stick camera input with X up, Y left,
A right and B down. A held direction starts at radial magnitude 10,000 out of
32,767 and eases quadratically to full deflection over two seconds. At one
second it is approximately 48% deflection. Actual camera speed follows WoW's
stick bindings, sensitivity and dead zone; these are not changed by the launcher.

Release, opposing-direction cancellation or a direction change restarts the
slow ramp. Diagonals stay normalized. D-pad movement and shoulders/menu mappings
retain their existing behavior. Changing movement or menu buttons while holding
the same camera direction does not restart acceleration.

The ramp uses host monotonic elapsed time rather than packet count, so different
valid input cadences give the same hold-time speed. A gap of 250 ms restarts
gently on the next snapshot. The existing 500 ms input lease still neutralizes
held controls; neutral/shutdown clears the ramp. No background input worker is
introduced.

The pinned controller-only AV client already dispatches every fresh MSI1. For
combined sessions, the WoW profile sink now explicitly requests repeated held
snapshots from the ordered adapter. Other profiles keep change-only output.
Wrong-session, duplicate and stale snapshots cannot advance the ramp or renew
the lease. Wire packets and driver setup are unchanged.

Use the existing launcher after stopping an older controller session:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/start_gamebub_controller.ps1 -Profile wow
```

Validation uses fake virtual-controller output plus localhost AV sessions,
including audio enabled/disabled. It covers all 4,096 WoW masks, elapsed-time
cadence invariance, gradual/capped speed, normalized diagonals, direction changes,
neutral/release, stale rejection and driver cleanup. No physical controller was
running during development, no new handheld session was started, and the actual
in-game camera feel remains for the operator to check. Installed Sunshine stays
running unchanged; no native build or driver installation is needed.

Final validation: 38 focused controller/session tests pass. The full host suite
completes 401 tests with five existing skips. `gamepad_backend`, `windows_gamepad`
and `live_session` reach 100% statement/branch coverage (386 statements,
138 branches). Ruff, diff whitespace and PowerShell launcher parsing pass.
Evidence is retained locally under `artifacts/wow-camera-*`; generated logs and
coverage files are excluded from the source commit.
