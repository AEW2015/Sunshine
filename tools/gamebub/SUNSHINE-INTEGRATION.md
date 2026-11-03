# Sunshine integration map for a negotiated Game Bub mode

This is an implementation map, not an enabled feature or an agreed protocol.
The standalone MSV1 path must first pass sustained physical receiver tests.
Do not map JPEG to an existing H.264, HEVC, or AV1 identifier. Receiver and
host must agree on a separate versioned capability and transport before any
experimental session is accepted.

## Existing stock-client path

* `src/nvhttp.cpp`, `get_codec_mode_flags()` and `serverinfo()`, publishes the
  Moonlight codec mask from encoder probes. It is global stock-client metadata,
  not a per-client Game Bub negotiation. Reusing one of its codec bits for JPEG
  would give clients the wrong meaning.
* `src/rtsp.cpp`, `cmd_announce()`, parses `x-nv-vqos[0].bitStreamFormat` as
  a raw integer and explicitly checks disabled HEVC and AV1. `src/video.h`,
  `encoder_t::codec_from_config()`, logs unknown values and falls back to H.264.
  A future implementation must not simply reinterpret a previously unknown
  value as JPEG for all clients. Verify an explicit experimental version and
  capability first and reject unsupported combinations before session creation.
* `src/stream.cpp`, `videoThread()`, obtains encoded video via `video::capture`.
  `src/video.cpp`, `make_avcodec_encode_session()` and the capture paths select
  conventional Sunshine encoders. `videoBroadcastThread()` then packetizes using
  Moonlight framing, FEC, and optional encryption. MSV1 is a distinct JPEG
  frame/chunk and feedback protocol: selecting a JPEG codec alone does not make
  this packetizer compatible.

A possible future architecture is a separately selected experimental session
which obtains Sunshine platform capture frames and runs a purpose-built,
versioned JPEG/MSV1 encoder and transport. It must retain the stock path and
its advertised formats unchanged for ordinary clients. Exact negotiation,
security, audio, input, concurrent sessions, and recovery remain open questions
for the receiver team, not choices made by this note.

## Validation before enabling

Cover explicit acceptance, unknown and malformed capability rejection, and
stock-client advertisement and behavior with native regression tests. Exercise
capture reinitialization and bounded frame queues in the new path; verify actual
JPEG syntax, packet bytes, frame IDs, pacing and receiver recovery against the
agreed protocol. Measure independently on the physical receiver. Preserve the
installed Sunshine service and test a separate candidate build.

The isolated native `test_sunshine` build passed 13 focused RTSP-header, codec
advertisement and video-format-mapping tests in November 2026. That check covers
existing behavior only; it does not test a future JPEG mode, pairing, gameplay,
or full stock Moonlight compatibility.
