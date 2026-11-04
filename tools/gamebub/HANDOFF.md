# ESP32/FPGA handoff

Latest Windows offline transport/profiling work is described in
[the implementation report](measurements/v20-transport-and-generated-profile-20261104.md).
Native wire replay and a sender-only intent/reply helper are available;
full packet-permit/drain/recovery ownership and a live custom endpoint remain
open. Frame-local encoder analysis reuse is checked against the frozen golden
cases without changing maps, packet bytes or independent candidate validation.
Generated-motion software timings must not be reported as physical playback.

Windows native body/policy update2026-11-04: all 20 frozen full-body AR03 cases
match10368000 YUV samples,6912000 display words,211200 mandatory source HUD
words, exact AF03 and post-bank state. Native candidate policy now enforces
all-patch reservation, four maps, immutable source leases, bounded readers,
commit/discard and exact reference ACKs. Actual native RGB8-to-YUV420, Q14
forward transform, quantization and CP02 raw/Rice coding now produce GM01;
actual HP01/HR01 coding produces exact RGB565 HUD patches. All 20 frozen cases
match inner, selected patch and full AR03 bytes. The 10 mandatory cases verify 13
actual policy attempts, including losing builds; the 10 baseline partial-HUD
cases do not establish mandatory coverage. SR01 decoding exists, but SR01
encoding does not. No persistent analysis or patch cache is implemented.
The final encoder fixtures are `artifacts/v20-encoder-cases-20261104`; export
and verification commands are in [the development guide](V20-DEVELOPMENT.md).
These are offline software checks and profiling, with no new physical FPS,
latency or audio result. There is no live custom endpoint. See
[body/policy validation](measurements/v20-native-body-candidate-20261104.md) and
[native encoder validation](measurements/v20-native-encoder-20261104.md).
Earlier inverse/envelope evidence remains preserved. The JPEG/AV launcher adds callback capture,
inactivity reporting and finite cleanup; it has localhost validation but no
physical callback test. See [validation](measurements/v20-offline-foundations-20261104.md),
[setup](V20-DEVELOPMENT.md) and [launcher](SESSION-LAUNCHER.md). No hardware
stream, flash, driver install or installed-service restart occurred for this work.

The Windows work is isolated in `C:\ai\sunshine-gamebub`, branch `gamebub/host`,
based on upstream `3d6e1d60`. Nothing changes the installed Sunshine service.
Hosted branch: https://github.com/AEW2015/Sunshine/tree/gamebub/host.
The video-only test protocol remains
[`protocol/0.5.0-draft.md`](protocol/0.5.0-draft.md). The newly published separate
AV v1 contract is recorded in [`protocol/0.7.0-av-v1.md`](protocol/0.7.0-av-v1.md).
AV packet bytes and decoded PCM now align; physical acceptance remains open.
Neither path is a production Sunshine/Moonlight codec negotiation.

Current candidate work is isolated on `gamebub/windows-jpeg-retry-20261103`.
The [five-minute combined12fps/audio/Elden Ring test](measurements/combined-elden-12fps-5m-50000-gain075-20261103.md)
ran IDs50000..53599 at720x480,q25,2Mbps video, zero shift, plus audio gain0.75
and the working controller profile in one AV cookie. Video:3,250 complete
(10.807 host sends/s),91 partial,46 zero-byte,84 skipped,129 replaced; ACKs
3,241 accepted,8 rejected,1 pending. Audio:28,262 sent,65 host queue drops,
25,992 accepted and2,254 rejected/unconfirmed in the last MSI1. Last state3
invalidates its zero FPGA counters; last-valid underruns rose1,767 (45→1,812).
No MSI1 gap/invalid/stale/input timeout; controller remained live. This is not
a stable12fps/audio or continuity pass; independent receiver reasons/stages and
optical/acoustic results are pending. Controller-only Elden Ring was restored:
192.168.0.47:57614, cookie`cd0be9feb028b3a2`, up to2h, audio/video off.

The [Elden Ring profile](measurements/elden-ring-controller-profile-20261103.md)
is active and operator-confirmed: D-pad→left stick, A→RB/light attack,
B→left-stick click/crouch, X→LT/working guard, Y→Xbox A/jump. X was changed from
LB to LT at the operator's request and verified via Windows XInput trigger255/0.
The standard profile is preserved. Current session:192.168.0.47:64052,
cookie`e26a2752fc7969db`, log`controller-20261104T023909340706Z.jsonl`, input-only,
up to2h. Prior controller sessions were stopped only for remapping; Sunshine
remained PID7420. Full discovery254 tests,5 skips; changed-module coverage100%.

The [Windows Xbox controller path](measurements/windows-gamepad-first-20261103.md)
is now physically verified for all12 digital controls and releases through
independent XInput reads. ViGEmBus installed with operator administrator consent;
neutral attach/remove passed and Sunshine stayed at PID7420. The 60-second test
had2,862 loop MSI1 records and no invalid/stale/timeouts; target removal passed.
A regular standard-profile input-only session was started and later replaced
by the Elden Ring profile above. The operator confirmed game recognition and
response. Standard-profile sticks/triggers are neutral; audio/video are off.
Do not start a competing AV audio session.
See [quickstart](CONTROLLER-QUICKSTART.md). Full discovery:251 tests,5 skips.

The [one-minute gain0.75 PC audio repeat](measurements/av-v1-loopback-60s-gain075-qpc-20261103.md)
completed from192.168.0.47:56641, cookie`50f7753168335cc7`, with video and gamepad
injection off. Accounting:5,589 encoded =5,571 sent +15 queue drops +3 unsent;
stale drops/capture errors0. Last MSI1:5,540 accepted,11 rejected/unconfirmed,
656 queued; played +2,794,522 and underruns +15 (30→45). Post-STOP receiver totals
are5,542 accepted,11 rejected/unconfirmed,0 queued,6,036,993 lifetime played
(+2,797,568),33 sequence gaps and45 lifetime underruns (+15). Eighteen sends
remain unexplained. Microphone capture succeeded without mic clipping; comfort,
speaker distortion and individual clicks remain unconfirmed. STOP completed,
power saving restored, core/socket/malformed errors0 per receiver report.
One host-observed MSI1 sequence gap, no invalid/stale packets or timeouts.
STOP572 sent; exit0. Earlier gain0.25 evidence and defaults were preserved.

The [one-minute PC speaker-loopback test](measurements/av-v1-loopback-60s-product-qpc-20261103.md)
completed from192.168.0.47:61347 to192.168.0.157:5534, gain0.25, with video and
gamepad injection off. Exact worker accounting:5,557 encoded =5,530 sent +24
queue drops +3 queued unsent at close; stale drops/capture errors0. Last MSI1
reported5,476 accepted,4 rejected/unconfirmed and2,040 queued frames. Digital
played count advanced2,763,344 in MSI1 and underruns increased17 (13→30). The
operator later confirmed audible PC audio and post-STOP totals5,477 accepted,
4 rejected/unconfirmed,0 queued,3,239,425 lifetime played (+2,763,704). Final
admission counts leave49 of5,530 sends unreconciled; causes remain unknown.
Acoustic continuity/distortion were not characterized. The recorder is being
fixed before a requested repeat; no new session was started. All2,826 MSI1 sequences0..2825 were
contiguous; no invalid/stale/timeouts. This run uses QPC timing and saves full
source/packet/worker evidence. STOP570 sent; exit0. No clean-continuity claim.

The [first ten-second quiet stereo tone](measurements/av-v1-tone-first-product-20261103.md)
ran from192.168.0.47:59499 to192.168.0.157:5534, gain0.25,440/660Hz, product-rounded
encoder, with video and gamepad injection off. Sent944 audio blocks; final MSI1
reported942 accepted,0 rejected/unconfirmed,1,142 queued frames,474,067 lifetime
played frames and 13 underruns. Host queue drops9, stale audio0;473 contiguous
MSI1 packets and no invalid/stale/input-timeout events. STOP93 sent; exit0.
The operator later confirmed all944 sends were accepted and the tone was heard.
The9 missing sequence IDs were sender omissions matching9 host queue drops;
stale drops0. At least953 blocks were encoded through sequence952, but the exact
final encoded total/unsent queue tail was not logged. Eight observed send gaps
were32ms on the15.625ms-resolution host clock; full timestamps are saved.
Digital playback was reported, with13 underruns; this is not a
clean-continuity pass. Raw packets and encoder/transport source hashes are saved.

The [physical AV input-only repeat](measurements/av-v1-input-first-20261103.md)
passed20 seconds from192.168.0.47:62268 to192.168.0.157:5534 using the unchanged
published reference client at`aab1ba3`. One HELLO/OFFER/START established cookie
`f0ff0cbc894918c5`;954 MSI1 snapshots had contiguous sequences0..953 and included
A, Up, Down, Left, Right and neutral releases. Zero invalid/stale packets or
input timeouts;182 keepalives and STOP184 sent. Audio and virtual-gamepad
injection were disabled. This confirms physical input/status transport, not
Windows gamepad injection or audio playback. Full raw packet/frame logs and
the earlier face-button-only attempt are retained separately.

The [published AV v1 check](measurements/av-v1-conformance-20261103.md) now pins
MoonBub `dff54528`: all7 datagrams match the48-byte-header/whole-CRC contract.
New packet/session adapters test nonce/cookie handshake, independent sequences
and500ms MSI1 release. Clarification `aab1ba3` requires product-based IMA rounding;
Windows now uses it in both encoder feedback and decoder, resolving the PCM
oracle discrepancy. All7 packets and exact2020-byte PCM hash pass; see
[protocol0.7.0](protocol/0.7.0-av-v1.md). All23 focused tests pass with100% coverage;
full discovery passes245 tests with5 existing integration skips. The acceptance
verifier now returns zero with wire/PCM conformance true. The Windows adapters
still have no integrated AV socket runner; the physical input test above used
the isolated published reference client. Audible quiet-tone playback is now
operator-confirmed as recorded above; controller injection remains unverified.

The [Windows audio/controller setup](AUDIO-CONTROLLER-SETUP.md) now provides local
WASAPI stereo capture, proposed48,293Hz/512-byte stereo IMA ADPCM preparation,
deterministic audio fixtures and a sequenced-input adapter/virtual Xbox backend.
The real five-second capture and478 independently decoded audio blocks passed.
All22 new regressions pass with100% new-module statement/branch coverage;
full lab discovery at that stage passed230 tests with5 existing integration skips.
AV v1 wire headers are now published, as recorded above; the last reported installed
receiver has neither audio playback nor independently sequenced input. The real
controller probe reports missing ViGEmBus (`0xe0000001`); no driver was installed
and MSF1 buttons are still logging-only. See the
[historical proposal](protocol/0.6.0-av-input-proposal.md) for its earlier scope;
the current contract and remaining gates are in0.7.0 above.

The [margin13 20-minute 12fps desktop run](measurements/margin13-desktop-12fps-20m-31600-shift0-20261103.md)
finished IDs31600..45999:14,055 complete,94 partial,4 zero-byte sends,
247 encoded replacements and zero skipped slots; matched ACKs13,837 accepted,
197 rejected,21 pending. Final ingress feedback15,437 received/293 dropped.
Independent final decoded/presented19,147 each confirm +13,837 at both stages.
Receiver reports505 queue packet drops,peak32/32,126 Busy and71 Sequence failures;
96 frame-drop reasons remain unknown. Core faults/overflow/underruns/transport
overflow were zero; the separate core drop counter was154. Camera sampling
showed changing scenes but cannot rule out brief freezes. Correlate remote IDs
with saved packet records before attributing individual losses or raising rate.
The [app-codec v11 review](measurements/app-codec-v11-review-20261103.md)
found research formats and an8Mbps software model, not a new live Sunshine
mode compatible with the current JPEG receiver. Twenty lightweight model/audit
tests passed; codec benchmarks and hardware integration were not rerun.

The current requested host view is **zero host shift**. The operator removed
the experimental20-pixel right shift after the margin10 diagnostic. Use
`--shift-right-px 0` or `shift_right_px=0` for future desktop tests (also the
sender default). This restores all720 source columns without the added left
strip or host-side right crop. MoonBub's receiver margin/viewport is separate.
Historical fixture28001 and stream30000..30099 used20 and their artifacts
remain intact for reproduction; do not inherit that value into new runners.

The latest [five-minute margin10/original-timing run with shift0](measurements/margin10-desktop-5fps-5m-30100-shift0-20261103.md)
sent IDs30100..31599 at5fps,720x480,q25/2Mbps: all1,500 complete sends received
matching accepted feedback, with zero skipped/partial/suppressed frames, zero
pending feedback and zero logger loss. Final feedback was1,600 received/0
dropped. Independent counters confirm +1,500 decoded/presented (final5,310 each),
zero frame/queue drops, peak24/32 and empty queue; all reported core faults,
core drops, overflows and underruns were zero. Margin10/timing0 stayed applied.
The supplied receiver-side post-run camera report describes no flashing and
stable placement; this host did not optically monitor the full run. This is the
current clean five-minute5fps baseline. No host crop or horizontal shift applied.

The latest [five-minute desktop stream after the receiver margin change](measurements/desktop-10fps-5m-21000-20261103.md)
used IDs21000..23999 with unchanged host geometry, quality25/2Mbps/200ms at10fps:
2,618 complete, 338 partial, six zero-byte sends and 38 skipped slots. Matched
feedback was2,605 accepted/13 rejected, with one pending. One rejection belongs
to a partial frame22844; full-send22849 lacks matched feedback. Final cumulative
feedback was2,605 received/350 dropped, independently confirmed decoded/presented
at2,605 each. Queue saturation is recorded:36 packet drops,32/32 high-water,
first at22842 offset3072; reported core faults/overflow/underruns remain zero.
Receiver outcomes total2,955 versus2,956 host nonzero sends; one outcome and
frame22849's disposition remain unexplained. Do not add packet and frame drop
counts as independent losses. Panel-placement confirmation remains pending.
No host margin or firmware change was made; the margin change was on MoonBub.

The latest [20-minute live desktop run including Elden Ring](measurements/elden-ring-live-desktop-10fps-20m-9000-20261103.md)
targeted 10 fps at quality25/2Mbps with unchanged source port55534 and 200 ms
deadline. IDs9000..20999: 11,943 complete, 20 partial, two zero-byte sends,
35 skipped slots; 11,893 accepted / 50 rejected responses, zero pending or
logger loss. Independent receiver counters confirm +11,893 received, decoded
and presented from baseline 2,019, with 70 new drops from baseline30.
Fifty distinct receiver Busy rejections agree with the 50 host rejections;
9724/20793 explicitly report `FPGA overlap start: Policy(Busy)` at offset0,
expected None, status0x02 decode/drain. The other20 drops numerically match
host partials, but individual reasons remain unknown. Queue drops and all
reported faults/overflows/underruns were zero; session high-water was29/32,
final occupancy0. Keep host deadline/pacing and bounded admission-wait testing
separate; Busy is now demonstrated in this live run. The operator
confirmed updating images with some drops during heavy motion. Desktop app
switches are included; this is not twenty continuous minutes of game-only
footage. A reported right shift remains unresolved: host snapshot and reported
RTL mapping are centered, but physical panel-origin/edge checks are pending.

The subsequent [20-second 10 fps exploration](measurements/handheld-v19-overlap-10fps-20s-8218-20261103.md)
used IDs 8218..8417 with the same quality25, 2 Mbps cap and 200 ms deadline:
161 complete sends, 28 partial and 11 zero-byte deadline refusals; zero skipped
slots or feedback suppression. Independent receiver counters confirm all 161
accepted frames were decoded/presented, with 28 new drops, zero queue packet
drops/errors/faults/overflows/underruns and no Busy diagnostics. Exact receiver
reasons were not retained. Frame 8240 ended at a host packet-deadline guard
after 23,552 payload bytes; next actual SOF 8242 followed 21.4424 ms later.
Investigate host pacing, queue age and deadline handling; keep admission-wait
firmware separate while Busy remains undemonstrated in this run.

The [offline partial-frame timing comparison](measurements/10fps-partial-frame-timing-comparison-20261103.md)
finds median encoded queue wait 82.804 ms for partial frames versus 0.237 ms
for complete frames; encode medians remain about 2.2 ms. Host full-packet gaps
were median 4.984 ms versus the configured 4.256 ms interval. A separate
500-sleep probe reproduced a 4.983 ms median without a socket. Source preparation
was separately profiled offline; original acquisition times remain unlogged.
Receiver frame 8340's 20 packets / 20,480 QSPI-forwarded bytes match host
partial counts, but no explicit receiver reason or next-SOF identity survives.
Keep quality/bitrate/receiver unchanged while measuring wait overhead and exact
host deadline decisions; no admission-wait change is justified by this run.

The latest [v19 overlap five-minute comparison](measurements/handheld-v19-overlap-5fps-5m-6718-20261103.md)
sent IDs 6718..8217 at 5 fps, fixed quality 25 and a 2 Mbps cap: all 1,500
were completely sent and received matching accepted ACKs, with zero skipped,
suppressed, incomplete or rejected frames and zero lost log records. Final
feedback was 1,599 received / 1 dropped against the 99 / 1 baseline.
Independent counters confirm all 1,500 decoded and presented, zero new frame
or queue packet drops, high-water 25/32 and final queue occupancy zero. Overlap
remained active; the core ended 0x01 idle/ready with zero faults, FIFO/transport
overflows or scanout underruns. A camera check showed the game image near the
end; continuous motion was not optically monitored. The five-minute 5 fps
milestone passes on receiver counters. Next use a short, separately requested
10 fps exploration with the same receiver application/queue before changing
admission firmware. Do not infer physical 30 fps or isolate overlap from the
FPGA revision change.

It adds an optional local JPEG capacity guard and one deadline-aware quality
retry, without changing the wire format. See the
[Windows development plan](WINDOWS-DEVELOPMENT-PLAN.md) and
[capacity/retry validation report](measurements/jpeg-capacity-retry-validation-20261103.md).
The candidate passed 200 lab tests and a ten-minute prerecorded-game localhost
soak at 29.982 complete ingress fps. A separate physical 5 fps comparison sent
IDs 3617..5116: 1,500 complete sends, 1,485 accepted feedback, 15 rejected,
zero skipped/suppressed and no pending feedback. Final feedback was 4,294
received / 297 dropped, versus the operator's 2,809 / 282 baseline. The operator
subsequently confirmed 4,294 decoded and presented (+1,485 each), zero
application-queue packet drops and a queue high-water of 26/32. All 1,500
outcomes are accounted for. Application-queue overflow is not supported as
the cause of these 15 losses; per-frame failure reasons and first missing
offsets remain needed. Keep the physical rate at 5 fps while correlating rejected IDs and packet timestamps
with the receiver trace; neither run establishes physical 30 fps playback.

A [continuously recorded repeat](measurements/handheld-recorder-repeat-20261103.md)
sent IDs 5117..6616 with identical source/settings: 1,500 complete sends,
1,488 accepted / 12 rejected feedback, zero skips/suppression and no lost log
records. All 29,446 packet timestamps were exported. The receiver captured
frame 5361 rejecting offset 0 with `Decoder unavailable: Busy`; status
`0x00000002` showed decoding active and READY clear. Its admission began
3.512 ms after previous commit confirmation on the receiver clock. This
identifies a Busy admission failure. Final recorded traces classify all twelve
rejections as offset-0 `Decoder unavailable: Busy`: eleven during decoding and
one pending presentation. Independent counters confirm +1,488 decoded/presented,
zero application-queue packet drops, high-water 26/32 and last completion 6616.
Evaluate bounded READY admission with frame-age/queue limits before changing
the rate or Wi-Fi pacing. Active decoder frame ID and completion/READY timing
remain needed; any host readiness-credit semantics must be explicitly agreed.

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

The receiver's separate [30 fps simulation study](https://github.com/AEW2015/moonbub/tree/28bcd7d23b22e91dec454efe1a4dc2d638f49d0a)
contains experimental burst-memory and packet-recovery work. A later
gameplay-derived model reports 300 presentations over roughly ten simulated
seconds, with 299 distinct source JPEGs and abstract input and queue
assumptions. It does not establish sustained physical playback or a deployed
receiver change. A local sample also
contained JPEGs larger than 32 KiB, so a smaller compressed-frame limit or
dual-bank buffer cannot be assumed without agreement and an oversize policy.
The study also reports a separate strict ten-second model with 300 distinct
precompressed game-derived JPEGs sampled at 29 Hz and replayed at 30 Hz;
complete inputs were assumed available, with no ESP32 or network timing.
Its later strict 1,800-frame modeled run failed: the last frame missed the
capture window, and 370 frames exceeded 33.33 ms modeled arrival-to-presentation
age, despite all eventually being presented. The proposed two-bank storage
is an isolated experiment and is not the deployed receiver protocol.
Its later hypothetical 60 Hz panel-clock simulations require a new clock
configuration and do not establish routed timing or physical panel support.
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

Recent host-only results include a [30-minute-per-cap sweep](measurements/xonotic-rate-sweep-30m.md),
a [one-hour moving-game soak](measurements/xonotic-latest-soak-1h.md), and a
[synthetic missing-chunk recovery run](measurements/xonotic-fault-soak-10m.md).
The one-hour reference run reassembled 107,482 frames at 29.85 fps; it does not
establish physical Wi-Fi, FPGA decode or display performance. For the next
coordinated hardware run, use optional `--packet-timing` and correlate frame IDs
with receiver ingress, QSPI, decode and presentation logs. The frame-size limit,
bank ownership, audio and presentation-feedback contracts remain to be agreed.
