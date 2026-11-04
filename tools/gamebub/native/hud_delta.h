/**
 * @file tools/gamebub/native/hud_delta.h
 * @brief Bounded offline HD22 RGB565 reconstruction from MoonBub4025d355.
 * @note This decoder owns private output only; it does not acknowledge, publish or transport HUD banks.
 */
#pragma once

// standard includes
#include <array>
#include <cstdint>
#include <span>
#include <vector>

// local includes
#include "body_decoder.h"

namespace gamebub::v24::hud_delta {
  using Tag = v20::body::Tag;  ///< First16 bytes of the canonical SHA256 patch identity.
  inline constexpr unsigned max_words = 21120;  ///< Complete bounded HUD-word allocation.
  inline constexpr unsigned fixed_bytes = 50;  ///< HD22 header plus final CRC.
  inline constexpr unsigned max_packet = fixed_bytes + 2 * max_words;  ///< Maximum complete packet.

  /** @brief Caller-owned exact row-major RGB565 patch; no alias to a receiver bank. */
  struct Patch {
    unsigned width {}, height {};  ///< Independent bounded dimensions, including odd sizes.
    std::vector<std::uint16_t> words;  ///< Exactly width times height decoded words.
    /** @brief Compare dimensions and every reconstructed word. */
    bool operator==(const Patch &) const = default;
  };

  /**
   * @brief Check HD22 geometry without imposing the base codec's even-dimension restriction.
   * @param width Patch width, in the range1..720.
   * @param height Patch height, in the range1..480.
   */
  inline void geometry(unsigned width, unsigned height) {
    v20::body::require(width > 0 && width <= 720 && height > 0 && height <= 480 && std::uint64_t(width) * height <= max_words, "HD22 bounded geometry");
  }

  /**
   * @brief Hash canonical little-endian width/height and RGB565 words.
   * @param patch Exact bounded patch storage.
   * @return Truncated SHA256 identity, never an authentication credential.
   */
  inline Tag tag(const Patch &patch) {
    geometry(patch.width, patch.height);
    v20::body::require(patch.words.size() == std::size_t(patch.width) * patch.height, "HD22 exact patch storage");
    std::vector<std::uint8_t> bytes;
    bytes.reserve(4 + 2 * patch.words.size());
    for (unsigned value : {patch.width, patch.height}) {
      bytes.push_back(static_cast<std::uint8_t>(value));
      bytes.push_back(static_cast<std::uint8_t>(value >> 8));
    }
    for (auto value : patch.words) {
      bytes.push_back(static_cast<std::uint8_t>(value));
      bytes.push_back(static_cast<std::uint8_t>(value >> 8));
    }
    std::array<unsigned char, SHA256_DIGEST_LENGTH> digest {};
    v20::body::require(SHA256(bytes.data(), bytes.size(), digest.data()) != nullptr, "HD22 SHA256");
    Tag result;
    std::copy_n(digest.begin(), result.size(), result.begin());
    return result;
  }

  /**
   * @brief Decode exact HD22 RAW, COPY or canonical SPAN_XOR into private owned words.
   * @param packet Entire HD22 packet, including CRC and both content identities.
   * @param reference Optional immutable acknowledged patch; required for COPY and SPAN_XOR.
   * @return Fully tag-checked output; malformed input throws without mutating the reference.
   */
  inline Patch decode(std::span<const std::uint8_t> packet, const Patch *reference = nullptr) {
    using namespace v20::body;
    require(packet.size() >= fixed_bytes && packet.size() <= max_packet, "HD22 bounded packet");
    const auto width = u16(packet, 6), height = u16(packet, 8);
    geometry(width, height);
    const auto mode = packet[5];
    require(magic(packet, "HD22") && packet[4] == 1 && mode <= 2, "HD22 version/mode");
    const auto size = u32(packet, 10);
    require(size <= 2 * max_words && fixed_bytes + std::uint64_t(size) == packet.size(), "HD22 exact payload");
    check_crc(packet);
    const auto reference_tag = tag_at(packet, 14), current_tag = tag_at(packet, 30);
    const auto payload = packet.subspan(46, size);

    /** @brief Validated span descriptors retaining offsets, never pointers into mutable banks. */
    struct Span {
      unsigned y, x, words;  ///< Bounded row-local destination extent.
      std::size_t offset;  ///< First XOR word in the immutable payload.
    };

    std::vector<Span> spans;
    if (mode == 0) {
      require(size == 2U * width * height && reference_tag == Tag {}, "HD22 RAW framing");
    } else if (mode == 1) {
      require(size == 0, "HD22 COPY payload");
    } else {
      require(size >= 2, "HD22 missing span count");
      const unsigned count = u16(payload, 0);
      require(count > 0 && count <= unsigned(width) * height && count <= (size - 2) / 8, "HD22 bounded span count");
      spans.reserve(count);
      std::size_t position = 2;
      int last_y = -1;
      unsigned last_end = 0;
      for (unsigned i = 0; i < count; ++i) {
        require(position <= size && size - position >= 6, "HD22 truncated span");
        const unsigned y = u16(payload, position), x = u16(payload, position + 2), words = u16(payload, position + 4);
        position += 6;
        require(y < height && words > 0 && words <= width && x + words <= width && int(y) >= last_y && (int(y) != last_y || x >= last_end + 3), "HD22 span geometry/order/gap");
        require(position <= size && 2ULL * words <= size - position, "HD22 truncated XOR words");
        require(u16(payload, position) != 0 && u16(payload, position + 2 * (words - 1)) != 0, "HD22 zero span endpoint");
        unsigned zeros = 0;
        for (unsigned at = 0; at < words; ++at) {
          if (u16(payload, position + 2 * at) == 0) {
            ++zeros;
          } else {
            require(zeros < 3, "HD22 noncanonical internal gap");
            zeros = 0;
          }
        }
        spans.push_back({y, x, words, position});
        position += 2 * words;
        last_y = static_cast<int>(y);
        last_end = x + words;
      }
      require(position == size, "HD22 trailing span bytes");
    }
    Patch result {width, height, {}};
    if (mode == 0) {
      result.words.resize(std::size_t(width) * height);
      for (std::size_t i = 0; i < result.words.size(); ++i) {
        result.words[i] = u16(payload, 2 * i);
      }
    } else {
      require(reference != nullptr, "HD22 missing acknowledged reference");
      require(reference->width == width && reference->height == height && tag(*reference) == reference_tag, "HD22 wrong exact reference");
      result.words = reference->words;
      for (const auto span : spans) {
        for (unsigned at = 0; at < span.words; ++at) {
          result.words[span.y * width + span.x + at] ^= u16(payload, span.offset + 2 * at);
        }
      }
    }
    require(tag(result) == current_tag, "HD22 reconstruction tag");
    return result;
  }
}  // namespace gamebub::v24::hud_delta
