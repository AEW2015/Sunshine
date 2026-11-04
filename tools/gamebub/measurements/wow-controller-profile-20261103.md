# Simple WoW controller profile

Added and activated `wow` on2026-11-03 America/Denver. D-pad drives left-stick
movement. Face buttons drive right-stick camera with the operator's preceding
layout: X up,Y left,A right,B down. Cardinal deflection32767, normalized
diagonals23169, opposing directions cancel independently. L/R remain LB/RB,
Start/Select remain Start/Back. Triggers remain zero; no face-button actions,
spell rotation, interaction, jump or keyboard/mouse injection are added.
Existing standard, Elden Ring and Mass Effect profiles remain available.

The opt-in launcher still uses pinned AV v1 input sequencing and500ms release
lease. WoW needs native controller support enabled and suitable stick bindings.
The launcher does not change game configuration or install addons. In-game
`/console GamePadEnable 1` is described by the
[Blizzard-hosted community guide](https://us.forums.blizzard.com/en/wow/t/guide-to-the-new-gamepadcontroller-support-in-901/683913).
Client edition, custom bindings and camera inversion may affect game behavior.

Validation:20 focused controller tests passed in0.922s. Exhaustively checked
all4096 WoW masks, normalized independent sticks, shoulders/menu flags,
neutral triggers, neutral release and driver failure cleanup. Three controller
modules have100% statement/branch coverage (275 statements,96 branches).
Ruff checks passed. No native code changed; no build/driver install needed.

No previous AV controller process was running at launch. New console PID15976,
source192.168.0.47:53755 to192.168.0.157:5534, cookie`7fc3e7f39d609257`.
ACTIVE handshake and advancing MSI1 confirmed. Log:
`artifacts/controller-20261104T043133797853Z.jsonl`. This validates session
liveness, not physical button-to-XInput or actual WoW movement/camera, which
remain pending operator testing. Audio/video are off. SunshineService remains
running, PID7420, untouched.

From candidate root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/start_gamebub_controller.ps1 -Profile wow
```

Stop the current AV session before launching another profile.
