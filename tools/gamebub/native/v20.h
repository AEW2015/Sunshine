/**
 * @file tools/gamebub/native/v20.h
 * @brief Offline v20 inverse arithmetic and envelope checks; no runtime endpoint.
 */
#pragma once

// standard includes
#include <array>
#include <cstdint>
#include <span>
#include <string_view>

namespace gamebub::v20 {
  /** @brief One row-major signed dequantized or residual block. */
  using block_t = std::array<std::int32_t, 64>;

  /** @brief Frozen Q14 inverse basis from MoonBub v20 commit27a4dde. */
  inline constexpr std::int32_t basis[8][8] = {
    {5793, 5793, 5793, 5793, 5793, 5793, 5793, 5793},
    {8035, 6811, 4551, 1598, -1598, -4551, -6811, -8035},
    {7568, 3135, -3135, -7568, -7568, -3135, 3135, 7568},
    {6811, -1598, -8035, -4551, 4551, 8035, 1598, -6811},
    {5793, -5793, -5793, 5793, 5793, -5793, -5793, 5793},
    {4551, -8035, 1598, 6811, -6811, -1598, 8035, -4551},
    {3135, -7568, 7568, -3135, -3135, 7568, -7568, 3135},
    {1598, -4551, 6811, -8035, 8035, -6811, 4551, -1598}
  };

  /**
   * @brief Compute floor((value+8192)/16384) for bounded inverse accumulators.
   * @param value Legal inverse sum, whose biased magnitude fits signed64.
   * @return Signed rounded value; negative rounding does not rely on signed shifts.
   */
  inline std::int32_t round_q14(std::int64_t value) {
    const auto biased = value + 8192;
    return static_cast<std::int32_t>(biased >= 0 ? biased / 16384 : -((-biased + 16383) / 16384));
  }

  /**
   * @brief Invert one legal block with exact sparse two-pass rounding and ZERO/DC bypass.
   * @param input Dequantized values within [-522240,522240]; may alias output.
   * @param output Residual block; unchanged on invalid input.
   * @return True after atomic output assignment, false for out-of-domain input.
   */
  inline bool inverse(const block_t &input, block_t &output) {
    bool ac = false;
    for (unsigned i = 0; i < 64; ++i) {
      if (input[i] < -522240 || input[i] > 522240) {
        return false;
      }
      ac = ac || (i != 0 && input[i] != 0);
    }
    block_t result {};
    if (!ac) {
      result.fill(input[0] == 0 ? 0 : round_q14(static_cast<std::int64_t>(round_q14(static_cast<std::int64_t>(input[0]) * 5793)) * 5793));
    } else {
      block_t middle {};
      for (unsigned row = 0; row < 8; ++row) {
        std::array<std::int64_t, 8> sums {};
        for (unsigned k = 0; k < 8; ++k) {
          if (input[row * 8 + k] != 0) {
            for (unsigned col = 0; col < 8; ++col) {
              sums[col] += static_cast<std::int64_t>(input[row * 8 + k]) * basis[k][col];
            }
          }
        }
        for (unsigned col = 0; col < 8; ++col) {
          middle[row * 8 + col] = round_q14(sums[col]);
        }
      }
      for (unsigned col = 0; col < 8; ++col) {
        std::array<std::int64_t, 8> sums {};
        for (unsigned k = 0; k < 8; ++k) {
          if (middle[k * 8 + col] != 0) {
            for (unsigned row = 0; row < 8; ++row) {
              sums[row] += static_cast<std::int64_t>(middle[k * 8 + col]) * basis[k][row];
            }
          }
        }
        for (unsigned row = 0; row < 8; ++row) {
          result[row * 8 + col] = round_q14(sums[row]);
        }
      }
    }
    output = result;
    return true;
  }

  /**
   * @brief Read a little-endian word after the caller has checked available bytes.
   * @param bytes Span containing at least offset+4 bytes.
   * @param offset Word start.
   * @return Unsigned32 value without alignment or native-endian assumptions.
   */
  inline std::uint32_t le32(std::span<const std::uint8_t> bytes, std::size_t offset) {
    return static_cast<std::uint32_t>(bytes[offset]) |
           (static_cast<std::uint32_t>(bytes[offset + 1]) << 8) |
           (static_cast<std::uint32_t>(bytes[offset + 2]) << 16) |
           (static_cast<std::uint32_t>(bytes[offset + 3]) << 24);
  }

  /**
   * @brief Calculate IEEE CRC32, matching Python zlib.crc32.
   * @param bytes Exact message prefix excluding its stored trailer.
   * @return Final unsigned CRC32.
   */
  inline std::uint32_t crc32(std::span<const std::uint8_t> bytes) {
    std::uint32_t value = 0xffffffffU;
    for (auto byte : bytes) {
      value ^= byte;
      for (unsigned bit = 0; bit < 8; ++bit) {
        value = (value >> 1) ^ ((value & 1) ? 0xedb88320U : 0);
      }
    }
    return value ^ 0xffffffffU;
  }

  /**
   * @brief Check bounded outer AR03/AF03 framing, version, flags and trailer CRC only.
   * @param bytes Complete packet bytes.
   * @param ack Select fixed AF03 feedback instead of variable AR03 body.
   * @return Empty view on envelope success, otherwise a stable rejection reason.
   * @note Success does not validate entropy, HUD coverage, bank/tag state or publication.
   */
  inline std::string_view envelope(std::span<const std::uint8_t> bytes, bool ack) {
    if ((ack && bytes.size() != 43) || (!ack && (bytes.size() < 65 || bytes.size() > 49152))) {
      return "size";
    }
    const auto magic = ack ? std::string_view("AF03") : std::string_view("AR03");
    for (unsigned i = 0; i < 4; ++i) {
      if (bytes[i] != static_cast<std::uint8_t>(magic[i])) {
        return "magic";
      }
    }
    if (bytes[4] != 3) {
      return "version";
    }
    if ((ack && bytes[5] != 1 && bytes[5] != 2) || (!ack && (bytes[5] & ~3U))) {
      return "flags";
    }
    if (!ack) {
      const std::uint64_t declared = 65ULL + le32(bytes, 52) + le32(bytes, 57);
      if (declared != bytes.size()) {
        return "length";
      }
    }
    if (crc32(bytes.first(bytes.size() - 4)) != le32(bytes, bytes.size() - 4)) {
      return "crc";
    }
    return {};
  }
}  // namespace gamebub::v20
