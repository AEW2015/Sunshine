/**
 * @file tests/unit/test_gamebub_v20.cpp
 * @brief Offline inverse, endian and envelope regression checks for the v20 port.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <algorithm>
#include <cmath>
#include <limits>
#include <random>
#include <vector>

// local includes
#include "tools/gamebub/native/v20.h"

namespace {
  /** @brief Store a little-endian test word without native-layout casts. */
  void put32(std::vector<std::uint8_t> &bytes, std::size_t offset, std::uint32_t word) {
    for (unsigned i = 0; i < 4; ++i) {
      bytes[offset + i] = static_cast<std::uint8_t>(word >> (8 * i));
    }
  }

  /** @brief Recompute only an envelope's trailer for structural-negative tests. */
  void seal(std::vector<std::uint8_t> &bytes) {
    put32(bytes, bytes.size() - 4, gamebub::v20::crc32(std::span(bytes).first(bytes.size() - 4)));
  }

  /** @brief Produce synthetic outer framing; no entropy/body-validity claim. */
  std::vector<std::uint8_t> packet(bool ack = false, std::size_t inner = 1) {
    std::vector<std::uint8_t> bytes(ack ? 43 : 65 + inner);
    const std::string_view magic = ack ? "AF03" : "AR03";
    std::copy(magic.begin(), magic.end(), bytes.begin());
    bytes[4] = 3;
    bytes[5] = 1;
    if (!ack) {
      put32(bytes, 52, inner);
    }
    seal(bytes);
    return bytes;
  }
}  // namespace

TEST(GamebubV20, InverseDomainRoundingBypassAndAliasing) {
  using namespace gamebub::v20;
  EXPECT_EQ(round_q14(8191), 0);
  EXPECT_EQ(round_q14(8192), 1);
  EXPECT_EQ(round_q14(-8192), 0);
  EXPECT_EQ(round_q14(-8193), -1);
  block_t input {}, output {};
  output.fill(123);
  EXPECT_TRUE(inverse(input, output));
  EXPECT_EQ(output, block_t {});
  input[0] = -8193;
  EXPECT_TRUE(inverse(input, input));
  EXPECT_TRUE(std::all_of(input.begin(), input.end(), [](auto x) {
    return x == -1024;
  }));
  for (auto invalid : {std::numeric_limits<std::int32_t>::min(), -522241, 522241, std::numeric_limits<std::int32_t>::max()}) {
    input.fill(0);
    input[63] = invalid;
    output.fill(321);
    const auto before = output;
    EXPECT_FALSE(inverse(input, output));
    EXPECT_EQ(output, before);
  }
}

TEST(GamebubV20, SparseAndDenseInverseMatchIndependentDenseSum) {
  using namespace gamebub::v20;
  std::mt19937 random(20261104);
  std::uniform_int_distribution<std::int32_t> coefficient(-522240, 522240);
  for (unsigned sample = 0; sample < 256; ++sample) {
    block_t input {}, middle {}, expected {}, actual {};
    for (unsigned i = 0; i < 64; ++i) {
      input[i] = i % (sample % 16 + 1) == 0 ? coefficient(random) : 0;
    }
    for (unsigned row = 0; row < 8; ++row) {
      for (unsigned col = 0; col < 8; ++col) {
        std::int64_t sum = 0;
        for (unsigned k = 0; k < 8; ++k) {
          sum += static_cast<std::int64_t>(input[row * 8 + k]) * basis[k][col];
        }
        middle[row * 8 + col] = static_cast<std::int32_t>(std::floor((sum + 8192) / 16384.0));
      }
    }
    for (unsigned row = 0; row < 8; ++row) {
      for (unsigned col = 0; col < 8; ++col) {
        std::int64_t sum = 0;
        for (unsigned k = 0; k < 8; ++k) {
          sum += static_cast<std::int64_t>(middle[k * 8 + col]) * basis[k][row];
        }
        expected[row * 8 + col] = static_cast<std::int32_t>(std::floor((sum + 8192) / 16384.0));
      }
    }
    ASSERT_TRUE(inverse(input, actual));
    EXPECT_EQ(actual, expected);
    auto alias = input;
    ASSERT_TRUE(inverse(alias, alias));
    EXPECT_EQ(alias, expected);
  }
}

TEST(GamebubV20, EndianAndIeeeCrcMatchStandardCheckValue) {
  using namespace gamebub::v20;
  const std::array<std::uint8_t, 5> word {0, 0x78, 0x56, 0x34, 0x12};
  EXPECT_EQ(le32(word, 1), 0x12345678U);
  const std::array<std::uint8_t, 9> check {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
  EXPECT_EQ(crc32(check), 0xcbf43926U);
  EXPECT_EQ(crc32({}), 0U);
}

TEST(GamebubV20, EnvelopesRejectMalformedHeaderFlagsSizesLengthsAndCrc) {
  using namespace gamebub::v20;
  for (bool ack : {false, true}) {
    const auto valid = packet(ack);
    EXPECT_TRUE(envelope(valid, ack).empty());
    for (unsigned i = 0; i < 4; ++i) {
      auto bad = valid;
      bad[i] ^= 1;
      EXPECT_EQ(envelope(bad, ack), "magic");
    }
    auto bad = valid;
    bad[4] = 1;
    EXPECT_EQ(envelope(bad, ack), "version");
    bad = valid;
    bad[5] = 4;
    EXPECT_EQ(envelope(bad, ack), "flags");
    bad = valid;
    bad.back() ^= 1;
    EXPECT_EQ(envelope(bad, ack), "crc");
    EXPECT_EQ(envelope({}, ack), "size");
    bad = valid;
    bad.pop_back();
    EXPECT_FALSE(envelope(bad, ack).empty());
    bad = valid;
    bad.push_back(0);
    EXPECT_FALSE(envelope(bad, ack).empty());
    for (unsigned flags = ack ? 1 : 0; flags <= (ack ? 2U : 3U); ++flags) {
      bad = valid;
      bad[5] = flags;
      seal(bad);
      EXPECT_TRUE(envelope(bad, ack).empty());
    }
  }
  auto bad = packet(true);
  bad[5] = 0;
  EXPECT_EQ(envelope(bad, true), "flags");
  bad = packet();
  put32(bad, 52, 0xffffffffU);
  put32(bad, 57, 0xffffffffU);
  EXPECT_EQ(envelope(bad, false), "length");
  EXPECT_TRUE(envelope(packet(false, 49152 - 65), false).empty());
  EXPECT_EQ(envelope(packet(false, 49153 - 65), false), "size");
  EXPECT_TRUE(envelope(packet(false, 0), false).empty());
}
