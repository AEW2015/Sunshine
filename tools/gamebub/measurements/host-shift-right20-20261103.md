# Host image shifted right by twenty pixels

The operator explicitly selected a host-side shift, accepting a crop of the
rightmost twenty columns. `stream_sender.py --shift-right-px 20` applies this
after scaling/letterboxing and before pipeline submission. It inserts black
columns 0..19, translates source columns 0..699 to destination20..719 and
discards source700..719. The 720x480 canvas, JPEG profile and MSV1 framing stay
unchanged. No receiver or installed-service change was made.

The option defaults to zero to preserve previous runs. This experiment selected
20 explicitly; the operator subsequently removed the shift after the margin10
diagnostic. The current view uses `shift_right_px=0`. Historical artifact
runners are unchanged. The session configuration event
records the selected shift. JPEG compression can introduce normal edge ringing
near the black/content boundary.

## Shifted fixture result

- Receiver reported by operator: left-aligned v20 build48, overlap,32-slot queue.
- Source fixture: tracked `fixtures/frame-00000000.png`, quality75. Re-encoding
  the unshifted PNG reproduced the known-good JPEG hash before shifting.
- Shifted JPEG:69,848 bytes, validated baseline8-bit4:2:0, agreed Huffman tables,
  no restart markers;69 datagrams /72,608 MSV1 bytes.
- Sent as ID28001 from192.168.0.47:55534 to192.168.0.157:5533 at0.7Mbps,
  3000ms deadline and3s feedback wait.
- Complete send; matching MSF1 status0 with the same ID and capture timestamp.
  Cumulative ACK counters:2 received/0 dropped.
- Operator observation: left side looks good;20 pixels looks good; right side
  is trimmed by hardware. That accepts the requested placement, not an
  independent measurement of physical panel trim.

The fixture uses the original PNG rather than decoding/recompressing the
previous JPEG. Both exact pre-encode pixel mapping and source non-mutation are
covered by regressions, including shifts0,20,719 and invalid inputs. CLI/run
tests cover option validation, actual prepared pixels and configuration logging.
The complete suite ran208 tests successfully. Fresh isolated statement/branch
coverage reached100% across all configured modules (2,010 statements and654
branches) after the documented CLI entry checks. Ruff lint/format passed for
all76 files. No long stream was started.

Evidence under `tools/gamebub/artifacts`, prefix
`v20-host-shift-right20-fixture-28001-20261103`: `.png`, `.jpg`, `-context.json`,
`-packets.json`, `-result.json` and `-observation.json`. Test output is in
`shift20-full-tests-20261103.txt`; isolated final coverage output is recorded
separately as `shift20-fresh-coverage-report-20261103.txt`.
