# ESP32/FPGA handoff

The Windows work is isolated in `C:\ai\sunshine-gamebub`, branch `gamebub/host`,
based on upstream `3d6e1d60`. Nothing changes the installed Sunshine service.
Hosted branch: https://github.com/AEW2015/Sunshine/tree/gamebub/host.
The current shared protocol draft is
[`protocol/0.5.0-draft.md`](protocol/0.5.0-draft.md); it still awaits
receiver-agent agreement. It documents the current video-only test protocol;
audio and a production button/session protocol remain to be agreed.

Physical bring-up has started: see [handheld fixture results](measurements/handheld-fixture-bringup.md)
for confirmed decode/display at low rates and sequence errors at higher rates.
The operator also confirmed visible updates in a [short live game-video diagnostic](measurements/handheld-live-game-test-01.md)
at a 1 fps target and 0.5 Mbps cap; audio and input were not tested.
Most recently, cumulative handheld counters were 7 received/7 decoded/7
displayed/4 dropped; a 0.5 Mbps fixture displayed and a 0.7 Mbps fixture was
dropped. The first failing expected/observed offsets are unavailable because
serial logging was not captured. Please instrument the first sequence error
per frame with frame ID and expected/observed offsets, and correlate socket
drops, QSPI timing/credits and decode/display counters before selecting a rate.
The receiver agent reports a separate earlier 1 Mbps gap (expected 7168,
observed 8192), but no failure in its two later capture windows. Its installed
firmware does not yet capture per-transfer QSPI duration, receive-queue drops,
or decode-to-display timestamps. A bounded per-frame trace matched to the host
packet log is the next agreed diagnostic; no new wire format is assumed.
The host's [30 fps JPEG bandwidth study](measurements/30fps-jpeg-budget.md)
quantifies the expected MSV1 rate across quality settings on moving footage.

Receiver response: [MoonBub receiver capabilities, fixture results and protocol proposal](https://github.com/AEW2015/moonbub/blob/75f8497b6ffefadd8c0403728b93ccfbbfa02f52/docs/sunshine-receiver-handoff.md).

The response confirms the experimental 4:2:0 JPEG profile, MSV1/MSF1 test framing, button
bits, current buffer limits, and successful frame-0 RTL checks. This host now
passes the receiver's pinned packet fixture and Rust parser tests. Please review
[protocol/0.5.0-draft.md](protocol/0.5.0-draft.md) and coordinate the next work:

1. Confirm the actual board revision and memory population. When the receiver
   is ready, provide its test LAN address and run the single-frame MSV1 test;
   capture ingress, decode, and displayed-frame evidence separately.
2. Measure concurrent Wi-Fi/QSPI throughput, display rate, frame age, drops,
   and input response using detailed moving gameplay.
   Please also evaluate the host's experimental 750 ms feedback timeout and
   one-frame-per-second recovery probes against the receiver's 250 ms heartbeat
   and reconnect behavior; these are host policies, not a new wire format.
   The pinned firmware locks its peer to the first UDP source IP and port for
   the session. Please confirm intended peer reset/rebind rules and frame-ID
   handling on host restart. The host now has `--source-port` and
   `--start-frame-id` for coordinated test restarts.
3. Agree and implement the audio codec, rate/channels, block duration, clock,
   buffering and recovery. The current streaming FPGA has no audio path.
4. Agree a versioned, authenticated session and fixed-device provisioning for
   passwordless operation; the current test receiver has no TLS or pairing.
5. Confirm the streaming core's access to the documented button states and its
   mapping. Enable host gamepad injection only after the session and failure
   behavior are agreed and verified. MSF1 can send multiple input changes with
   the same video frame ID but has no input sequence; please propose an ordered
   input snapshot counter and session/reconnect rules, including heartbeat,
   timeout, neutralization, and authentication. The host currently logs mapped
   snapshots only and does not inject Windows input.

Read or clone the hosted branch, or transfer the `tools/gamebub` directory
(omit `.venv`, `artifacts`, `.coverage`,
and `__pycache__`). These paths are local to the Windows machine; the relay does
not transfer them and a second machine cannot access them by path alone.

The host lab reads clips or captures the desktop, generates deterministic test
patterns, letterboxes to 720×480, and encodes baseline JPEG. It checks actual
JPEG headers, Huffman fingerprints, restart order/count, and software decode.
The original fixture JPEGs are 4:2:0/no restart, 4:2:2/10-MCU restart,
and 4:4:4/no restart, all encoder quality 75. The receiver team reports that
frame 0 of 4:2:0 and 4:4:4 passed its RTL test; 4:2:2/restart is unsupported.
`msv1.py` currently accepts the conservative 4:2:0/no-restart subset only.

The single-frame `msv1.py` and continuous `stream_sender.py` test senders implement
the receiver prototype's unauthenticated video-only transport. The continuous
sender passed localhost reassembly with the pinned receiver Python reference;
please run it against the actual hardware when ready and report ingress, FPGA
decode, and display results separately. No Sunshine JPEG mode is enabled. The
physical observations so far include fixture frames and a short, low-rate live
game-video diagnostic, not sustained gameplay. The host also has a moving-game localhost run
using [Xonotic footage](measurements/xonotic-loopback.md); Big Buck Bunny is a
separate animation baseline. Host timing and simulated transmission are
explicitly labeled in `measurements/` and must not be reported as playback.
A [ten-minute localhost soak](measurements/xonotic-soak-10m.md) and packet-loss,
reordering, delayed-feedback and restart tests are also available.
The transport-independent `realtime.py` provides bounded media buffers and
button-state bookkeeping only; it does not capture audio or inject input.
`seed_pairing.py` prepares an isolated Sunshine certificate state file; the
current MSV1 receiver does not implement the control protocol needed to use it.

After agreement: complete authenticated framing/feedback, pass receiver tests, then add
the opt-in Sunshine extension. Preserve pairing, application launch, input, and
stock codec identifiers. Video-only must remain usable without Moonlight audio.
