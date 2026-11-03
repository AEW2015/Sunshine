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
Later [16-slot fixture trials](measurements/handheld-16slot-fixture-trials.md)
included two 20-frame runs at 1 Mbps with no receiver-reported drops; the
operator confirmed frame 88 was decoded and displayed. The receiver team has
enabled trace telemetry and supplied FPGA and isolated QSPI timing. In a
subsequent [5 fps live desktop run](measurements/ddagrab-soak-10m.md), the
host sent 92 of 100 target frames and the last feedback reported 82 received
and 10 dropped; an independent starting counter baseline and decode/display
counts were not recorded. Receiver log correlation remains important before
selecting a sustained rate. No new wire format is assumed by the telemetry.
The host's [30 fps JPEG bandwidth study](measurements/30fps-jpeg-budget.md)
quantifies the expected MSV1 rate across quality settings on moving footage.

The receiver's separate [30 fps simulation study](https://github.com/AEW2015/moonbub/tree/8aebc57a3cb5bc7167ec7f602cffa0cfe0ae5e07)
contains experimental burst-memory and packet-recovery work. A later
gameplay-derived model reports 300 presentations over roughly ten simulated
seconds, with 299 distinct source JPEGs and abstract input and queue
assumptions. It does not establish sustained physical playback or a deployed
receiver change. A local sample also
contained JPEGs larger than 32 KiB, so a smaller compressed-frame limit or
dual-bank buffer cannot be assumed without agreement and an oversize policy.
Its later strict 1,800-frame modeled run failed: the last frame missed the
capture window, and 370 frames exceeded 33.33 ms modeled arrival-to-presentation
age, despite all eventually being presented. The proposed two-bank storage
is an isolated experiment and is not the deployed receiver protocol.
The study also clarifies that FPGA register `0x0c` is remaining frame bytes,
not free FIFO capacity. Treat MSF1 free bytes as advisory until a credit contract
is explicitly agreed; the experimental credit register is not production.

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
   Please also evaluate the host's experimental 750 ms feedback timeout, bounded
   in-flight grace (at most three seconds of silence), and one-frame-per-second
   recovery probes against the receiver's 250 ms heartbeat and reconnect
   behavior; these are host policies, not a new wire format.
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
The [Sunshine integration map](SUNSHINE-INTEGRATION.md) identifies the existing
codec-advertisement, RTSP, capture, and packetizer boundaries to protect.

The later [16-slot fixture trials](measurements/handheld-16slot-fixture-trials.md)
include 20-frame runs at 1 Mbps and a consumer-priority comparison. They are
individual-frame ingress tests, not a sustained 30 fps stream.
