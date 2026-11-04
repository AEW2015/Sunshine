/**
 * @file tools/gamebub/native/composed_case.h
 * @brief Pinned synthetic refresh reconstruction with explicit static/subset scope.
 */
#pragma once

// standard includes
#include <set>

// local includes
#include "composed_refresh.h"
#include "transport_case.h"

namespace gamebub::v24::composed_case {
  /**
   * @brief Verify all published independent-refresh probes using the native decoder.
   * @param path Exact v24 results.json blob already used for reset conformance.
   * @return Software byte/pixel/ACK checks; no capture, moving footage or hardware claim.
   */
  inline v20::body_case::Json run(const std::filesystem::path &path) {
    const auto raw = v20::body_case::read_file(path, 256 * 1024);
    v20::body::require(v20::body_case::digest(raw) == "93f91047a7b2ae82e866ac35de54d673ca228fa7331ea3d39fc3a62699dec802", "pinned CP23 results hash");
    const auto document = v20::body_case::Json::parse(raw);
    unsigned count = 0, exact_words = 0;
    std::set<unsigned> epochs;
    const auto verify = [&](const auto &output) {
      const auto packet = v20::transport_case::unhex(output.at("packet_hex"));
      const auto ack_bytes = v20::transport_case::unhex(output.at("ack_hex"));
      const auto pair = composed::parse_pair(packet);
      v20::body::require(composed::serialize_pair(pair) == packet, "CP23 exact serialization");
      const auto ack = composed::parse_ack(ack_bytes);
      const auto encoded_ack = composed::serialize_ack(ack);
      v20::body::require(std::equal(encoded_ack.begin(), encoded_ack.end(), ack_bytes.begin(), ack_bytes.end()), "JA23 exact serialization");
      const auto decoded = refresh::decode_legacy_refresh(packet);
      v20::body::require(std::equal(decoded.ack.begin(), decoded.ack.end(), ack_bytes.begin(), ack_bytes.end()), "JA23 independently constructed ACK");
      v20::body::require(pair.epoch == output.at("epoch").template get<unsigned>() && pair.frame == output.at("frame").template get<unsigned>(), "CP23 frozen identity");
      v20::body::require(v20::body_case::digest(refresh::display_le(decoded)) == output.at("display_rgb565_sha256").template get<std::string>(), "CP23 full display hash");
      for (const auto rectangle : v20::candidate::rectangles) {
        for (unsigned y = rectangle.y; y < rectangle.y + rectangle.height; ++y) {
          for (unsigned x = rectangle.x; x < rectangle.x + rectangle.width; ++x) {
            v20::body::require(decoded.frame.display565[y * 720 + x] == 0x2b13, "independent source RGB565 HUD word");
            ++exact_words;
          }
        }
      }
      epochs.insert(pair.epoch);
      ++count;
    };
    for (const auto &entry : document.at("results").at("cases")) {
      if (!entry.at("output").is_null()) {
        verify(entry.at("output"));
      }
    }
    for (const auto &output : document.at("results").at("reboot_sequence").at("outputs")) {
      verify(output);
    }
    v20::body::require(count == 12 && epochs == std::set<unsigned> {1, 2, 3} && exact_words == 253440, "CP23 frozen refresh counts");
    return {{"scope", "static_independent_key_full_legacy_hud_software_reconstruction"}, {"vectors", count}, {"distinct_epoch_variants", epochs.size()}, {"width", 720}, {"height", 480}, {"exact_hud_words_checked", exact_words}, {"joint_acks_constructed", count}, {"full_display_hashes_matched", count}, {"moving_content", false}, {"stateful_hud_supported", false}, {"hardware_playback", false}, {"performance_measured", false}};
  }
}  // namespace gamebub::v24::composed_case
