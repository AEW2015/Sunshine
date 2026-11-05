# CPL1 next-network readiness, 2026-11-05

Windows source: `gamebub/windows-jpeg-retry-20261103`, code/document checkpoint
`7bcd56d388d7341edadb577301288835846efefc`. MoonBub prompt/export inspected at
`e708b61f677915e1bb96395a9961ef50465a8343` on
`feature/fpga-timing-cleanup-20261105`. No hardware traffic was sent. The installed
Sunshine service remains running and unchanged.

## Fresh offline fixture check

Exact exported asset:
`fpga/exports/cpl1-timing-fsmcopy-source-20261105-v002/key.cp23.hex`.
The byte-entry hex text SHA256 was checked before conversion:
`fca70fd87f66960ed1e617ea69215255fd61199022279b3f7331c32771026673`.

| Field | Actual Windows result | Required / expected |
| --- | --- | --- |
| Binary length | 17,412 bytes | 17,412 bytes |
| Binary SHA256 | `3255ef9bbdb71f8678547aaadd72a41bf92991b7b09ee7cd88ad2a073df08107` | Exact exported asset, converted offline |
| Identity | epoch 1, frame 0 | Parsed from asset; not a live session allocation |
| AR03 / HC22 bytes | 10,464 / 6,891 | Exact CP23 component bounds validated |
| HC22 patch dispatch | 0 / 0 / 0 / 0 | Independent LEGACY subset |
| Display words | 345,600 | 720 x 480 |
| Column-major little-endian RGB565 CRC32 | `4c5725e5` | Published `4c5725e5`: match |
| Column-major RGB565 SHA256 | `e8b55a3cf7034b2b2c6ede6ca9177025408224ec67533e27d87e090b08ac1090` | Actual diagnostic hash; no separate published SHA oracle asserted |

An isolated UCRT64 helper invoked the existing native `composed::parse_pair`
and `refresh::decode_legacy_refresh`, including nested framing/CRC/component
digest, reconstructed base/HUD tag and mandatory-rectangle checks. It explicitly
serialized words with x outer/y inner and low byte first before CRC comparison.
This is an independent Windows software reconstruction check against the
published rendered-frame CRC, not FPGA execution or presentation evidence.
The helper compiled and exited successfully. Raw conversion, helper source,
executable and result are under `artifacts/cpl1-network-preflight-20261105/`.

Existing standalone conformance executable SHA256 is
`15a08cc10367e9f26531b8f6cf1503f97217ca3f8bf56bc9497087f8dcbf22af`.
It was not replaced by the isolated helper. Earlier regression results remain
[548 Python and 173 native tests](windows-validation-20261105.md); the full
suite was not rerun for this documentation/asset-only preparation.

## Readiness boundary

- **Ready:** exact fixture software verification; preserved MSV1/JPEG and AV v1
  tooling, hash-verified saved Xonotic clip at offset zero, optional explicit
  pacing/source binding and owned outbound capture through STOP. The clip hash
  remains `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83`.
- **Compatible subset only:** the Windows independent-key/full-LEGACY checker
  accepts this exact CPL1 fixture. That does not qualify every encoder output
  against restricted HR01 INDEX_RUNS2 hardware or advertise a full CP23 profile.
- **Blocked for custom networking:** CPL1 has CAPS=0, immutable ROM input and no
  upload/decoder endpoint. No custom port, carriage, real credits/admission,
  ownership/release, reset/rekey, completion/publication/presentation, timeout or
  STOP contract was selected. Existing GF03/RS24/ownership checks are offline
  models; they do not validate a newly implemented CPL1 network protocol.
- **Legacy testing conditional:** only after MoonBub restores and freshly
  verifies a compatible JPEG/AV image. Never send CP23 bytes to UDP 5533/5534.

Before any live send, obtain fresh local-test outcomes, installed ESP32/FPGA
hashes, current address/source route, actual receive mode/port and counters.
Historical .47/.157 addresses and published timing closure are not current
device/network readiness. Begin a custom network path only with one agreed
fixture after both endpoints and recovery semantics exist, audio and injection
off. No malformed/reassembly/timeout emulator result is claimed for an
undefined custom carriage. Keep 30 unique displayed fps as a later physical gate.
