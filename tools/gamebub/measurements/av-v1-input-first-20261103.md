# Physical AV v1 input-only sessions

The Windows golden-vector check passed immediately before testing: all seven
packet vectors and the exact2020-byte product-rounded PCM oracle matched.
The receiver was192.168.0.157:5534, with Windows source192.168.0.47 explicitly
bound. No audio source, audio packets, virtual controller or gamepad injection
was enabled. Existing video sender and installed Sunshine service were untouched.

The exact published reference `av_client.py` and `av_protocol.py` were extracted
from MoonBub `aab1ba337550ba472c30ee417fcf6d439b5a7f1e` into isolated ignored
artifact directories. Their SHA-256 values remained unchanged. A wrapper records
successful socket sends and received datagrams and delegates to the unchanged
reference CLI with an explicit receiver, source bind and20-second duration,
and an exclusive `input-first.jsonl` log. The exact reference command is shown
below. Every captured datagram was then
validated by the independent Windows AV packet parser, including whole CRC.

## Repeat: A and all four D-pad directions observed

| Measurement | Result |
| --- | --- |
| America/Denver process window | 2026-11-03 18:27:08.943–18:27:29.004 MST |
| UTC process window | 2026-11-04 01:27:08.943–01:27:29.004 |
| Requested active duration | 20 seconds |
| Source / receiver | 192.168.0.47:62268 /192.168.0.157:5534 |
| HELLO / OFFER / START | 1 /1 /1 |
| Nonce / cookie | `b95c5a3d46f07736` /`f0ff0cbc894918c5` |
| Host HELLO-send to initial ACTIVE-MSI receipt | 31ms, host monotonic clock |
| All nonce echoes, input-only flags and peer endpoints | Valid |
| MSI1 packets, including handshake confirmation | 954 |
| MSI1 sequence range / gaps / duplicate or stale | 0..953 /0 /0 |
| Reference client loop input count | 953, excluding the first handshake MSI1 |
| Invalid datagrams / input timeouts | 0 /0 |
| KEEPALIVE count / sequences | 182 /2..183 |
| STOP sent / sequence | 1 /184 |
| Final button mask | `0x000`, neutral |
| Audio packets / virtual input injection | 0 /disabled |
| Process result | Exit0; stderr empty |

| Observed complete button mask | Meaning | MSI1 packets |
| --- | --- | ---: |
| `0x800` | A | 75 |
| `0x080` | Up | 70 |
| `0x040` | Down | 12 |
| `0x020` | Left | 22 |
| `0x010` | Right | 62 |
| `0x000` | Neutral | 713 |

The masks above are complete12-bit Game Bub states, not Xbox report flags.
Press/release transitions are retained with MSI1 sequence and host receipt
timestamps in `analysis.json`. All954 snapshots matched the negotiated cookie,
and every received sequence advanced exactly one. The final snapshot had state5
(ACTIVE and FPGA_SNAPSHOT_VALID, with AUDIO_ENABLED clear), build ID
`0x4d424f50` and zero audio counters. This is input/status transport evidence,
not a physical decoder/audio/core qualification.

The run passed the input-only transport/button milestone for A and all four
directions. It does not demonstrate Windows controller recognition, input
injection, game response or physical button-to-game latency. No STOP ACK exists
in this contract; the log establishes a successful host STOP send, not a
receiver-side stop/flush observation. Receiver confirmation can strengthen that
shutdown evidence. Host-monotonic handshake timing is not physical button
latency or a synchronized receiver measurement.

## First attempt, retained separately

The first20-second active session ran18:24:54.621–18:25:14.958 MST
(2026-11-04T01:24:54.621–01:25:14.958Z), from192.168.0.47:60902.
HELLO/OFFER/START each appeared3 times, with matching nonce
`e2ca5c8b2ff760c5` and cookie`2b8aaf997fededf5`. Initial ACTIVE arrived312ms
after the first host HELLO. It received955 contiguous MSI1 packets, sequence0..954;
the reference loop count954 excludes the initial handshake snapshot. There were
no invalid/stale packets or timeouts,182 keepalives and STOP184, and exit0.

Only A/B/X/Y and neutral masks appeared in that first window. D-pad validation
was therefore incomplete. The operator said the requested presses were probably
after the window and requested a repeat. The second session above captured the
requested masks; no receiver mapping defect was inferred from the first run.

## Logs and reproduction

Artifact directories under `tools/gamebub/artifacts`:

- `av-v1-input-first-aab1ba3-20261103/`
- `av-v1-input-repeat-aab1ba3-20261103/`

Each retains the pinned reference source and hashes, `input-first.jsonl`, full
raw `packets.jsonl`, `stdout.jsonl`, `stderr.txt`, `run-metadata.json`, PID record
and `analysis.json`. The preflight golden result is
`artifacts/av-v1-before-input-first-golden-20261103.json`. Previously saved
failure and codec-conformance evidence remains unchanged.

From the extracted reference directory, using the lab Python interpreter:

```powershell
python av_client.py --receiver 192.168.0.157 --bind 192.168.0.47 --seconds 20 --log input-first.jsonl
```

Choose a fresh directory/log; the reference client refuses overwrites. Windows
test execution uses the repository's MSYS2/UCRT64 command prefix. Announce ACTIVE
and have the operator press/release buttons during the active20-second window.
No new stream or session was started after the repeat.
