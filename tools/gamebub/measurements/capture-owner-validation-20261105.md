# Capture-owner localhost validation

Two localhost checks validated capture startup, finalization and exact STOP
matching. Neither involved a hardware receiver, RF transmission or performance
measurement.

## CaptureOwner smoke

The short smoke used Npcap `\Device\NPF_Loopback` with BPF filter
`udp and host 127.0.0.1 and port 59189`. Dumpcap reported ready and created the
pcapng before AV started; readiness took 0.113 seconds. A 0.4-second input-only
AV session received 12 valid input packets, with zero invalid, stale or timed
out packets. STOP sequence 5 was sent and independently received by the
localhost peer.

Dumpcap reached its natural 8-second autostop with exit code 0, after 7.594
seconds of post-STOP capture. It reported 21 packets captured, 21 received and
zero drops. `capture_evidence.verify_stop` matched the exact STOP wire bytes
once, at pcapng frame 20. The retained summary, stderr and ignored raw capture
are under
[`artifacts/capture-owner-localhost-smoke-20261105`](../artifacts/capture-owner-localhost-smoke-20261105/summary.json).

## Production launcher localhost run

The launcher check used the localhost video reference and AV input peer with
the explicit loopback filter. The reference peer completed 20 of 20 video
frames; AV received 54 valid MSI1 snapshots, with no invalid/stale input,
timeouts or cleanup errors. The capture reported 446 packets received and
zero drops, with dumpcap exit code 0 and no forced stop. The exact STOP was
verified once at frame 446. Capture continued 119.438 seconds after STOP until
the configured 121-second safety autostop elapsed.

The run summary is
[`result.json`](../artifacts/overnight-launcher-localhost-20261105/result.json).
Both loopback peers report that no hardware was contacted. The pcapng and
native stderr remain ignored artifacts in that same run directory.

## Lifecycle and verification scope

These runs show that capture was active before media, remained active through
the sent STOP, and closed naturally with native packet/drop statistics. The
launcher run additionally verified the exact STOP datagram in the finalized
savefile. This is capture-point evidence only: it does not establish RF
delivery, receiver acknowledgement, decode or display.

CaptureOwner regression coverage used a separate ignored coverage file. All
26 deterministic tests passed; `capture_owner.py` measured 190/190 statements
and 48/48 branches (100% for both). Ruff passed. The coverage data is
`tools/gamebub/artifacts/.coverage-capture-owner-20261105`.

The no-console capture path uses natural finite autostop rather than a
graceful console control event. The launcher currently budgets 120 seconds
after the media duration, so a successful capture can remain open for nearly
two minutes after STOP. Raw pcaps are ignored artifacts; the JSON summaries
and stderr preserve the measured metadata without adding binary captures to
version control.
