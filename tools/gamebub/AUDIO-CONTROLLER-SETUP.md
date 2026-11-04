# Windows audio and controller setup

The Windows preparation components are implemented and locally tested. The
published AV v1 headers now have a tested Windows packet/session adapter; see
[protocol0.7.0](protocol/0.7.0-av-v1.md) and the
[conformance report](measurements/av-v1-conformance-20261103.md). All7 wire vectors
and the exact decoded-PCM oracle match after implementing the receiver's required
product-based rounding in encoder and decoder. A live AV
socket runner and physical receiver qualification are still pending. Existing
MSV1 video remains video-only; do not launch these
commands expecting sound or controller operation on the handheld.

## Install the isolated laboratory dependencies

Use the candidate worktree `C:\ai\sunshine-gamebub`; preserve its existing changes.
From its `tools\gamebub` directory:

```powershell
py -3.11 -m uv sync --locked --extra windows-audio
```

`PyAudioWPatch` is an optional Windows-only dependency locked at0.2.12.9. The
default test environment can still run without it; only actual loopback capture
requires the extra. It captures the default output endpoint, not the microphone,
and does not change the default playback device. API reference:
[PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch).

## Capture and validate audio locally

From the repository root, run each command separately:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked --extra windows-audio python windows_audio.py --seconds 5 --output artifacts/my-loopback.wav'
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked python audio_codec.py artifacts/my-loopback.wav artifacts/my-adpcm.wav'
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked python make_audio_assets.py artifacts/my-audio-fixtures'
```

Use new output paths: captures/conversions and fixture directories refuse to
overwrite prior evidence. Audio capture is limited to60 seconds per diagnostic;
this command is not a long-running network sender. Reads raise on overflow or
short blocks rather than claiming uninterrupted audio. The current host's
Realtek endpoint advertises8 channels; a stereo shared-loopback request succeeds,
while the eight-channel request failed. Device enumeration is not proof that
every advertised format opens. Other output devices require their own probe.

The codec now explicitly implements the receiver's full-product IMA rounding in
both encoding feedback and decoding, producing512-byte independent stereo blocks
with505 sample frames. PyAV resamples the source to48,293Hz; it does not choose
the ADPCM reconstruction arithmetic. The encoder and local decoder share their
reconstruction primitive, so the independent frozen2020-byte PCM oracle and the
encoder's rounding-counterexample regression remain necessary validation.
The [contract clarification](https://github.com/AEW2015/moonbub/blob/aab1ba337550ba472c30ee417fcf6d439b5a7f1e/docs/av-wire-v1.md)
specifies the exact product/sign/clamp/index order.

Fixture output includes source/decoded PCM WAVs, an ADPCM WAV, raw concatenated
`blocks.ima` (no packet headers), and a versioned manifest with per-block encoded
and reconstructed PCM SHA-256, encoder identity and PyAV/FFmpeg versions. Left is440Hz, right880Hz at
amplitude4096; twenty blocks contain10,100 sample frames. Codec-version changes
may change encoder choices; use the manifest when comparing peers.

## Build and probe the virtual Xbox backend

The adapter uses the repository-pinned `third-party/ViGEmClient` revision
`8d71f6740ffff4671cdadbca255ce528e3cd3fef`. From the repository root:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'bash tools/gamebub/build_windows_gamepad.sh'
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked python windows_gamepad.py --dll C:/ai/sunshine-gamebub/cmake-build-gamebub-vigem/libViGEmClient.dll'
```

The separate DLL statically links its MinGW runtime dependencies and does not
replace Sunshine files. The probe only attaches a neutral controller and removes
it; it never sends button presses. Actual driver errors are reported with their
hex status. The current machine returns `0xe0000001` (bus not found), matching
the absent ViGEmBus service/device. No driver was installed during this work.

A real virtual-controller test requires the signed driver separately. The
upstream project's final release is
[ViGEmBus1.22.0](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0);
the project is archived. This setup does not silently run its installer or
restart Sunshine/Windows. An alternative backend can be supplied through the
same `set_buttons()` interface after its platform/driver requirements are tested.

`OrderedInput` supplies session/sequence rejection and timeout release, with
neutral analog axes/triggers. A future socket runner must establish the peer,
validate the agreed packet and call expiry even during silence. Its local
session/sequence types are provisional, not a published network message.
It is deliberately not connected to unsequenced MSF1 snapshots.

## Validation recorded on2026-11-03

Current validation after the rounding clarification: all seven wire vectors and
the exact PCM oracle pass,245 tests completed with5 existing integration skips,
and23 focused regressions have100% statement/branch coverage. The capture and
initial FFmpeg checks below are retained as earlier evidence. Use the new
`audio-fixtures-product-v2-20261103/` and `av-v1-product-vector-report-20261103.json`
artifacts for the product-rounded codec; do not substitute the earlier raw-block
or decoded-PCM hashes.

- Real five-second48kHz stereo loopback:240,000 frames,5.223s wall time,
  peak magnitude32,768 and RMS5,004.19; nonzero captured output. No recording
  overflow was reported. Source content/listening quality was not independently
  verified.
- Resampling to48,293Hz:478 blocks/241,390 decoded stereo frames,75 tail frames
  explicitly discarded at EOF; all478 blocks decoded in fresh contexts.
- Proposed raw payload rate391,699bits/s, before headers or Wi-Fi overhead.
- ViGEm DLL built/loaded; real attach blocked by absent driver. No physical
  controller or game-input result is claimed.
- All22 new regressions passed, with100% statement/branch coverage across336
  statements and114 branches. Full lab discovery:230 tests,5 skipped existing
  integration tests, no failures. Ruff checks and formatting passed.
- Installed `SunshineService` remained running; no receiver packets, driver
  installations, default-device changes or service restarts were performed.

Artifacts under `tools/gamebub/artifacts`: `windows-audio-loopback-stereo-20261103.*`,
`windows-audio-adpcm-20261103.*`, `audio-fixtures-v1-20261103/`,
`windows-controller-probe-static-20261103.txt`, `av-input-tests-20261103.txt`,
`av-input-coverage-20261103.txt` and `av-input-full-tests-20261103.txt`.
Failed earlier device-format probes are also retained; use the stereo result.

For focused regressions from the repository root:

```powershell
C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'cd tools/gamebub && py.exe -3.11 -m uv run --locked python -m unittest -v test_windows_audio test_audio_codec test_windows_gamepad test_audio_assets'
```

## Receiver handoff

The published AV v1 contract supersedes the provisional0.6.0 proposal. Its PCM
rounding oracle now passes locally. Next validate the
raw512-byte fixture blocks and returned decoded hashes before enabling sound.
Then test audio-only, ordered controller-only and finally5fps video with reserved
audio bandwidth. Keep current firmware/FPGA changes independently identifiable.
Do not add392kbps audio to a fully used2Mbps video budget and call the aggregate
rate2Mbps; agree and measure the combined scheduler first.
