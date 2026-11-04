/**
 * @file tools/gamebub/native/composed_refresh.h
 * @brief Offline independent-key/full-LEGACY-HUD reconstruction, without live publication.
 */
#pragma once

// local includes
#include "candidate.h"
#include "composed_wire.h"

namespace gamebub::v24::refresh {
  /** @brief Complete private software reconstruction of the supported refresh subset. */
  struct Decoded {
    v20::body::Frame frame;  ///< Base planes and RGB565 with all four exact HUD overlays.
    std::array<std::uint8_t, 134> ack {};  ///< Complete constructed JA23 response, never sent here.
  };

  /**
   * @brief Compute the profile's truncated SHA256 identity over exact component bytes.
   * @param bytes Bounded validated bytes owned by this offline transaction.
   * @return First16 SHA256 bytes, without native endian assumptions.
   */
  inline v20::body::Tag sha16(std::span<const std::uint8_t> bytes) {
    std::array<unsigned char, SHA256_DIGEST_LENGTH> digest {};
    v20::body::require(SHA256(bytes.data(), bytes.size(), digest.data()) != nullptr, "CP23 SHA256 unavailable");
    v20::body::Tag tag;
    std::copy_n(digest.begin(), tag.size(), tag.begin());
    return tag;
  }

  /**
   * @brief Reconstruct one independent AR03 key with nonreferenced LEGACY HUD patches.
   * @param packet Complete CP23 packet; P frames and HD22 dispatch are deliberately rejected.
   * @return Fully checked private image and joint ACK; caller state is never mutated.
   * @note This is a strict subset, not a stateful HC22/HD22 receiver or hardware implementation.
   */
  inline Decoded decode_legacy_refresh(std::span<const std::uint8_t> packet) {
    const auto pair = composed::parse_pair(packet);
    const auto &hud = pair.hud;
    v20::body::require(pair.base[5] == 1 && hud[18] == 255, "CP23 independent refresh required");
    v20::body::require(std::all_of(hud.begin() + 75, hud.begin() + 79, [](auto mode) {
                         return mode == 0;
                       }),
                       "CP23 refresh supports LEGACY HUD only");
    v20::body::State state;
    state.epoch = pair.epoch;
    Decoded output;
    std::string error;
    if (!v20::body::decode(pair.base, state, output.frame, error)) {
      throw std::invalid_argument("CP23 refresh base: " + error);
    }
    v20::body::require(output.frame.width == 720 && output.frame.height == 480, "CP23 refresh canvas");
    std::vector<std::uint8_t> canonical;
    canonical.reserve(42272);
    std::size_t position = 79;
    for (unsigned i = 0; i < v20::candidate::rectangles.size(); ++i) {
      const auto size = v20::body::u32(hud, 59 + 4 * i);
      const auto patch = v20::body::decode_patch(std::span(hud).subspan(position, size), 720, 480);
      position += size;
      const auto rectangle = v20::candidate::rectangles[i];
      v20::body::require(patch.x == rectangle.x && patch.y == rectangle.y && patch.width == rectangle.width && patch.height == rectangle.height, "HC22 exact mandatory rectangle");
      for (const auto value : {rectangle.x, rectangle.y, rectangle.width, rectangle.height}) {
        canonical.push_back(static_cast<std::uint8_t>(value));
        canonical.push_back(static_cast<std::uint8_t>(value >> 8));
      }
      for (const auto word : patch.words) {
        canonical.push_back(static_cast<std::uint8_t>(word));
        canonical.push_back(static_cast<std::uint8_t>(word >> 8));
      }
      for (unsigned row = 0; row < patch.height; ++row) {
        std::copy_n(patch.words.begin() + row * patch.width, patch.width, output.frame.display565.begin() + (patch.y + row) * 720 + patch.x);
      }
    }
    const auto hud_tag = sha16(canonical);
    v20::body::require(hud_tag == v20::body::tag_at(hud, 43), "HC22 reconstructed HUD tag");
    std::array<std::uint8_t, 54> hud_ack {};
    std::copy_n("HA22", 4, hud_ack.begin());
    hud_ack[4] = 1;
    v20::body::put32(hud_ack, 5, pair.epoch);
    v20::body::put32(hud_ack, 9, pair.frame);
    v20::body::put32(hud_ack, 13, v20::body::u32(hud, 13));
    hud_ack[17] = hud[17];
    const auto body_tag = sha16(hud);
    std::copy(body_tag.begin(), body_tag.end(), hud_ack.begin() + 18);
    std::copy(hud_tag.begin(), hud_tag.end(), hud_ack.begin() + 34);
    v20::body::put32(hud_ack, 50, v20::crc32(std::span(hud_ack).first(50)));
    output.ack = composed::serialize_ack({pair.epoch, pair.frame, sha16(packet), output.frame.feedback, hud_ack});
    return output;
  }

  /**
   * @brief Serialize a private refresh display to canonical little-endian RGB565 words.
   * @param decoded Complete fixed-canvas software result.
   * @return Exactly691200 bytes for hash comparison, never a capture or presentation record.
   */
  inline std::vector<std::uint8_t> display_le(const Decoded &decoded) {
    const auto &frame = decoded.frame;
    v20::body::require(frame.width == 720 && frame.height == 480 && frame.display565.size() == 720 * 480, "CP23 display geometry");
    std::vector<std::uint8_t> bytes;
    bytes.reserve(2 * frame.display565.size());
    for (auto word : frame.display565) {
      bytes.push_back(static_cast<std::uint8_t>(word));
      bytes.push_back(static_cast<std::uint8_t>(word >> 8));
    }
    return bytes;
  }
}  // namespace gamebub::v24::refresh
