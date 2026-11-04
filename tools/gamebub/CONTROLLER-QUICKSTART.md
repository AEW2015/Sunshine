# Use Game Bub as a Windows game controller

## World of Warcraft profile

Launch `start_gamebub_controller.ps1 -Profile wow` after stopping any previous
AV session. D-pad controls the left stick (character movement); X looks up,
Y left, A right and B down through the right stick (camera). Diagonals are
normalized and opposing directions cancel independently on both sticks.
L/R remain LB/RB, Start/Select remain Start/Back, and triggers stay neutral.
No spells, jump or interaction bindings are assigned. The input lease releases
all axes and buttons after500ms without fresh valid MSI1 input.

Use a WoW client with native controller support enabled. If disabled, the
commonly used in-game command is `/console GamePadEnable 1`, documented in the
[Blizzard-hosted community guide](https://us.forums.blizzard.com/en/wow/t/guide-to-the-new-gamepadcontroller-support-in-901/683913).
Game version, camera inversion and custom/addon bindings can affect behavior;
the launcher does not edit WoW settings, install addons or inject keyboard/mouse
events. Validate movement and camera in-game before treating the profile as
qualified for that installation. All other profiles remain available.

## Mass Effect profile

Launch `start_gamebub_controller.ps1 -Profile mass-effect` after stopping the
previous controller session. This input-only profile maps D-pad to the left
stick; X/Y/A/B to aim up/left/right/down on the right stick; L to LT (aim),
R to RT (fire), Select to LB (tap weapon switch / hold weapon wheel), and
Start to Start. Both sticks use full cardinal deflection, normalized diagonals,
and cancellation of opposing directions. Releasing buttons or input timeout
neutralizes both sticks and triggers. Face buttons produce aim only; use the
PC controls for interact, reload, and menu confirmation. No game settings are
changed. Game edition/custom bindings may change the action of each Xbox input.
The original [EA Xbox manual](https://eaassets-a.akamaihd.net/eahelp/manuals/mass-effect-manuals_Microsoft%20XBOX360_en_US.pdf)
documents LT zoom, RT fire and LB weapon switching. Physical/game validation of
this new profile remains pending.

The handheld's AV v1 MSI1 button packets and Windows Xbox/XInput output now pass
physical validation for all twelve digital controls and releases. The opt-in
adapter forwards validated snapshots to a virtual Xbox360 controller. Actual
game recognition/response remains to be confirmed by the operator. See the
[first Windows-controller report](measurements/windows-gamepad-first-20261103.md).
Video and audio remain off in this controller launcher. The installed Sunshine
service is not replaced or restarted.

## One-time setup

From `C:\ai\sunshine-gamebub`, build the pinned user-mode backend:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'bash tools/gamebub/build_windows_gamepad.sh'
```

Stage/verify the signed driver, then install it:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/setup_windows_controller.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/setup_windows_controller.ps1 -Install
```

The second command requires Windows administrator consent. The elevated Windows
PowerShell process runs the verified Nefarius installer with `/exenoui /qn
/norestart`, matching the [WinGet package manifest](https://github.com/microsoft/winget-pkgs/blob/master/manifests/v/ViGEm/ViGEmBus/1.22.0/ViGEm.ViGEmBus.installer.yaml);
it does not restart Windows or Sunshine. If consent is declined or
installation fails, no controller success is claimed. If the installer returns
3010, its result records that Windows requests a restart; no restart is automatic.

Installer: [official ViGEmBus1.22.0 release](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0).
Staged under `tools/gamebub/artifacts/controller-setup-20261103/`.
SHA-256: `89220a7865076b342892f98865f3499fb7c4cfd673159e89d352c360fd014c6a`.
The setup script rechecks both this hash and valid Authenticode with the Nefarius
signer before execution. It leaves the existing Virtual Desktop gamepad bus in
place. Installing the driver by itself does not create a controller; the running
client creates and owns one for its session.

Probe neutral attach/remove:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked python windows_gamepad.py --dll C:/ai/sunshine-gamebub/cmake-build-gamebub-vigem/libViGEmClient.dll'
```

## Connect and play

The handheld must accept this host's IPv4 address and support the AV v1 input
session at192.168.0.157:5534. From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/start_gamebub_controller.ps1
```

This runs input-only with Xbox injection enabled for up to two hours. Keep its
console open. Ctrl+C ends the session, releases held controls and removes the
owned virtual controller. Stop is not a Sunshine service operation.
For a thirty-second check use `-Seconds 30`. For packet observation without
injection use `-ObserveOnly`. Receiver/bind addresses can be overridden with
`-Receiver` and `-BindAddress`.

Open Windows Game Controllers (`joy.cpl`) and check that the Xbox controller
appears, then press/release A and each D-pad direction. Check the game after
that; some games enumerate controllers only at startup. Do not treat packet
logging as proof of Windows input or gameplay. Validate timeout release and
controller removal before considering the path qualified.

The Python launcher fetches only two pinned reference files into its isolated
runtime cache, verifying their SHA-256 values before execution. Modified cache
files are rejected rather than overwritten. It sets the child module path to
the tested local `gamepad_backend.py`; no `vgamepad` package or automatic driver
installer is imported. Audio flags are not exposed by this controller-only
launcher. It uses the published independent MSI1 ordering and500ms input lease,
never MSF1 button snapshots. Logs get fresh UTC-stamped names under `artifacts`.

An AV receiver has one active cookie/endpoint at a time. A separate audio client
and this input-only client must not compete for the same active AV session;
combined audio/controller operation needs one owning session. The legacy video
test uses a separate protocol/port and is unaffected by this launcher.

## Available controls

| Game Bub | Xbox |
| --- | --- |
| A/B/X/Y | Same named face buttons |
| D-pad | D-pad |
| L/R | LB/RB |
| Start/Select | Start/Back |

Analog sticks, analog triggers and stick-click buttons remain neutral/unavailable
in the standard profile. Digital-controller games and menus can use these controls; games that
require analog movement/camera or triggers need an explicitly selected mapping
or additional controls. No D-pad-to-stick conversion is silently applied.

### Elden Ring profile

The operator's confirmed mapping is available explicitly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/start_gamebub_controller.ps1 -Profile elden-ring
```

D-pad becomes normalized left-stick movement; A sends RB (light attack), B sends
left-stick click (crouch), X sends LT while held (the operator's working guard
binding), Y sends Xbox A (jump). Shoulders and Start/Select retain their standard
mapping. Right-stick camera and right trigger remain unmapped. Releases and the
input timeout neutralize the stick and LT. See the
[profile report](measurements/elden-ring-controller-profile-20261103.md) for
tests, game confirmation and the operator-requested LB→LT correction.
The physical Game Bub face names differ from the Xbox prompts in this profile.
Use the standard profile for the original same-name mapping.

## Current verification

Driver installation returned0 with administrator consent and no reboot; the
neutral native attach/remove probe passed. The physical60-second test confirmed
all twelve controls via independent Windows XInput reads, including releases and
device removal at the end. A regular input-only controller session was then left
running in its console for game testing. Six adapter/launcher unit tests pass
with100% coverage over93 statements and26 branches; full lab discovery passes251
tests with5 existing integration skips at that milestone. The operator has now
confirmed game response; the later Elden Ring profile passes254 tests with5
existing skips and has operator-confirmed movement/actions. A console interrupt
may not stop every child on this Windows setup; close the controller console
to disconnect if Ctrl+C does not end it.
