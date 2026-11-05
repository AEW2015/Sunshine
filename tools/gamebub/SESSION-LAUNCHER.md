# Finite Windows Game Bub session launcher

`session_launcher.py` and `start_gamebub_session.ps1` consolidate the existing
MSV1 JPEG video, AV v1 product-rounded PC audio and profile-selected Xbox input.
This is a standalone laboratory sender. It does not implement the v20 custom
codec, change game bindings, install drivers, flash hardware or replace/restart
the installed Sunshine service. Existing receiver compatibility must be confirmed
before a hardware test. Stop an existing AV session first: the receiver has one
AV owner/cookie at a time. This launcher does not kill unrelated sessions.

From `tools/gamebub`, prepare the locked Windows audio environment:

```powershell
py.exe -3.11 -m uv sync --locked --extra windows-audio
```

Use a new output directory and an unused frame-ID range. A dry run writes only
the manifest and prints the video command; it opens no socket, capture device or
virtual controller:

```powershell
.venv\Scripts\python.exe session_launcher.py --receiver 192.168.0.157 --bind 192.168.0.47 --video --audio --gamepad --profile wow --seconds 60 --fps 5 --quality 25 --mbps 2 --gain 0.75 --start-frame-id 80000 --output artifacts/session-preview --dry-run
```

After inspecting the manifest, omit `--dry-run` and use another new output
directory to run the selected modes. PowerShell equivalent:

```powershell
.\start_gamebub_session.ps1 -Receiver 192.168.0.157 -BindAddress 192.168.0.47 -Video -Audio -Gamepad -Profile wow -Seconds 60 -FPS 5 -Quality 25 -Mbps 2 -Gain 0.75 -StartFrameId 80000 -Output artifacts/session-live
```

Every media/injection mode is opt-in. Omit `--audio` for video plus controller,
omit `--gamepad` for no Windows injection, or select `--video` alone for the
existing video-only path. Input observation still occurs in audio sessions;
only `--gamepad` creates a virtual controller. Profiles are `standard`,
`elden-ring`, `mass-effect` and `wow`. The driver/DLL must already be prepared
for injection; see `CONTROLLER-QUICKSTART.md`.

### Input-only AV, saved clips and optional wait

`--av-input` selects a real AV owner without PC audio capture or virtual-gamepad
injection. Combine it with `--video` for the input/video coexistence test.
Video starts after AV ACTIVE; AV remains active until the owned video sender
has exited, including final feedback/log drain. A finite five-second video
grace prevents a stuck sender from keeping AV alive indefinitely. STOP is
sent through normal AV cleanup; its exact wire bytes and success are logged.

`--clip PATH` selects a saved clip instead of desktop capture; `--loop-clip`
reopens it at EOF without retaining decoded history. Empty clips terminate.
Clip paths are made absolute before the child changes directory, and the
manifest records the file SHA-256 and start offset zero. Source proportions
are preserved; the active viewport can differ from 720×405 for non-16:9 input.

`--pacing-wait sleep` is the unchanged default. `--pacing-wait precise` opts
into a blocking Windows high-resolution timer with deadline rechecks, no spin
and visible fallback. The selected mode, backend/fallback counters and cleanup
are recorded. This option is experimental: a more precise API name does not
establish a measured speed improvement. The earlier spin-tail lab adapter is
not enabled by this flag. A separate process timer-period helper is not
selected by either launcher mode.

`--pacing-wait hybrid` explicitly requests a bounded native spin tail, defaulting
to 600 microseconds. `--pacing-spin-us 400` selects a smaller tail; the accepted
range is 0–1000 microseconds and a nondefault value requires hybrid mode.
Its wait-thread CPU and spin counters are reported. Fallback disables
the tail; it does not silently busy-spin on unsupported systems. This remains
an experimental CPU/precision tradeoff, with no default behavior change.

PowerShell equivalents: `-AvInput`, `-Clip PATH`, `-LoopClip`,
`-PacingWait precise`, or `-PacingWait hybrid -PacingSpinUs 400`.
All existing media flags remain explicit.

The launcher's `--bind` now binds both the AV socket and video child to that
source IPv4 address. The standalone sender keeps its wildcard default unless
`--bind` is selected. Video logs record the actual local and peer endpoints;
the capture filter must match those addresses. This avoids silently choosing
another source interface for video on a host with multiple adapters.
`-VideoSourcePort` and `-AvSourcePort` expose the existing source-port options
in PowerShell. Their defaults remain ephemeral; distinct free nonzero ports
can be reused across a matched comparison without retaining old session cookies.
Route preflight binds that source before connecting its probe, so a valid
explicit bind need not match Windows' wildcard default. Lost log records or
log I/O errors produce a nonzero CLI result; they describe incomplete evidence
and do not turn successful video sends into receiver drops.

`--clip-selection legacy` retains the existing hold-based clip resampler. At
equal nominal rates, rounded source PTS can make it repeat and skip native
frames; slot FPS alone must not be presented as unique source-frame FPS.
`--clip-selection native` instead decodes each original frame once and requires
the source's nominal rate to equal `--fps`. It checks strictly increasing
rational PTS and cadence within one source tick and less than half a frame.
Mismatched-rate or variable-cadence inputs fail visibly. Looping reopens and
closes the decoder; it does not retain a frame history. The PowerShell option
is `-ClipSelection native`. Desktop capture and the default remain unchanged.

### Owned capture through STOP

`--capture-interface INTERFACE` opts into an installed dumpcap capture. An AV
owner is required so STOP can delimit coverage. The launcher requires dumpcap
and neighboring tshark, starts capture before AV, confirms native readiness
and file creation, and checks capture health during the session. No tools or
drivers are installed. Use `dumpcap -D` to select the actual intended interface;
never copy an interface number from another machine.

The filter includes UDP between the explicit sender/receiver addresses on the
selected video/AV ports, in both directions. Native stderr and numeric capture
statistics are retained. Capture's safety autostop is the requested media
duration plus 120 seconds; successful finalization waits for natural exit,
which can keep the launcher alive for roughly two minutes **after media STOP**.
`media_end_utc` and final `end_utc` distinguish these intervals. An early capture
exit aborts the session and cannot report complete coverage. The capture owner
uses a conservative post-readiness deadline and does not force-stop a successful
capture merely to finish early.

The launcher then uses tshark to verify the exact successfully sent STOP
datagram, including cookie, sequence and CRC, at the capture point. Lifecycle
completion alone is not packet-level STOP evidence. Missing/failed verification,
forced cleanup or missing capture statistics produces an incomplete result.
Capture drop counts remain explicit; zero host-capture drops still do not prove
radio delivery or receiver reception. The selected interface may expose Ethernet
encapsulation rather than raw 802.11 frames.

`--capture-executable PATH` overrides dumpcap's installed location. PowerShell
equivalents are `-CaptureInterface` and `-CaptureExecutable`. Dry-run never
starts capture, AV, media or a virtual controller.

## Preserved contracts and bounded behavior

- Video remains baseline JPEG in MSV1 on UDP5533,720×480 with720×405 active
  16:9 content, zero host shift, fixed requested JPEG quality, packet timestamps
  and a bounded existing latest-frame pipeline. No JPEG is labeled H.264.
- AV v1 uses the tested local48-byte-header/whole-packet-CRC serializer and
  nonce/cookie HELLO/OFFER/START handshake on UDP5534. One socket owns audio,
  keepalive, independent MSI1 input ordering and STOP. Profile routing preserves
  all twelve raw Game Bub bits. No newer MSI1 for500ms neutralizes input and
  fails the session, even when no button was held.
- PC audio uses default-speaker WASAPI callback capture, never a microphone.
  Native mono/stereo capture is resampled to48,293Hz stereo, then encoded by
  `audio_codec.AudioEncoder` with the product-based IMA rounding selected by
  the receiver. There is no FFmpeg ADPCM encoder substitution.
- PCM callbacks only enqueue into eight bounded native chunks; encoding occurs
  off the callback. A full PCM queue or native status/short block fails visibly
  rather than silently compressing the sample clock. Four encoded blocks are
  retained; the oldest is discarded when full, after allocating its sequence.
  Audio older than80ms is dropped. Each transmitted or stale-dropped block is
  logged with sequence and age; encoded-queue eviction totals are separate and
  transmitted sequence holes remain visible. No retransmission or unbounded
  catch-up burst occurs.
- No callbacks for2s emits `audio_source_inactive`; fresh callbacks emit
  `audio_source_resumed`. Silent/inactive endpoints can stop callback delivery.
  The launcher does not invent silence or claim playback during inactivity.
  Inactivity keeps the finite video/input test running and is a visible limit,
  not a confirmed capture-driver error. `--source-timeout` changes that threshold.
- Capture shutdown joins for2s and records `shutdown_complete=false` if native
  cleanup does not finish; the CLI returns failure. Resampler tail frames and
  complete tail blocks are reported but never padded/sent after STOP. Audio
  queue counters distinguish encoded, dropped and queued-unsent blocks.
  Final accounting separately records captured source frames, encoded source
  frames, dropped PCM frames and queued PCM block/byte/frame totals. An incomplete
  worker shutdown can still have in-flight native work; it is never a clean drain.
- The video child is started after AV ACTIVE, uses the base Python interpreter
  directly with locked environment package paths, and is monitored for nonzero
  early exit. The route preflight requires its routed source IP to equal the
  explicit AV bind IP. UDP connect sends no datagram. Mid-session route changes
  are not protected by this preflight.
- Only the spawned video process is waited/terminated/killed on cleanup. Normal
  drain grace is5s; termination/kill waits are2s each. Callback/native cleanup
  limits are reported separately. Synchronous driver and local-file operations
  are not hard real-time guarantees. Do not interpret the finite duration as a
  proven end-to-end latency bound.

The2Mbps setting is the video cap; audio adds bandwidth. No shared AV transport
budget, receiver admission-wait change or audio priority firmware policy is
introduced. Those need separate measured comparisons. The complete49,152-byte
AR03 cap and v20 packet permits are not applied to the working JPEG endpoint.
Requested video frame-ID ranges that would wrap32bits are rejected before any
socket or capture opens; choose a fresh nonwrapping range.

## Evidence and verification

Each new output directory contains `manifest.json`, `av.jsonl`,
`session-summary.json`, and, when video is enabled, `video.jsonl`,
`video-summary.json` and `video-stderr.txt`. The manifest records settings,
canvas geometry, source hashes and route preflight. Logs distinguish source
inactivity, audio send/stale-drop events, MSI1 sequence/status, capture queue
loss, video frame/packet timing and final logger failures/drops. A snapshot-valid
clear MSI1 exposes FPGA played/queued/underrun values as null. Admission
rejections/unconfirmed outcomes are not assumed to be Wi-Fi loss.

Focused fake-device tests and real localhost UDP tests cover handshake/control,
product-audio datagram parsing, sequence/CRC, audio-off behavior, all4096 button
mask round trips, selected profile output and neutral release. They do not
prove WASAPI callback behavior on the actual Realtek endpoint or hardware
decode/presentation/audio quality. Run those physical checks as a separate
versioned test before replacing the artifact-only laboratory commands.

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'py.exe -3.11 -m uv run --locked --extra windows-audio python -m unittest test_live_audio test_live_session test_session_launcher test_live_session_loopback'
```
