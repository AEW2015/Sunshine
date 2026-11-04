/**
 * @file tests/unit/test_gamebub_v20_crc.cpp
 * @brief IEEE checksum conformance across binary values, alignments and packet boundaries.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <random>
#include <span>
#include <vector>

// local includes
#include "tools/gamebub/native/v20.h"

namespace {
  /** @brief Independent bit-at-a-time reference for the reflected IEEE polynomial. */
  std::uint32_t scalar_crc(std::span<const std::uint8_t> bytes) {
    std::uint32_t result = 0xffffffffU;
    for (auto byte : bytes) {
      result ^= byte;
      for (unsigned bit = 0; bit < 8; ++bit) {
        result = (result >> 1) ^ ((result & 1U) ? 0xedb88320U : 0);
      }
    }
    return result ^ 0xffffffffU;
  }
}  // namespace

TEST(GamebubV20Crc, MatchesPublishedCheckValueAndEmptyMessage) {
  const std::array<std::uint8_t, 9> digits {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
  EXPECT_EQ(gamebub::v20::crc32(digits), 0xcbf43926U);
  EXPECT_EQ(gamebub::v20::crc32({}), 0U);
}

TEST(GamebubV20Crc, MatchesScalarForEveryByteAndUnalignedPacketBoundaries) {
  std::array<std::uint8_t, 256> values {};
  for (unsigned i = 0; i < values.size(); ++i) {
    values[i] = static_cast<std::uint8_t>(i);
    EXPECT_EQ(gamebub::v20::crc32(std::span(values).subspan(i, 1)), scalar_crc(std::span(values).subspan(i, 1)));
  }
  EXPECT_EQ(gamebub::v20::crc32(values), scalar_crc(values));
  std::mt19937 random(0xb0b2026);
  std::vector<std::uint8_t> bytes(49152 + 17);
  for (auto &byte : bytes) {
    byte = static_cast<std::uint8_t>(random());
  }
  for (unsigned offset : {0U, 1U, 15U, 17U}) {
    for (unsigned length : {0U, 1U, 2U, 3U, 4U, 7U, 8U, 15U, 16U, 31U, 256U, 1024U, 49152U}) {
      const auto view = std::span(bytes).subspan(offset, length);
      EXPECT_EQ(gamebub::v20::crc32(view), scalar_crc(view)) << offset << ":" << length;
    }
  }
}
