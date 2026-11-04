/**
 * @file tools/gamebub/native/encoder_case.h
 * @brief Offline native encoder comparison against frozen source and bank oracles.
 */
#pragma once

// standard includes
#include <chrono>
#include <functional>

// local includes
#include "body_case.h"
#include "inner_encoder.h"
#include "patch_encoder.h"

namespace gamebub::v20::encoder_case {
  /** @brief Reject a byte mismatch with a precise offset, without dumping source pixels. */
  inline void exact(std::span<const std::uint8_t> actual, std::span<const std::uint8_t> expected, std::string_view stage) {
    if (actual.size() != expected.size()) {
      throw std::invalid_argument(std::string(stage) + " byte length: native=" + std::to_string(actual.size()) + ", frozen=" + std::to_string(expected.size()));
    }
    const auto mismatch = std::mismatch(actual.begin(), actual.end(), expected.begin());
    if (mismatch.first != actual.end()) {
      throw std::invalid_argument(std::string(stage) + " byte mismatch at " + std::to_string(mismatch.first - actual.begin()));
    }
  }

  /** @brief Build an explicit outer frame from actual native inner and selected patch bytes. */
  inline std::vector<std::uint8_t> packet(const candidate::BuildRequest &request, const candidate::BuildResult &built, const std::vector<std::vector<std::uint8_t>> &patches) {
    body::require(built.inner.size() <= 2 * 1024 * 1024 && patches.size() <= 4, "encoded frame allocation bound");
    std::vector<std::uint8_t> blob;
    for (const auto &patch : patches) {
      body::require(patch.size() <= 49152, "encoded patch bound");
      encoder::append32(blob, static_cast<std::uint32_t>(patch.size()));
      blob.insert(blob.end(), patch.begin(), patch.end());
    }
    std::vector<std::uint8_t> out(61);
    std::copy_n("AR03", 4, out.begin());
    out[4] = 3;
    out[5] = request.key ? 1 : request.promoted ? 2 :
                                                  0;
    body::put32(out, 6, request.epoch);
    body::put32(out, 10, request.frame_id);
    out[14] = static_cast<std::uint8_t>(request.reference_slot);
    out[15] = static_cast<std::uint8_t>(request.destination_slot);
    body::put32(out, 16, request.reference ? request.reference->id : 0xffffffffU);
    if (request.reference) {
      std::copy(request.reference->tag.begin(), request.reference->tag.end(), out.begin() + 20);
    }
    std::copy(built.stored_tag.begin(), built.stored_tag.end(), out.begin() + 36);
    body::put32(out, 52, static_cast<std::uint32_t>(built.inner.size()));
    out[56] = static_cast<std::uint8_t>(patches.size());
    body::put32(out, 57, static_cast<std::uint32_t>(blob.size()));
    out.insert(out.end(), built.inner.begin(), built.inner.end());
    out.insert(out.end(), blob.begin(), blob.end());
    encoder::seal(out);
    return out;
  }

  /**
   * @brief Re-encode an isolated source with exact pre-banks, including real mandatory retries.
   * @param path Derived encoder-case JSON with frozen source/profile/attempt metadata.
   * @return Scoped byte/oracle report; this does not measure capture, transport or playback.
   */
  inline body_case::Json run(const std::filesystem::path &path) {
    using body_case::blob;
    using body_case::number;
    using Json = body_case::Json;
    // Validate the original frozen output independently before asking the encoder to reproduce it.
    const auto frozen_decode = body_case::run(path);
    const auto metadata = Json::parse(body_case::read_file(path, 1024 * 1024));
    const auto base = path.parent_path();
    body::require(metadata.at("geometry").at("width") == 720 && metadata.at("geometry").at("height") == 480, "encoder profile geometry");
    const auto &oracle = metadata.at("encoder_oracle");
    const auto &profile = oracle.at("selected_profile");
    body::require(profile.is_array() && profile.size() == 2, "encoder oracle map shape");
    const candidate::Map map {static_cast<unsigned>(number(profile[0], 32)), static_cast<unsigned>(number(profile[1], 32))};
    body::require(std::find(candidate::maps.begin(), candidate::maps.end(), map) != candidate::maps.end(), "encoder declared map");
    const auto expected_packet = blob(base, metadata.at("packet"), static_cast<std::size_t>(number(metadata.at("packet").at("bytes"), 49152)));
    const auto expected_ack = blob(base, metadata.at("ack"), 43);
    const auto raw_source = blob(base, metadata.at("source_rgb"), 720 * 480 * 3);
    const auto source = std::make_shared<const candidate::Source>(std::span<const std::uint8_t>(raw_source));
    std::array<std::shared_ptr<const body::Bank>, 2> banks;
    for (unsigned slot = 0; slot < 2; ++slot) {
      const auto &data = metadata.at("pre_banks").at(std::to_string(slot));
      if (!data.is_null()) {
        banks[slot] = std::make_shared<const body::Bank>(body::Bank {
          static_cast<std::uint32_t>(number(data.at("id"), 0xfffffffeU)),
          body_case::tag(data.at("tag")),
          body_case::planes(base, data.at("planes"), 720, 480)
        });
      }
    }
    const bool key = expected_packet[5] == 1, promoted = expected_packet[5] == 2;
    body::require(metadata.at("key") == key && metadata.at("promoted") == promoted && oracle.at("key") == key && oracle.at("promoted") == promoted, "encoder oracle frame flags");
    const unsigned ref = expected_packet[14], dest = expected_packet[15];
    const auto &reference_oracle = oracle.at("reference");
    const auto &destination_oracle = oracle.at("destination");
    const auto &map_oracle = oracle.at("roi_quantmap");
    body::require(number(reference_oracle.at("bank"), 255) == ref && number(reference_oracle.at("id"), 0xffffffffU) == body::u32(expected_packet, 16) && body_case::tag(reference_oracle.at("tag")) == body::tag_at(expected_packet, 20) && number(reference_oracle.at("geometry").at("width"), 720) == 720 && number(reference_oracle.at("geometry").at("height"), 480) == 480, "encoder reference oracle mismatch");
    body::require(number(destination_oracle.at("bank"), 255) == dest && body_case::tag(destination_oracle.at("tag")) == body::tag_at(expected_packet, 36), "encoder destination oracle mismatch");
    body::require(number(map_oracle.at("roi_scale"), 32) == map.roi && number(map_oracle.at("background_scale"), 32) == map.background && oracle.at("packet_sha256") == body_case::digest(expected_packet), "encoder map/hash oracle mismatch");
    const candidate::BuildRequest request {source, ref == 255 ? nullptr : banks[ref], body::u32(expected_packet, 6), body::u32(expected_packet, 10), ref, dest, key, promoted, map};
    const auto encoded = encoder::encode_inner(request);
    const auto inner_size = body::u32(expected_packet, 52);
    exact(encoded.inner, std::span(expected_packet).subspan(61, inner_size), "GM01 inner");
    body::require(encoded.inner.size() == number(oracle.at("inner_bytes"), 2 * 1024 * 1024) && encoded.stored_tag == body::tag_at(expected_packet, 36), "encoder inner oracle/tag mismatch");
    const auto all_patches = encoder::encode_patches(*source);
    body::require(all_patches.size() == 4, "native mandatory patch count");
    std::vector<std::vector<std::uint8_t>> selected;
    const auto expected_blob = std::span(expected_packet).subspan(61 + inner_size, body::u32(expected_packet, 57));
    std::size_t cursor = 0;
    for (unsigned i = 0; i < expected_packet[56]; ++i) {
      const auto length = body::u32(expected_blob, cursor);
      cursor += 4;
      body::require(length <= expected_blob.size() - cursor, "frozen patch length");
      const auto bytes = expected_blob.subspan(cursor, length);
      const auto decoded = body::decode_patch(bytes, 720, 480);
      const candidate::Rect rect {decoded.x, decoded.y, decoded.width, decoded.height};
      const auto found = std::find(candidate::rectangles.begin(), candidate::rectangles.end(), rect);
      body::require(found != candidate::rectangles.end(), "frozen requested rectangle");
      const auto &generated = all_patches[found - candidate::rectangles.begin()];
      exact(generated, bytes, "HUD patch");
      selected.push_back(generated);
      cursor += length;
    }
    body::require(cursor == expected_blob.size() && expected_blob.size() == number(oracle.at("patch_bytes"), 49152), "encoder patch blob oracle");
    const auto direct_packet = packet(request, encoded, selected);
    exact(direct_packet, expected_packet, "AR03 frame");
    body::require(direct_packet.size() == number(oracle.at("packet_bytes"), 49152), "encoder complete byte oracle");
    Json attempts = Json::array();
    const bool mandatory = metadata.at("policy") == "mandatory";
    body::require(mandatory || metadata.at("policy") == "baseline", "encoder case policy");
    if (mandatory) {
      candidate::Policy policy(49152, request.epoch);
      for (unsigned slot = 0; slot < 2; ++slot) {
        if (banks[slot]) {
          policy.seed_reference(slot, *banks[slot]);
        }
      }
      encoder::FrameBuilder builder;
      const auto prepared = policy.prepare(source, request.frame_id, encoder::encode_patches, std::ref(builder), key, promoted);
      body::require(prepared.accepted(), "native mandatory candidate rejected");
      exact(policy.packet(prepared), expected_packet, "mandatory AR03 candidate");
      const auto &expected_attempts = oracle.at("attempts");
      body::require(expected_attempts.is_array() && expected_attempts.size() == prepared.metrics().attempts.size(), "mandatory attempt count");
      for (std::size_t i = 0; i < prepared.metrics().attempts.size(); ++i) {
        const auto &attempt = prepared.metrics().attempts[i];
        const auto &expected = expected_attempts[i];
        body::require(attempt.map.roi == expected.at("roi_scale") && attempt.map.background == expected.at("background_scale") && attempt.complete_bytes == expected.at("attempted_complete_bytes") && attempt.accepted == expected.at("accepted"), "mandatory attempt oracle");
        attempts.push_back({{"roi", attempt.map.roi}, {"background", attempt.map.background}, {"complete_bytes", attempt.complete_bytes}, {"accepted", attempt.accepted}, {"build_ns", attempt.build_ns}, {"validation_ns", attempt.validate_ns}, {"discard_ns", attempt.discard_ns}});
      }
      exact(policy.commit(prepared), expected_packet, "committed mandatory packet");
      body::require(policy.acknowledge(expected_ack) && policy.pending() == 0 && !policy.active(), "native encoded AF03 lifecycle");
      for (unsigned slot = 0; slot < 2; ++slot) {
        const auto &expected = metadata.at("post_banks").at(std::to_string(slot));
        if (!expected.is_null()) {
          const auto lease = policy.acquire(slot);
          body::require(lease->bank().id == number(expected.at("id"), 0xfffffffeU) && lease->bank().tag == body_case::tag(expected.at("tag")), "native encoder confirmed bank");
        }
        body::require(policy.readers(slot) == 0, "native encoder leaked reader");
      }
    }
    return {{"scope", "native_encoder_fixture"}, {"label", metadata.at("label")}, {"id", request.frame_id}, {"inner_bytes", encoded.inner.size()}, {"selected_patch_count", selected.size()}, {"packet_bytes", direct_packet.size()}, {"inner_byte_exact", true}, {"patches_byte_exact", true}, {"ar03_byte_exact", true}, {"mandatory_policy_verified", mandatory}, {"mandatory_policy_analysis_reuse", mandatory}, {"policy_attempts", attempts}, {"frozen_decode", frozen_decode}, {"profiling_not_playback", true}};
  }
}  // namespace gamebub::v20::encoder_case
