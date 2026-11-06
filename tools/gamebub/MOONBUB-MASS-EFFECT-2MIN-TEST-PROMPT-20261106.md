# MoonBub prompt: Mass Effect two-minute video test

The user START confirmed 20 fps/Q35, superseding the original 24 fps/Q25 proposal. This document records the approved setup. Do not start transmission until both agents confirm fresh readiness and recording coverage. This replaces the Xonotic source and desktop capture; it is not a matched-content firmware comparison.

## Send this to the MoonBub agent

Please prepare a **120-second video test** using the new Mass Effect Legendary Edition combat clip on the Windows host. Keep V38/build50, overlap and the 32-slot queue unchanged unless you report a different installed identity before the run.

The Windows source file is:

`C:\Users\lavat\Downloads\YTDown.com_YouTube_Media__luGrl_3Ajc_Mass-Effect-Legendary-Edition-Combat_004_720p.mp4`

Verified metadata: **1280x720, square pixels, 60 fps, 132.307302 seconds, 55,394,529 bytes**, H.264 video with AAC audio. SHA-256:

`fb01977e41e649bfb9fd53d1ee0e6db436127fb86e4b3b7ec303158e0568aff5`

Use **offset zero for 120 seconds, no looping**. Windows will decode and sample this 60 fps source in real time for a **20 fps** MSV1 JPEG stream; it will not send H.264 to the handheld. Source audio is ignored.

Retain these host settings:

- Windows **192.168.0.47** to receiver **192.168.0.157:5533**.
- **720x480 baseline-JPEG canvas**, Q35, **5 Mbps cap**.
- Scale 16:9 source to **720x405**, positioned at **(0,37)**: **zero left/right padding, 37 black rows above and 38 below**, zero host shift. This is the vertically centered placement the user approved. Preserve game proportions; no stretch or additional crop. JPEG compression may bleed slightly at border rows.
- **20 fps**, `--pacing-wait hybrid --pacing-spin-us 600`; other sender behavior unchanged, including the existing `legacy` clip selection and 200 ms frame-age deadline.
- Input-only AV v1 on **UDP5534** through video, then **STOP**. **Audio and virtual-controller injection off**.
- Reserve **2,400 target IDs 3,018,000-3,020,399 (3,020,400-3,020,879 remain unused/reserved)**, or coordinate a higher unused contiguous range before starting. Skipped/replaced slots may leave gaps in transmitted IDs.

Before START, confirm the current app/ELF and FPGA identities, receiver/source filter, overlap/queue settings, and a fresh trace epoch. Preserve starting received/decoded/presented/dropped, queue drops/high-water, rejected-tail count, core completed/drops/faults/overflows/underruns and initial power-save mode. Counters may be cumulative; use recorded deltas rather than assuming zero.

Verify USB recording and advancing full-panel camera timestamps **before START**, with at least **three minutes of coverage** for startup, 120 seconds of video, STOP and a final display check. Reply READY with the baseline and coverage deadline. Do not reset or reconfigure during the run.

Windows will retain capture/encode/queue/frame/packet logs and outbound Npcap through STOP, and report actual backend/duration/pacing tail, encoded and wire rates, complete/replaced/partial/skipped counts, accepted/rejected/unmatched identities and capture-drop statistics. Clip decoding and scaling are measured separately from verified receiver playback; standalone acquisition/scale durations are not instrumented in the current sender.

After STOP, freeze/export the receiver trace before further transmission. Preserve all failure identities, incoming/active frame IDs, expected/observed offsets, queue/phase timing and trace-loss/table-overflow counts where available. Report final counter deltas, rejected tails, core errors and power-save restoration. Use camera review to check changing combat scenes, placement, flashing and freezes; state coverage and sampling limits. Do not subtract host and ESP clocks.

A two-minute run is an initial reliability check, not a long soak or proof of 20/30 fps playback. Compute presentation rate from the receiver presented delta and measured run duration; host target fps alone is not achieved playback fps. If stable, coordinate a five-minute repeat using the same source/offset and an explicitly agreed loop policy before raising fps or bitrate.

## Windows command after a fresh START

From `C:\ai\sunshine-gamebub`, first recheck the source hash above and reserve a new output directory. The existing launcher defaults to video-only unless other flags are supplied; `--av-input` keeps AV input active without injection.

```powershell
& C:/msys64/msys2_shell.cmd -defterm -here -no-start -ucrt64 -c 'tools/gamebub/.venv/Scripts/python.exe -u tools/gamebub/session_launcher.py --receiver 192.168.0.157 --bind 192.168.0.47 --video --clip "C:/Users/lavat/Downloads/YTDown.com_YouTube_Media__luGrl_3Ajc_Mass-Effect-Legendary-Edition-Combat_004_720p.mp4" --clip-selection legacy --content-origin center --av-input --seconds 120 --fps 20 --quality 35 --mbps 5 --pacing-wait hybrid --pacing-spin-us 600 --start-frame-id 3018000 --capture-interface 4 --output tools/gamebub/artifacts/hardware-mass-effect-centered-2min-v38-20261106-3018000'
```

Interface4 must still resolve to the intended Wi-Fi adapter before the run. Capture uses the existing natural safety tail and exact STOP verification; capture finalization can continue passively after video/AV STOP. No installed Sunshine service restart or receiver flash is part of this test.
