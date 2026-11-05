# Remaining Windows gates for CP23 / HC22 / HD22

Date: 2026-11-05. Source-bound gap audit, not a hardware-readiness declaration.

The selected reference remains MoonBub
`4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189`. CP25/GM25/HD25 is not selected.
Reference paths below are relative to that revision, available locally through
`git -C tools/gamebub/artifacts/moonbub-30fps-study show 4025d355:PATH`.
This audit changes no executable, endpoint, installed service or firmware.

## What Windows already has

| Component | Implemented scope | Boundary |
| --- | --- | --- |
| `native/composed_wire.h` | Bounded CP23/JA23/HC22/HA22 identity, framing, CRC/digest parsing and serialization | Syntax/identity checks do not establish decoded pixels or publication. |
| `native/composed_encoder.h`, `refresh_encoder::encode` | Original RGB8 independent key plus four complete LEGACY HUD patches; all ordered real candidates; full 49,152-byte pair admission; selected software decode and JA23 validation | No stateful P frames, HD22 sender, acknowledged HUD banks or joint reference publication. |
| `native/key_budget_encoder.h`, `KeyBudgetBuilder` | Optional independent-key size-first strategy; actual entropy sizes for every attempted map; only fitting keys get full inverse/tag finalization | Rejects predictive, promoted and referenced requests. Default `FrameBuilder` remains available. |
| `native/inner_encoder.h`, `native/candidate.h` | Base key/P/promotion primitives, exact frame-local analysis binding, standalone AR03 `candidate::Policy` leases/prepare/commit/AF03 acknowledgement | Existing AR03 component state is not an atomic CP23 sender. |
| `native/hud_delta.h`, `hud_delta::decode` | Private bounded HD22 RAW/COPY/SPAN_XOR reconstruction and tag validation | No native HD22 encoder, confirmed HC22 sender cache or atomic joint HUD receiver. |
| `native/composed_refresh.h`, `decode_legacy_refresh` | Private software decode/display/ACK check of independent LEGACY refresh pairs | No stateful joint receiver or hardware write-drain/vblank proof. |
| `native/composed_transaction.h`, `transaction::PendingPair` | One copied immutable outstanding pair, identical retry, exact whole JA23 match, monotonic acknowledged frame | Retires only its private retry bytes; does not publish base/HUD banks or release transport owners. |
| `native/transport_ownership.h`, `transport::SenderOwnership` | Coupled bounded epoch-one GF03/FG19/PC18/QC18 packet/frame ledgers; sticky stop, exact late settlement, explicit drain blockers | No live endpoint or RS24 epoch bridge. Packet receipts/FINISHED are not decoder ACKs or physical drain. |
| `native/recovery_host.h`, `recovery::Host` / `EpochLedger` | Offline RS24 agreement, finite retries, retained unknown outcomes, explicit modeled drain gate | Ledger is in memory; no durable storage or live codec/transport reset coupling. |
| `native/composed_sequence.h`, `composed_sequence::run` | One-process hash-bound saved-source replay, explicit repeat, bounded metadata, separately paid input/encode/hash/retirement work | Each iteration is codec epoch `i+1`, frame 0, HUD generation 1. This is independent fixtures, not a stateful stream or transport-epoch exercise. |

## Next implementation order and acceptance gates

1. **Native HD22 encoder and HC22 sender cache.** Port the selected exact
   `experiments/python-game-gap-span-study/model.py` functions `optimal_row_spans`,
   `encode`, `inspect`, `decode`; then
   `experiments/python-game-hd22-joint-study/model.py` `hud_Sender.prepare`,
   `retry`, `accept_ack`. Retain the pinned LEGACY-versus-HD22 selection rule
   (`len(full) <= len(delta)` selects LEGACY), acknowledged-only references,
   generation/frame/tag binding and destination-bank alternation. Gate on exact
   RAW/COPY/SPAN_XOR bytes, canonical merged-zero spans, tie choices, original
   RGB565 reconstruction, odd/bounded geometry, stale reference/tag rejection,
   and no confirmed-cache change before exact HA22. Extend the existing
   `test_gamebub_hud_delta.cpp` oracle coverage with encoder and sender goldens.

2. **A joint native sender, with real stateful P/promotion and complete-pair
   admission.** Port selected `JointSender.build`, `_owned`, `discard`, `commit`,
   `ack` from the same joint-study model. Reuse verified base primitives, but
   keep HUD preparation and base candidates private until one atomic joint
   commit. Do not independently call the two existing component commit/ACK
   methods against live state and risk a half transition. Retain full-pair cap,
   all paid attempts, deadline checks before/after work, immutable source/frame
   binding, late-reader rechecks and exact retry bytes. Gate on independent
   multi-frame source oracles: key -> ordinary P -> promotion, unchanged HUD
   COPY and changed HUD SPAN_XOR, cap rejection with frame-ID reuse, deadlines,
   exceptions, foreign/stale/mutated candidates and late destination readers.

3. **Atomic acknowledgement and joint reference publication.** Bind the new
   sender's expected JA23 to its exact outstanding pair. The selected
   `JointSender.ack` validates both AF03 and HA22 against private component
   states before swapping joint state. `PendingPair` is a useful exact-byte
   prerequisite, not this publisher. Gate on mixed component ACKs, wrong pair
   digest/CRC/frame/epoch, duplicate/stale ACKs, lost ACK with byte-identical
   retry, and unchanged base/HUD snapshots on every rejection. Compare bank
   IDs/tags, generation, pending owners and readers to the pinned Python model.

4. **Stateful software receiver oracle before network integration.** Extend
   independent LEGACY refresh checking to selected `JointReceiver.prepare`,
   `abort`, `mark_writes_drained`, `present`, `retry_ack`. Gate on fourth-patch
   failure after private base decode, explicit write-drain plus vblank before
   publication, late base/HUD readers, immutable published banks and exact
   display/JA23 hashes across a stateful sequence. Software events remain model
   evidence; they cannot certify real FPGA fences or panel presentation.

5. **Resolve transport/recovery coupling before creating a custom socket.**
   Selected `experiments/python-game-recovery-v24-study/model.py` provides
   `Host.build`, `commit`, `acknowledge_data` and `Target.prepare_data` around
   the joint codec. Current native RS24 and epoch-one ownership wrappers are
   separate components. Agree how the selected custom transport carries CP23,
   routes JA23, binds boot/epoch identities, settles packet/frame owners and
   proves drain; do not invent an epoch extension for GF03/FG19/PC18/QC18.
   Implement durable atomic epoch reservation before deployment. Gate on stale
   boot/epoch traffic, ACK/data loss, duplicate control, bounded retry exhaustion,
   shutdown with outstanding owners, restart after actual drain, and the first
   fresh-epoch independent key/full-HUD requirement. Keep unknown outcomes owned.

The joint reference's `test_model.py` supplies concrete regression names,
including `test_complete_pair_rejects_after_base_fits_and_reuses_id`,
`test_commit_rechecks_late_destination_reader_without_half_commit`,
`test_packet_loss_and_ack_loss_keep_exact_pending_pair`,
`test_mixed_ack_and_wrong_pair_digest_cannot_advance_one_component`, and
`test_receiver_requires_explicit_fence_and_vblank_then_atomic_pair`.
Use their semantics and freeze independent serialized/display/state oracles;
passing static envelope vectors alone is insufficient.

## Performance and hardware release gates

Keep all 20 existing AR03 encoder goldens and the 16 independent CP23 source
oracles exact while adding stateful cases. Preserve the fixed complete cap and
declared map order. The optional budgeted-key optimization must remain isolated
from predictive encoding until separately proven. Charge losing candidates,
source conversion/hash, HUD work, validation, cleanup and output hashing;
compare total wall/CPU as well as stage buckets whose boundaries differ.

Current same-process study repeats 60 unique decoded Xonotic sources. Its
budgeted strategy improves host cost, but 43.3% of these independent refreshes
still exceed the complete cap and encoding tails exceed 33.333 ms. See
[the same-process study](cp23-same-process-sequence-20261105.md). It does not establish stateful encoding
quality/rate or 30 fps playback. After stateful correctness, benchmark a longer
finite moving-game sequence with exact source hashes and unique original PTS;
report actual accepted/replaced frames, quality, cap failures, paid latency,
bitrate, CPU and memory separately from transport and display measurements.

Existing JPEG/AV remains the available hardware path unless the MoonBub agent
provides new verified readiness evidence. A custom CP23 hardware run requires
the selected complete decoder image and local loader, installed image/source
hashes, actual bank/fence/ACK semantics, and matching known-fixture results.
A subsequent network fixture additionally requires an agreed carriage, live
receiver and port; a local FPGA fixture does not depend on assigning a UDP port.
No custom endpoint or deployable image is
established by this Windows source audit. Proceed fixture -> short stateful
sequence -> controlled moving-content rate steps -> soak only after those gates.

This note is a source review only; no new build, test, benchmark or hardware run
was performed for it.
