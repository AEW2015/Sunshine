# Proposed 25 fps legacy MSV1 hardware test

This is a test proposal only. No media, capture, service, hardware, or receiver
session was started while preparing it.

## Identity and endpoint boundary

- Pin the Windows sender source to `61fef798556c78bc2d4f4788400a14005e41f646`.
  Record the exact sender executable/source hashes in the run manifest.
- Pin the Sunshine legacy test checkout to
  `fd0376fd152c07f563a398c89395498d39079a28`.
  Frozen candidate label: `gamebub-msv1-25fps-candidate-20261105`.
  This label identifies the test candidate; it is not a 25 fps result.
- Name the sender **GameBub standalone MSV1/JPEG sender**. It is a separate
  lab sender, not a released stock Sunshine version.
- This test is for the existing legacy JPEG/MSV1 endpoint and its AV v1 input
  channel only. The CU66 v70 development path has no confirmed compatibility
  with that endpoint. Do not send CU66-v70 traffic to it; proceed only after the
  receiver owner confirms an installed MSV1-compatible image and endpoint.

## Proposed run

After fresh receiver agreement and readiness confirmation, run one 30-second
session with these proposed settings:

| Setting | Proposed value |
|---|---|
| Coded canvas | 720×480 |
| Video rate | 25 fps, 750 target slots |
| JPEG quality | 25 |
| Video bitrate cap | 6 Mbps, proposed capacity-probe setting |
| Shift | 0 px |
| Source | Xonotic saved clip, legacy sampler, offset 0, looped if needed |
| Clip SHA-256 | `36ef854b29293c027dd161185dc0a2e9d03ec7854ea9039800164b03956d3a83` |
| Wait candidate | hybrid with 600 µs spin tail |
| AV mode | input-only AV v1; PC audio capture and gamepad injection off |

The 6 Mbps cap and hybrid600 wait are proposed settings, not assertions about
the receiver’s last operating configuration. The 25 fps run is a capacity probe,
not a like-for-like comparison with the earlier 20 fps / 4 Mbps test: both frame
rate and cap differ. Before launch, record the actual installed app and FPGA
identities, endpoint, current video cap and pacing configuration, source and
bind addresses, queue settings, and starting receive/decode/present/drop
counters. Obtain receiver-owner agreement to any proposed setting that differs
from its current operating configuration. If settings cannot be confirmed, do
not start media.

Do a host-side Q25 demand preflight with the planned legacy sampler before
selecting a cap. The existing [60-frame native JPEG sample](measurements/jpeg-quality-20261105.md) estimated 5.130 Mbps of
MSV1 application payload at 30 fps, or about 4.275 Mbps when prorated to 25 fps;
these are demand estimates, not achieved rates or proof for the legacy sampler.
They show why a 4 Mbps cap can cause sender-side replacements before 25 fps.
If the receiver owner requests 4 Mbps specifically as a matched baseline, label
it that way and expect possible pre-send replacements. Retain source-sampling,
encoded-replacement, sent, accepted, and skipped-slot counts separately.

The legacy sampler preserves the established source policy. Keep the exact clip
hash and offset. Do not select native CFR for this 25 fps run; a sampling-policy
change would be a separate workload. Record actual sent FPS using both the
sender media duration and the complete harness wall duration, alongside the
configured 25 fps rate; do not report the configured rate as measured output.

## IDs, capture, and run order

1. Confirm an unused frame-ID range of 750 consecutive IDs with the receiver
   owner. Record the chosen first ID and range in the manifest. This document
   reserves no IDs.
2. Select the host capture interface from a fresh `dumpcap -D` listing and
   record the exact interface name, capture point, filter, and output path.
   Confirm the capture owner is active and its output file exists before AV or
   video starts. Capture must cover the AV handshake, all video sends and
   feedback, AV input packets, and the session’s actual STOP.
3. Run the selected 30-second configuration. Do not open PC audio capture or
   virtual gamepad injection. Record media-end and STOP times separately.
4. Let the owned capture reach its configured finite safety autostop naturally.
   Do not count termination without native final statistics as complete
   capture coverage. After finalization, verify the actual STOP packet in the
   capture using the session identity/cookie and retain captured/received/drop
   statistics.
5. Reconcile target/submitted/encoded/sent/accepted/replaced/skipped/partial
   video counts, input packet and lease counts, receiver counter deltas, STOP,
   and cleanup. Record camera coverage through STOP separately from host logs
   and capture.

Use a fresh trace epoch and fresh starting receiver counters. Do not assume the
previous address, interface, installed image, queue configuration, pacing
choice, or capture readiness remains current. Stop if receiver identity or
compatibility is uncertain, the ID range is not fresh, capture is not active
before AV, or any unexpected media/cleanup failure occurs.

## Evidence boundary

This run would measure host sender behavior, local capture visibility, and the
confirmed receiver counters available for the installed legacy image. A host
capture does not prove RF departure or receiver presentation. Keep physical
camera observation and receiver decode/presentation counters as separate
evidence. This procedure makes no assertion that the proposed settings have
been run or that they qualify 25 fps hardware performance.
