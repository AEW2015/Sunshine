# Mass Effect controller profile

Implemented and activated the operator-requested `mass-effect` profile on
2026-11-03 (America/Denver). After the operator-requested X/Y and A/B swaps,
D-pad maps to left-stick movement; X aims up, Y left, A right, B down using
the right stick. L sends LT255 while held; R
sends RT255 while held. Select sends LB for weapon switching/wheel, Start
sends Start. Both sticks cancel opposing directions and normalize diagonals
to23169 per axis, with32767 cardinal deflection. All other digital flags remain
clear. No face-button actions, interaction, reload, or menu confirmation are
available in this profile; use PC controls for those actions.

The original [EA manual](https://eaassets-a.akamaihd.net/eahelp/manuals/mass-effect-manuals_Microsoft%20XBOX360_en_US.pdf)
documents trigger aim/fire and LB weapon switching. Edition/custom bindings
still require operator game validation. No game settings were modified.

Validation:19 focused controller tests passed, with100% statement and branch
coverage across269 statements/94 branches in the three controller modules.
Exhaustively checked4096 masks for both sticks, shoulder triggers, weapon and
pause buttons, opposing directions and simultaneous combinations. Fake-driver
tests verify native report field order, right-axis/trigger bounds, neutral
release and driver failure cleanup. Full lab suite:256 tests,5 existing skips,
19.818seconds. Ruff checks passed for all five modified Python files.
Standard and Elden Ring mapping regression tests remain passing.

Switched only the owned previous input-only client after verifying its PID and
exact pinned runtime/log command line; waited800ms for the500ms input lease.
New visible console PID37040, source192.168.0.47:65256 to192.168.0.157:5534,
cookie`d1542d451f26ef53`. ACTIVE handshake and advancing MSI1 confirmed.
Log:`artifacts/controller-20261104T030501345837Z.jsonl`.
Audio/video are off. SunshineService remains running with PID7420.
Physical button-to-XInput and in-game action validation for this new profile
remain pending; automated tests and session liveness are not gameplay proof.

Reproduce from the candidate root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/start_gamebub_controller.ps1 -Profile mass-effect
```

Stop the existing AV controller session before launching another profile.
