# Coupled packet/frame ownership checkpoint

The new `native/transport_ownership.h` wraps the existing bounded `PacketLedger`
and `SenderFrames` in one noncopyable `SenderOwnership` component. It closes
caller-side transport preconditions that `packet_model.h` previously enforced
manually. This is offline **epoch-one** state validation, not a live custom
endpoint, reference publication, physical-drain proof or 30 fps result.

## Source-backed scope

The inherited GF03/FG19/PC18/QC18 wire contract remains pinned to the existing
MoonBub `27a4dde` transport implementation; no fields or packet kinds changed.
The full-state/reset review also inspected MoonBub
`4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`, particularly
`experiments/python-game-recovery-v24-study/model.py` (Git blob
`a0ccf6087be6ca38c903b6ecf49903aeb02bec85`) and its tests. That Python model
checks live modeled readers/candidates before reset and enforces independent
base/full-HUD media after a new epoch. Those remain distinct media/reset gates.

Existing `recovery_host.h` supplies host agreement phases and explicit drain
inputs. `recovery_replay.h` replays 124 frozen controls using modeled clear
owners because the transcripts contain no full owner/drain snapshots; its
receiver-state/media-reset/physical-drain flags remain false. This checkpoint
does not relabel that replay as a complete receiver model.

## Implemented behavior

- Reserve the shared FG19 mailbox before mutating a frame intent. BUSY returns
  only that control reservation and never invents a frame grant.
- Couple exact GRANT acceptance to a registered packet account. At most two
  granted frames, five DATA permits and one shared QC18/FG19 mailbox remain owned.
- Require every fragment to be enqueued/resolved and the query mailbox returned
  before FINISH. FINISHED releases only its control mailbox; frame storage and
  its packet account remain owned until exact RELEASE.
- Permit CANCEL only with no outstanding DATA reservation and no prior queue handoff. An unsent
  packet reservation can first be returned through the existing exact-token
  cancellation API. Once CANCEL/FINISH begins, new DATA admission for that
  frame is frozen. CANCEL BUSY retains the frame and reopens its DATA admission;
  exact CANCELED returns frame and packet account together.
- Validate control CRC, identity, slot and expected kind before coupled state
  effects. Component ledgers remain private; the following fixed-size updates
  have guaranteed capacity and no externally mutable intermediate state.
- Keep admission stopped after an unknown outcome. Exact late grants, credits,
  FINISHED and RELEASE may settle already-issued work without resuming new work.
  An unresolved late grant remains owned rather than being discarded.
- Derive local RS24 drain blockers from actual component packet/frame/mailbox
  counts, while requiring an explicit external transport-drain signal and
  source/candidate/reference-reader counts. Credits, an empty packet queue or
  FINISHED cannot substitute for those external facts.

This wrapper does not authenticate a peer or validate codec payloads. It does
not inspect CP23/JA23, replace `composed_transaction.h`'s `PendingPair`, publish
base/HUD references, provide a durable epoch ledger or bridge the fixed epoch-one
transport to RS24's later epochs. CP23/HC22/HD22 remains the selected first-fixture
profile; no CP25 selection or new network port is implied.

## Verification

The shared native build passed **154 GameBub tests across 19 suites**, including
all **14 new ownership tests**. New tests exercise real existing serializers,
CRC failures, wrong identities, two frame slots, shared mailbox backpressure,
unsent reservation cancellation, ever-enqueued cancellation rejection,
query-before-FINISH blocking, FINISHED retention, exact RELEASE, sticky stop,
late settlement and independent reset blockers. Their payloads are deterministic
non-codec bytes, not an encoded-game or decoder benchmark.

Read-only gcov extraction from the isolated full-test profiles reports **81/81
executable header lines**, with all functions hit. Compiled branches were
191/312 hit, including compiler/exception edges; full branch coverage is not
claimed. The two new files were directly formatted using the root tooling
environment's clang-format; diff whitespace checks pass.

Local evidence:

- `tools/gamebub/artifacts/encoder-sequence-20261105/native-test-output-final.txt`
- `tools/gamebub/artifacts/encoder-sequence-20261105/native-results-final.xml`
- `tools/gamebub/artifacts/precise-wait-20261105/ownership-coverage/source-summary.json`
- `tools/gamebub/artifacts/precise-wait-20261105/ownership-coverage/test_gamebub_transport_ownership.cpp.gcov.json.gz`

Reproduce with the existing separately built test target:

```powershell
& C:\msys64\msys2_shell.cmd -defterm -here -no-start -ucrt64 -c './cmake-build-gamebub/tests/test_sunshine.exe --gtest_filter="GamebubTransportOwnership.*"'
```

Next integration gate: bind the separately validated media transaction and its
source/reference owners to this transport state under the jointly agreed
CP23 carriage/reset contract. A complete compatible receiver/FPGA fixture and
actual transport-drain evidence are still required before custom hardware use.
No hardware traffic, installed service change or new bitstream occurred here.
