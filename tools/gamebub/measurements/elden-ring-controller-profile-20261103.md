# Elden Ring movement and face-button profile

The operator confirmed that the standard Xbox controller worked in the game,
then requested D-pad movement and A/B/X/Y combat actions. An explicit
`elden-ring` host profile now implements that mapping. The standard profile
remains unchanged; the AV v1 packet format and raw twelve-button masks do not
change.

| Game Bub input | Xbox report | Intended game action |
| --- | --- | --- |
| D-pad | Left analog stick | Movement |
| A | RB | Light attack |
| B | Left-stick click | Crouch/stand |
| X | LT,255 while held;0 on release | Operator-confirmed shield/guard |
| Y | Xbox A | Jump |
| L/R | LB/RB, unchanged | Existing shoulder actions |
| Start/Select | Start/Back, unchanged | Existing menu/map actions |

The first profile used X→LB, following the game's default mapping documented in
the [publisher's controls guide](https://en.bandainamcoent.eu/elden-ring/news/elden-ring-starter-guide-tips-know-playing-the-game).
The operator reported that X invoked a spell in the current setup and requested
the second left shoulder instead. X was changed to LT; the operator then
confirmed it works. This is the operator's verified current configuration, not
a claim that LT is the game's universal default guard action.

## Movement and release behavior

Cardinal stick coordinates are±32767 with positive Y meaning up. Diagonals use
±23169 per axis to stay within the cardinal magnitude. Opposing directions
cancel on each axis. The original digital D-pad flags are suppressed in this
profile so movement does not simultaneously cycle equipment. Every complete
snapshot recomputes the full stick/button/trigger state; release and timeout
neutralize movement and LT. The right stick and right trigger stay neutral.

The native ctypes report supports validated signed16 left-stick coordinates,
left-stick click and left trigger0..255. Existing `set_buttons()` still sends
neutral axes/triggers; only the explicitly selected profile uses the expanded
report. No keyboard input or extra analog inputs were added to the wire.

## Validation

- Seventeen focused tests passed with100% statement/branch coverage over256
  source statements and90 branches. Cases include every direction combination,
  normalized diagonals, opposite cancellation, simultaneous actions, movement/
  trigger release, invalid axes/triggers, profile selection and driver failure.
- Full lab discovery completed254 tests in18.317 seconds with5 existing
  integration skips and no failures. Ruff checks and formatting passed.
- The initial profile's independent Windows XInput trace captured left-stick
  movement, including diagonals, while the operator confirmed movement/actions.
- After the LT correction, XInput captured left-trigger255 on presses,0 on
  releases, zero right trigger and the requested left-stick movement. The
  operator explicitly confirmed the final mapping works in the game.
- Sunshine remained Running under the same service process ID7420. No driver,
  game configuration, saved volume/routing or installed Sunshine file changed.

## Active session and evidence

The current visible controller console runs `-Profile elden-ring` for up to two
hours. It connected from192.168.0.47:64052 to192.168.0.157:5534 with cookie
`e26a2752fc7969db`. Its log is
`artifacts/controller-20261104T023909340706Z.jsonl`. Audio and video are off;
do not start a competing AV audio session while this controller owns the cookie.

Restart with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/gamebub/start_gamebub_controller.ps1 -Profile elden-ring
```

Earlier controller sessions were closed solely to apply the requested mapping.
The standard session did not respond to a programmatic console Ctrl+C, so the
verified AV-client leaf process was terminated and the receiver lease allowed
to expire before reconnecting. Its final summary was unavailable; its existing
log was retained. The intermediate LB session was similarly stopped for the
explicit LT change. No unrelated Python or Sunshine process was stopped.
Closing the controller console remains an available way to disconnect if a
console interrupt does not end its child process; device/lease cleanup must not
be confused with a confirmed STOP acknowledgment.

Evidence: `artifacts/elden-profile-tests-20261103.txt`,
`elden-profile-coverage-20261103.txt`, `elden-lt-profile-tests-20261103.txt`,
`elden-lt-profile-coverage-20261103.txt`, `elden-lt-profile-full-tests-20261103.txt`,
`elden-profile-20261103/xinput-events.jsonl`,
`elden-lt-profile-20261103/xinput-events.jsonl` and their result JSONs. Both
monitors retain the initial transient axis samples as in the earlier device
test; subsequent control reports show the requested movement/release state.

This does not supply right-stick camera control, heavy attack, dodge/sprint,
interact or item-selection mappings beyond the table. Those remain separate
binding decisions rather than silently changing the requested controls.
