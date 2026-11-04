# Game Bub to Windows Xbox controller: first physical check

The operator requested a game-facing Windows controller. The existing AV v1
physical input-only test had already demonstrated ordered MSI1 button snapshots,
but the machine lacked the ViGEm interface required for Xbox output.

## Driver and adapter setup

Downloaded the official ViGEmBus1.22.0 installer and verified its valid Nefarius
Authenticode signature and SHA-256
`89220a7865076b342892f98865f3499fb7c4cfd673159e89d352c360fd014c6a`.
The first attempt used unsupported `/install /quiet` bootstrapper switches and
failed with an Invalid Command Line dialog before installation. Its result was
preserved as `installation-result-attempt1.json` (exit-536870911).

The retry used `/exenoui /qn /norestart`, matching the
[Microsoft WinGet manifest](https://github.com/microsoft/winget-pkgs/blob/master/manifests/v/ViGEm/ViGEmBus/1.22.0/ViGEm.ViGEmBus.installer.yaml).
The operator supplied Windows administrator consent. The installer returned0,
with no reboot required or requested. The neutral native probe then attached
and removed an Xbox target successfully, with no cleanup errors. The existing
Virtual Desktop bus was not removed or altered by this work.

`gamepad_backend.py` adapts the published client to the built, pinned ViGEm DLL.
`gamepad_client.py` launches only the reviewed, SHA-pinned input-only reference
client and protocol, with injection opt-in. Cache modifications are rejected;
there is no package-triggered driver install. The public PowerShell launcher
enables the virtual controller and supports Ctrl+C shutdown.

The six new adapter/launcher tests passed with100% coverage across93 statements
and26 branches. Full lab discovery completed251 tests in16.610 seconds, with5
existing integration skips and no failures. Ruff checks/format passed; setup
and launcher PowerShell files parsed successfully. Installer testing is separate
from those fake-driver unit tests.

## Sixty-second live verification

| Measurement | Result |
| --- | --- |
| Host / receiver | 192.168.0.47:53767 /192.168.0.157:5534 |
| Cookie | `b59b42c084f94cb0` |
| Requested active duration | 60 seconds |
| Reference loop MSI1 records | 2,862, sequences1..2862 |
| Initial handshake ACTIVE MSI1 | Accepted before the loop |
| Invalid/stale packets / input timeouts | 0 /0 /0 |
| Audio/video | Off |
| Gamepad injection | On |
| Windows XInput slot | 0; no baseline connected slots |
| Test end | Neutral controls and target removal observed |

An independent process polled Windows `XInputGetState`. It observed all twelve
digital Xbox controls: A/B/X/Y, Up/Down/Left/Right, LB/RB, Start/Back; D-pad
diagonals and combined Start/Back were also observed. Releases returned to zero.
This verifies game-facing Windows XInput, beyond logging incoming MSI1 packets.
No synthetic button presses were generated; reports came from the handheld.
The test's end removed the newly created XInput device.

The first XInput enumeration sample had nonzero stick values within a few
thousand units. Subsequent digital reports and the persistent-session snapshot
showed zero axes/triggers. This startup observation is retained in the raw
monitor log; no analog-control functionality or universal neutral-start behavior
is inferred. The profile sends neutral axes/triggers and no analog inputs exist
in AV v1. Physical game response, deadzone behavior and user comfort remain
separate checks.

## Regular session left available for games

Started the normal controller launcher in a visible console titled
`Game Bub Xbox Controller (Ctrl+C to disconnect)`, for up to7,200 seconds.
Its handshake succeeded from192.168.0.47:63300 with cookie`0e686c99779f2d18`.
At the recorded independent snapshot, XInput slot0 was connected with all
buttons, sticks and triggers neutral. The input log was advancing and the
operator was asked to verify game recognition/response. That game result is
pending, so this report does not claim gameplay validation.

The current session is input-only and owns the AV cookie; do not run a competing
standalone audio client against that receiver while it is active. Combined
audio/controller streaming must share one owning session. The session stops on
Ctrl+C, its duration limit, error or missing newer MSI1 for500ms, releasing
controls/removing its owned controller. This task intentionally leaves this
operator-visible controller session running; it is not a Sunshine service.

Some games may require reopening after controller creation. Digital controls
are available, but games requiring analog movement/camera or triggers need an
explicit additional mapping or controls. No implicit D-pad-to-stick conversion
was introduced.

Installed Sunshine remained Running with the same service process ID7420 before
and after setup; no Sunshine files, configuration or service lifecycle changed.

See [controller quickstart](../CONTROLLER-QUICKSTART.md) for repeatable commands.
Evidence lives under `artifacts/controller-setup-20261103/`: installer signature
and result files, neutral probe, unit/full-test logs, `first-gamepad.jsonl`,
`xinput-events.jsonl`, `xinput-result.json`, `persistent-xinput-state.json`,
process records, and Sunshine before/after snapshots. The regular session log is
`artifacts/controller-20261104T022640941988Z.jsonl` (UTC-stamped filename).
