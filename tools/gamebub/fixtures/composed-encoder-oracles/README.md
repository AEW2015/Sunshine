# Independent CP23 encoder oracles

These fixtures target MoonBub commit `4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`.
They exercise a fresh independent AR03 key plus four nonreferenced LEGACY HC22
patches. They do not establish P-frame, HD22, reference publication, network,
FPGA, or playback support. `generation=1` belongs to a fresh sender instance.

The complete CP23 cap is 49,152 bytes. Its framing costs 124 bytes more than
AR03 carrying the same four patches, so the existing AR03 mandatory-HUD encoder
benchmark cannot be relabeled as a CP23 encoder benchmark.

`static.json` preserves all twelve output records from the pinned recovery-v24
results blob (SHA256 `93f91047a7b2ae82e866ac35de54d673ca228fa7331ea3d39fc3a62699dec802`).
They are three distinct epoch variants of one uniform scene, including repeated
epoch1 probes; they are not twelve different game scenes.

`nonuniform.json` comes from fresh `JointSender(epoch=7).build(rgb,19,force_key=True)`
instances in an isolated child process importing the unmodified pinned source
tree. Accepted packets were independently passed to `JointReceiver.prepare`,
then the model's explicit `mark_writes_drained` and `present` events to freeze
JA23 and full-display hashes. These injected model events are not hardware evidence.

Sources are exactly 480 rows by 720 columns, packed RGB8:

- `asymmetric-boxes`: RGB(44,96,156) background; overwrite `[y40:133,x17:213]`
  with (213,72,19), then `[y331:442,x151:579]` with (29,180,70), then
  `[y82:96,x22:182]` with (230,210,11). Half-open endpoints apply.
- `pattern`: at zero-based `(x,y)`, channels are `(x//9+3*(y//17))%256`,
  `((x//23)*31+(y//13)*7)%256`, and `(x+y//3)%256`.

The box scene at cap7542 rejects first choice7543 and selects second6941.
Cap256 pays all four rejected candidates7543/6941/6663/6503. The patterned
scene's first complete pair is38290 bytes. Tests regenerate original RGB8 and
check its SHA before comparing full packets, ACKs, attempt sizes and display.

The reference environment was CPython3.11 with NumPy1.26.4 and PyAV from the
separate GameBub tooling environment. Neither the frozen Python module globals
nor the installed receiver image were modified.
