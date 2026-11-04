# v20 transport contract audit (2026-11-04)

Read-only source audit of Moonbub commit `27a4dde6a7e2ea4fab09d892551ef542f05c8965`. The artifact checkout currently reports a different `HEAD` and deleted tracked paths; all facts below were read with `git show`/`git ls-tree` from the pinned commit. No checkout/reset was used. This is a source/model audit, not a hardware or radio claim.

## Executable contract sources

`hardware/gamebub-v20/export_contract.py` imports the runnable serializers from `experiments/python-game-frame-grant-study/{framing.py,gateway.py,frame_credit.py}` and generates `hardware/gamebub-v20/wire-contract.json` plus `include/gb_wire.h`. Blob IDs at the pinned commit:

| File | Git blob |
|---|---|
| `experiments/python-game-frame-grant-study/framing.py` | `3dbe2754b42fdec049d955636de2ba3673ca41aa` |
| `experiments/python-game-frame-grant-study/gateway.py` | `eb9f67fd6b7e3d4868aae55caf2ebbc05934bb3f` |
| `experiments/python-game-frame-grant-study/frame_credit.py` | `d098f082e86479571682f053cd49ed4df8de9810` |
| `experiments/python-game-frame-grant-study/results.json` | `2c61129bd3790242262306e0db7890b6f7ce1160` |
| `hardware/gamebub-v20/export_contract.py` | `dfeda01f6fffb487234fe79e10c84792c3f21dec` |
| `hardware/gamebub-v20/wire-contract.json` | `e48e81f738219eeb06f51735b55729f79dd0ab00` |
| `hardware/gamebub-v20/include/gb_wire.h` | `b74d177b29b3aff828f752c951671c1c1167bf3e` |

The contract identifies GF03, TOKEN, PC18, QC18 and FG19 by explicit `struct` formats, and produces matching byte offsets/constants. Integer fields in these transport messages are network byte order. CRC trailers use IEEE/zlib CRC32 of preceding bytes, stored in that message's declared byte order. Decode fields explicitly; do not cast packed C structs.

| Message | Field layout (offset: size) | Total | Contract behavior |
|---|---|---:|---|
| GF03 | magic 0:4, version 4:1, epoch 5:4, frame 9:4, total 13:4, fragment index 17:2, count 19:2, payload length 21:2, complete-packet CRC 23:4, AR03-body CRC 27:4 | 31-byte header + payload | v3, at most 49,152 frame bytes; 1,008-byte payload; fragment geometry and both completed-data CRCs checked by reassembly. No per-fragment CRC trailer. |
| TOKEN | epoch 0:4, packet slot 4:2, reserved zero 6:2, sequence 8:8 | 16 | Prefix on GF03 datagram. |
| PC18 | magic 0:4, epoch 4:4, packet slot 8:2, query/reply flag 10:2, sequence 12:8, status 20:1, token-header CRC 21:4, CRC trailer 25:4 | 29 | Returns packet-buffer capacity, never frame-slot ownership. |
| QC18 | magic 0:4, epoch 4:4, packet slot 8:2, reserved zero 10:2, sequence 12:8, token-header CRC 20:4, CRC trailer 24:4 | 28 | Queries a missing packet credit. |
| FG19 | magic 0:4, version 4:1, kind 5:1, frame slot 6:2, epoch 8:4, frame 12:4, nonce/sequence 16:8, total bytes 24:4, AR03-body CRC 28:4, CRC trailer 32:4 | 36 | Kinds 1..8: REQUEST, CANCEL, GRANT, BUSY, RELEASE, CANCELED, FINISH, FINISHED. Epoch is fixed to 1 in this lab model. |

For context, the same export describes AR03 as little-endian: 61-byte fixed header, variable inner/UI body, then final 4-byte CRC (65 fixed envelope bytes, not a contiguous header). AF03 is 43 bytes total. The export's actual packet example is synthesized from retained source RGB, passed through the frozen AR03 encoder/receiver, then wrapped as GF03/TOKEN and PC18/QC18/AF03; it is a software fixture.

## Ownership transitions and 1,725 control messages

`frame_credit.py` is the FG19 model. REQUEST reserves an exact receiver slot only on a matching GRANT; BUSY does not grant capacity. CANCEL succeeds only before any fragment is consumed. FINISH marks the sender transaction complete, and optional FINISHED confirms that the finish barrier arrived. The receiver emits RELEASE only after `finished` and `receiver_drained(frame)` are both true. That is the model's signal that ingress/read/decode has drained and receiver ownership can be cleared. The sender applies RELEASE only when frame, epoch, sequence/nonce, size, body CRC and slot match its outstanding owner and finish condition. Stale or wrong-kind replies cannot free another owner.

The serialized histories are in `experiments/python-game-frame-grant-study/results.json`, under each case's `result.frame_grants.history`; `export_contract.py` selects `sender_request`, `sender_cancel`, `sender_finish`, and `receiver_reply`, re-seals each event with `frame_credit.seal`, and stores wire hex/hash, parsed fields, model timestamp, and delivered flag in `wire-contract.json`'s `frame_control_sequences`. The export contains nine histories and 1,725 serialized messages total. Six histories have only delivered records; the `lost_grant` history has 2 messages (one intentionally lost) and safe-stops on `frame_control_reply_timeout`; `lost_release` has 5 (one intentionally lost) and safe-stops on `frame_release_reply_timeout`; `packet_credit_blackhole` has 2 and safe-stops on `packet_credit_query_timeout`. Control timestamps/losses are simulated model data, not a packet capture or calibrated radio timing. In particular, loss of RELEASE conservatively leaves sender ownership pinned; timeouts stop instead of inventing a credit.

## What can be tested from the wire contract

Native endpoint tests can consume `wire-contract.json` and the generated C constants to check golden bytes/offsets, CRC/endian handling, exact lengths, reserved fields, limits, GF03 fragmentation/reassembly, and every serialized FG19 message in order. Replay should check that duplicate/stale/wrong-owner replies do not mutate a distinct sender ledger entry; model unit tests and the exported histories are software evidence, not proof of hardware timing or an implementation's internal drain.

The exact physical ownership predicate represented by `receiver_drained(frame)` remains unverified: source code does not establish real FIFO emptiness, DMA completion, CDC visibility, SDRAM/read/decode completion, display independence, reset/rekey behavior, or integrated endpoint semantics. In the model, FINISH is accepted only for a matching reserved receiver owner and sets its `finished` flag; FINISHED, when configured, replies to acknowledge that FINISH was received. Neither is a drain certificate. RELEASE is emitted later only when the model's `receiver_drained(frame)` callback is true, and only a concrete receiver implementation can establish that its predicate covers all real consumers. PC18 models packet-buffer reuse only. The v20 README explicitly leaves true FIFO credits/endpoints, capability negotiation/reset/recovery, FPGA implementation/timing, ESP service, RF, and physical sustained 30 fps open. Do not infer those from the 1,725-message replay.
