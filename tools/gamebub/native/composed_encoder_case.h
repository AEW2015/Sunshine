/**
 * @file tools/gamebub/native/composed_encoder_case.h
 * @brief Hash-bound original RGB8 input for independent native CP23 encoder studies.
 */
#pragma once

// local includes
#include "body_case.h"
#include "composed_encoder.h"

namespace gamebub::v24::refresh_encoder_case {
  /**
   * @brief Encode one bounded source descriptor and report all actual paid pair attempts.
   * @param path JSON with schema, epoch, frame, cap and source_rgb blob descriptor.
   * @return Offline encoding/hash/timing report, never playback or reference publication.
   */
  inline v20::body_case::Json run(const std::filesystem::path &path) {
    using namespace v20;
    using Json = body_case::Json;
    const auto start = std::chrono::steady_clock::now();
    const auto input = Json::parse(body_case::read_file(path, 1024 * 1024));
    body::require(input.at("schema") == "gamebub-cp23-independent-encoder-case-v1", "CP23 encoder case schema");
    const auto &descriptor = input.at("source_rgb");
    body::require(descriptor.at("dtype") == "|u1" && descriptor.at("shape") == Json::array({480, 720, 3}), "CP23 original RGB8 descriptor");
    const auto epoch = static_cast<std::uint32_t>(body_case::number(input.at("epoch"), 0xfffffffeU));
    const auto frame = static_cast<std::uint32_t>(body_case::number(input.at("frame"), 0xfffffffeU));
    const auto cap = static_cast<std::size_t>(body_case::number(input.at("cap"), composed::frame_cap));
    const auto source_start = std::chrono::steady_clock::now();
    const auto pixels = body_case::blob(path.parent_path(), descriptor, 720 * 480 * 3);
    const auto source = std::make_shared<const candidate::Source>(std::span<const std::uint8_t>(pixels));
    const auto source_prepare_ns = refresh_encoder::elapsed(source_start);
    const auto result = refresh_encoder::encode(source, epoch, frame, cap);
    Json attempts = Json::array();
    for (const auto &attempt : result.attempts) {
      attempts.push_back({{"roi_scale", attempt.map.roi}, {"background_scale", attempt.map.background}, {"complete_bytes", attempt.complete_bytes}, {"accepted", attempt.accepted}, {"build_ns", attempt.build_ns}, {"framing_ns", attempt.framing_ns}, {"discard_ns", attempt.discard_ns}});
    }
    const auto hash_start = std::chrono::steady_clock::now();
    const auto packet_hash = result.accepted() ? Json(body_case::digest(result.packet)) : Json(nullptr);
    const auto ack_hash = result.accepted() ? Json(body_case::digest(result.ack)) : Json(nullptr);
    const auto output_hash_ns = refresh_encoder::elapsed(hash_start);
    Json report {{"scope", "offline_native_cp23_independent_key_four_legacy_hud_encoder"}, {"source_commit", "4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189"}, {"epoch", epoch}, {"frame", frame}, {"cap", cap}, {"accepted", result.accepted()}, {"packet_bytes", result.packet.size()}, {"packet_sha256", packet_hash}, {"ack_sha256", ack_hash}, {"hud_bytes", result.hud_bytes}, {"attempts", attempts}, {"source_prepare_ns", source_prepare_ns}, {"output_hash_ns", output_hash_ns}, {"hud_prepare_ns", result.hud_prepare_ns}, {"validation_ns", result.validation_ns}, {"cleanup_ns", result.cleanup_ns}, {"encode_total_ns", result.total_ns}, {"p_frames", false}, {"stateful_hud", false}, {"reference_publication", false}, {"hardware_playback", false}};
    report["case_total_ns"] = refresh_encoder::elapsed(start);
    return report;
  }
}  // namespace gamebub::v24::refresh_encoder_case
