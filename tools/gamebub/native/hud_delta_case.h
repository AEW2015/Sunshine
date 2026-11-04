/**
 * @file tools/gamebub/native/hud_delta_case.h
 * @brief Replay retained HD22 HUD words without a receiver, publisher or transport.
 */
#pragma once

// local includes
#include "body_case.h"
#include "hud_delta.h"

namespace gamebub::v24::hud_delta_case {
  /** @brief Load one hash-bound raw object named by the pinned source manifest. */
  inline std::vector<std::uint8_t> object(const std::filesystem::path &root, const v20::body_case::Json &descriptor, std::size_t limit) {
    const auto size = v20::body_case::number(descriptor.at("raw_bytes"), limit);
    const auto hash = descriptor.at("raw_sha256").get<std::string>();
    v20::body::require(hash.size() == 64 && hash.find_first_not_of("0123456789abcdef") == std::string::npos, "HD22 source object hash");
    return v20::body_case::blob(root, {{"bytes", size}, {"sha256", hash}, {"path", "objects/" + hash + ".bin"}}, size);
  }

  /** @brief Convert an exact little-endian frozen word array into owned patch storage. */
  inline hud_delta::Patch patch(const std::filesystem::path &root, const v20::body_case::Json &descriptor, unsigned width, unsigned height) {
    const auto raw = object(root, descriptor, 42240);
    v20::body::require(raw.size() == 2 * width * height, "HD22 reference word count");
    hud_delta::Patch value {width, height, {}};
    for (std::size_t i = 0; i < raw.size(); i += 2) {
      value.words.push_back(v20::body::u16(raw, i));
    }
    return value;
  }

  /**
   * @brief Compare every decoded word and exact tag in the seven retained source goldens.
   * @param root Export directory produced by prepare_hd22_fixtures.py.
   * @return Software conformance counts, without HC22/CP23 state or hardware claims.
   */
  inline v20::body_case::Json run(const std::filesystem::path &root) {
    const auto raw = v20::body_case::read_file(root / "source_results.json", 512 * 1024);
    v20::body::require(v20::body_case::digest(raw) == "2657a35912ca2b33b68f6ea75e705c0b2a88c8c5a8d4067fb8f85faecbe84971", "pinned HD22 results hash");
    const auto document = v20::body_case::Json::parse(raw);
    const auto &goldens = document.at("goldens");
    v20::body::require(goldens.is_array() && goldens.size() == 7, "HD22 golden count");
    unsigned words = 0, raws = 0, spans = 0;
    for (const auto &golden : goldens) {
      const auto height = v20::body_case::number(golden.at("shape").at(0), 480), width = v20::body_case::number(golden.at("shape").at(1), 720);
      v20::body::require(width && height && width * height <= 21120, "HD22 golden geometry");
      const auto expected = patch(root, golden.at("current"), width, height);
      std::optional<hud_delta::Patch> reference;
      if (!golden.at("reference").is_null()) {
        reference = patch(root, golden.at("reference"), width, height);
      }
      const auto saved = reference;
      const auto packet = object(root, golden.at("packet"), hud_delta::max_packet);
      const auto decoded = hud_delta::decode(packet, reference ? &*reference : nullptr);
      v20::body::require(decoded == expected && reference == saved, "HD22 decoded words or immutable reference");
      v20::body::require(hud_delta::tag(decoded) == v20::body_case::tag(golden.at("meta").at("current_tag")), "HD22 frozen reconstruction tag");
      raws += packet[5] == 0;
      spans += packet[5] == 2;
      words += decoded.words.size();
    }
    v20::body::require(raws == 5 && spans == 2 && words == 26880, "HD22 frozen modes/words");
    return {{"scope", "pinned_hd22_patch_words_only"}, {"vectors", 7}, {"raw_vectors", raws}, {"span_vectors", spans}, {"verified_words", words}, {"copy_golden_available", false}, {"stateful_hc22_verified", false}, {"hardware_playback", false}, {"performance_measured", false}};
  }
}  // namespace gamebub::v24::hud_delta_case
