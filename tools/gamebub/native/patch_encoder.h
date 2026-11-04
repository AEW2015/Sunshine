/**
 * @file tools/gamebub/native/patch_encoder.h
 * @brief Exact, bounded HP01/HR01 HUD encoding from immutable RGB565 words.
 * @note Every call pays the complete search and decoder validation. There is no
 * persistent cache, historical work reuse, Python runtime or reference mutation.
 */
#pragma once

// standard includes
#include <algorithm>
#include <span>
#include <vector>

// local includes
#include "candidate.h"

namespace gamebub::v20::encoder {
  namespace patch_detail {
    /** @brief Append an unsigned little-endian word. */
    inline void word(std::vector<std::uint8_t> &out, unsigned value) {
      out.push_back(static_cast<std::uint8_t>(value));
      out.push_back(static_cast<std::uint8_t>(value >> 8));
    }

    /** @brief Frame one fully built patch candidate with its common header and CRC. */
    inline std::vector<std::uint8_t> frame(bool row, unsigned mode, candidate::Rect rect, std::span<const std::uint16_t> palette, std::span<const std::uint8_t> payload) {
      std::vector<std::uint8_t> out {'H', static_cast<std::uint8_t>(row ? 'R' : 'P'), '0', '1', 1, static_cast<std::uint8_t>(mode)};
      for (auto value : {rect.x, rect.y, rect.width, rect.height, static_cast<unsigned>(palette.size())}) {
        word(out, value);
      }
      out.resize(24);
      body::put32(out, 16, rect.width * rect.height);
      body::put32(out, 20, static_cast<std::uint32_t>(payload.size()));
      for (auto value : palette) {
        word(out, value);
      }
      out.insert(out.end(), payload.begin(), payload.end());
      const auto crc = crc32(out);
      out.resize(out.size() + 4);
      body::put32(out, out.size() - 4, crc);
      return out;
    }

    /** @brief Greedy frozen row tokens: runs of at least three, literals up to128. */
    inline std::vector<std::uint8_t> tokens(std::span<const std::uint16_t> values, unsigned unit) {
      std::vector<std::uint8_t> out;
      const auto run_at = [&](std::size_t at) {
        std::size_t end = at + 1;
        while (end < values.size() && end - at < 128 && values[end] == values[at]) {
          ++end;
        }
        return end - at;
      };
      const auto symbol = [&](std::uint16_t value) {
        out.push_back(static_cast<std::uint8_t>(value));
        if (unit == 2) {
          out.push_back(static_cast<std::uint8_t>(value >> 8));
        }
      };
      std::size_t at = 0;
      while (at < values.size()) {
        auto count = run_at(at);
        if (count >= 3) {
          out.push_back(static_cast<std::uint8_t>(128 | (count - 1)));
          symbol(values[at]);
          at += count;
        } else {
          const auto begin = at;
          at += count;
          while (at < values.size() && at - begin < 128) {
            count = run_at(at);
            if (count >= 3) {
              break;
            }
            at += std::min(count, 128 - (at - begin));
          }
          out.push_back(static_cast<std::uint8_t>(at - begin - 1));
          for (auto value : values.subspan(begin, at - begin)) {
            symbol(value);
          }
        }
      }
      return out;
    }

    /** @brief Encode independent length-prefixed rows without crossing row boundaries. */
    inline std::vector<std::uint8_t> rows(std::span<const std::uint16_t> values, candidate::Rect rect, unsigned unit) {
      std::vector<std::uint8_t> out;
      for (unsigned y = 0; y < rect.height; ++y) {
        const auto row = tokens(values.subspan(std::size_t(y) * rect.width, rect.width), unit);
        word(out, static_cast<unsigned>(row.size()));
        out.insert(out.end(), row.begin(), row.end());
      }
      return out;
    }
  }  // namespace patch_detail

  /**
   * @brief Select exact frozen HP01/HR01 bytes from one contiguous rectangle.
   * @param words Original row-major RGB565 rectangle, with no canvas stride.
   * @param rect Rectangle position and extent on the source canvas.
   * @param canvas_width Bounded decoder canvas width.
   * @param canvas_height Bounded decoder canvas height.
   * @return Validated packet; HR01 ties choose lower mode, format ties choose HP01.
   * @throws std::invalid_argument Invalid source/canvas geometry or failed validation.
   */
  inline std::vector<std::uint8_t> encode_patch(std::span<const std::uint16_t> words, candidate::Rect rect, unsigned canvas_width = candidate::width, unsigned canvas_height = candidate::height) {
    body::geometry(canvas_width, canvas_height);
    body::require(rect.width && rect.height && rect.x < canvas_width && rect.y < canvas_height && rect.width <= canvas_width - rect.x && rect.height <= canvas_height - rect.y && words.size() == std::size_t(rect.width) * rect.height, "patch encoder geometry");
    std::vector<std::uint16_t> palette(words.begin(), words.end());
    std::sort(palette.begin(), palette.end());
    palette.erase(std::unique(palette.begin(), palette.end()), palette.end());
    std::vector<std::uint8_t> raw;
    raw.reserve(words.size() * 2);
    for (auto value : words) {
      patch_detail::word(raw, value);
    }
    auto hp = patch_detail::frame(false, 0, rect, {}, raw);
    auto hr = patch_detail::frame(true, 0, rect, {}, raw);
    auto word_runs = patch_detail::frame(true, 1, rect, {}, patch_detail::rows(words, rect, 2));
    if (word_runs.size() < hr.size()) {
      hr = std::move(word_runs);
    }
    if (palette.size() <= 256) {
      std::vector<std::uint16_t> indices;
      indices.reserve(words.size());
      for (auto value : words) {
        indices.push_back(static_cast<std::uint16_t>(std::lower_bound(palette.begin(), palette.end(), value) - palette.begin()));
      }
      const unsigned mode = palette.size() <= 2 ? 1 : palette.size() <= 4 ? 2 :
                                                    palette.size() <= 16  ? 4 :
                                                                            8;
      std::vector<std::uint8_t> packed((words.size() * mode + 7) / 8);
      for (std::size_t i = 0; i < indices.size(); ++i) {
        const auto bit = i * mode;
        packed[bit / 8] |= static_cast<std::uint8_t>(indices[i] << (8 - mode - bit % 8));
      }
      hp = patch_detail::frame(false, mode, rect, palette, packed);
      auto index_runs = patch_detail::frame(true, 2, rect, palette, patch_detail::rows(indices, rect, 1));
      if (index_runs.size() < hr.size()) {
        hr = std::move(index_runs);
      }
    }
    auto chosen = hr.size() < hp.size() ? std::move(hr) : std::move(hp);
    const auto decoded = body::decode_patch(chosen, canvas_width, canvas_height);
    body::require(decoded.x == rect.x && decoded.y == rect.y && decoded.width == rect.width && decoded.height == rect.height && std::equal(words.begin(), words.end(), decoded.words.begin(), decoded.words.end()), "patch encoder round trip");
    return chosen;
  }

  /**
   * @brief Encode all four mandatory rectangles in frozen priority order.
   * @param source Immutable full-canvas RGB565 snapshot, never altered by encoding.
   * @return Four complete validated packets without AR03 length prefixes.
   */
  inline std::vector<std::vector<std::uint8_t>> encode_patches(const candidate::Source &source) {
    std::vector<std::vector<std::uint8_t>> packets;
    packets.reserve(candidate::rectangles.size());
    for (const auto rect : candidate::rectangles) {
      std::vector<std::uint16_t> words;
      words.reserve(std::size_t(rect.width) * rect.height);
      for (unsigned y = 0; y < rect.height; ++y) {
        const auto row = source.words().subspan(std::size_t(rect.y + y) * candidate::width + rect.x, rect.width);
        words.insert(words.end(), row.begin(), row.end());
      }
      packets.push_back(encode_patch(words, rect));
    }
    return packets;
  }
}  // namespace gamebub::v20::encoder
