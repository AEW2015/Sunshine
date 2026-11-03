# Ten-minute synthetic missing-chunk recovery check

The standalone sender at sender-code commit `9403e54b` replayed the pinned
[Xonotic source](xonotic-source.json) to the pinned MoonBub Python reference on
localhost. A test-only receiver wrapper discarded the MSV1 datagram at JPEG
offset 1,024 for every frame ID divisible by 50. This is deterministic
synthetic loss, not a model or measurement of the physical Wi-Fi link. The
reference peer's feedback drop field is its invalid-datagram counter; the
host interprets those counter increases as congestion, which drove adaptive
quality downward in this experiment. It is not a physical dropped-frame count.

The sender revision and reference revision `75f8497b6ffefadd8c0403728b93ccfbbfa02f52`
were recorded by the operator; this test's output does not itself attest those
revisions. The reference loader does verify the pinned protocol source hash.

The target was 18,000 slots at 30 fps, quality range 20..75, 20 Mbps MSV1 cap,
and 200 ms host age deadline. The 600.285-second run included feedback grace.
It submitted and encoded 17,999 frames, skipped one slot, replaced two waiting
JPEGs and sent 17,997 complete frames. The wrapper discarded one datagram from
**360** sent frames. The reference reassembled **17,637** frames, reported
5,857 invalid datagrams and no reply errors. The invalid count includes later
chunks rejected after a gap, and is not a frame count. For all 360 sent selected
frame IDs, the log shows a newer status-0 reference feedback before the next
50-frame selection boundary. This is host-reference ingress recovery, not an
assertion of decode, display, or physical loss recovery. There were 360 pending
feedback entries at shutdown for the deliberately incomplete frames; the
bounded pending set did not exceed its configured limit. The sender ended
at quality 21. The separately returned logging summary reported zero dropped
records and no error. MSV1 wire rate was 4.394 Mbps over the full duration,
excluding lower-layer overhead, audio and input.

Reproduce from `tools/gamebub` after setting up the pinned reference and source
clip; save this script under a new `artifacts/` filename and use a new log path.
It opens a loopback-only peer and deliberately damages the traffic; it does not
connect to the handheld. The source recording repeats and other host activity
was not controlled.

```python
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd()))
from reference_loopback import ReferencePeer, load_reference, loop_clip
from stream_sender import run

original = load_reference(Path("C:/ai/moonbub-reference"))
injected = set()


class LossyReassembler:
    def __init__(self):
        self.receiver = original.Reassembler()

    def accept(self, data):
        packet = original.parse_packet(data)
        if packet.frame_id % 50 == 0 and packet.offset == 1024:
            injected.add(packet.frame_id)
            return None
        return self.receiver.accept(data)


peer = ReferencePeer(SimpleNamespace(Reassembler=LossyReassembler, FEEDBACK=original.FEEDBACK))
args = SimpleNamespace(
    target="127.0.0.1",
    port=peer.port,
    source_port=0,
    start_frame_id=0,
    log=Path("artifacts/fault-new.jsonl"),
    clip=None,
    fps=30,
    mbps=20,
    max_age_ms=200,
    quality=75,
    min_quality=20,
    frames=18000,
)
try:
    sender = run(args, loop_clip(Path("artifacts/media/Xonotic-0-8-2-gameplay.webm"), 30))
finally:
    receiver = peer.close()
print(json.dumps({"injected_frames": len(injected), "sender": sender, "receiver": receiver}))
```

Run with `C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c
'py.exe -3.11 -m uv run --locked python artifacts/fault-new.py'`. The original
ignored artifacts are `xonotic_fault_soak.py`, `xonotic-fault-soak-10m.jsonl`
and `xonotic-fault-soak-10m-summary.json`.
