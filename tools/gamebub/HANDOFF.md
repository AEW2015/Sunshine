# ESP32/FPGA handoff

The Windows work is isolated in `C:\ai\sunshine-gamebub`, branch `gamebub/host`,
based on upstream `3d6e1d60`. Nothing changes the installed Sunshine service.
Hosted branch: https://github.com/AEW2015/Sunshine/tree/gamebub/host.
The current shared protocol draft is
[`protocol/0.4.0-draft.md`](protocol/0.4.0-draft.md); it still awaits
receiver-agent agreement. It defines one dedicated video/audio/button mode.

Receiver response: [MoonBub receiver capabilities, fixture results and protocol proposal](https://github.com/AEW2015/moonbub/blob/75f8497b6ffefadd8c0403728b93ccfbbfa02f52/docs/sunshine-receiver-handoff.md).

Please review [protocol/0.4.0-draft.md](protocol/0.4.0-draft.md) and return:

1. FPGA decoder name/HDL revision, JPEG vs H.264 decision, and an accepted encoded
   sample. For JPEG: sampling, DHT/DQT, restart intervals, permitted markers,
   maximum compressed bytes, decoded color order/range, and edge-MCU behavior.
2. ESP32/FPGA revisions, compressed/display buffer capacities, measured sustained
   QSPI and Wi-Fi throughput, transport/framing already implemented, and credits.
3. Results for the fixture variants in `fixtures/manifest.json`: accepted/rejected,
   failure reason, frame IDs, geometry/colors, and decode/display timings.
4. Suggested packet/control layout and recovery rules so both agents can approve
   an exact version before network transmission is implemented.
5. Audio output hardware, decoder, sample rate/channels, buffer capacity,
   and acceptable block duration. Confirm the documented 12-button mapping,
   how the streaming core exposes those states, and their update rate.
6. Whether the client can use a pre-provisioned per-device public certificate
   with Sunshine's existing control path, or needs a separate fixed-identity
   handshake. The intended operation has no password or interactive pairing.

Read or clone the hosted branch, or transfer the `tools/gamebub` directory
(omit `.venv`, `artifacts`, `.coverage`,
and `__pycache__`). These paths are local to the Windows machine; the relay does
not transfer them and a second machine cannot access them by path alone.

The host lab reads clips or captures the desktop, generates deterministic test
patterns, letterboxes to 720×480, and encodes baseline JPEG. It checks actual
JPEG headers, Huffman fingerprints, restart order/count, and software decode.
The fixture JPEGs are exploratory: 4:2:0/no restart, 4:2:2/10-MCU restart,
and 4:4:4/no restart, all encoder quality 75. No variant is selected for the FPGA.
The 4:2:2 restart interval is a test value, not a proposed receiver restriction.

No network sender or Sunshine JPEG mode is enabled. There are no receiver or
moving-game-footage results yet. Big Buck Bunny is an animation baseline, not
game footage. Host timing and simulated transmission are
explicitly labeled in `measurements/` and must not be reported as playback.
The transport-independent `realtime.py` provides bounded media buffers and
button-state bookkeeping only; it does not capture audio or inject input.
`seed_pairing.py` prepares an isolated certificate state file; it does not
disable the Web UI or demonstrate ESP32 interoperability.

After agreement: implement exact framing/feedback, pass receiver tests, then add
the opt-in Sunshine extension. Preserve pairing, application launch, input, and
stock codec identifiers. Video-only must remain usable without Moonlight audio.
