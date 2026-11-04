/**
 * @file tests/unit/test_gamebub_composed_wire.cpp
 * @brief CP23/JA23 framing regressions, excluding entropy/pixel and publication claims.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

// local includes
#include "tools/gamebub/native/composed_wire.h"

namespace {
  namespace c = gamebub::v24::composed;
  namespace b = gamebub::v20::body;

  /** @brief Independent Python struct/zlib/hashlib oracle; payload entropy is intentionally opaque. */
  constexpr std::string_view pair_hex =
    "43503233010100000000000000c2000000570000004913017721f7a602334d8224557e2570668cb3216e4b2d171892dce15b8f1f1c"
    "4152303303010100000000000000ff00ffffffff0000000000000000000000000000000011111111111111111111111111111111810000000000000000"
    "474d303101010100000000000000ffffffff020002000000000001000100010000001a0000001a0000001a000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "d54e2c72aae5baba484332320101000000000000000100000000ffffffffffffffffff000000000000000000000000000000002222222222222222222222222222222201000000010000000100000001000000000000000102030442d22a71c15df817";

  /** @brief Independent matching JA23 oracle with nested AF03 and HA22 CRCs. */
  constexpr std::string_view ack_hex =
    "4a4132330101000000000000003ee5419e24fc829cae8bd62ecf0bdedc2b003600"
    "4146303303010100000000000000aae5baba000000000011111111111111111111111111111111cba7adc7"
    "484132320101000000000000000100000000668cb3216e4b2d171892dce15b8f1f1c22222222222222222222222222222222b88775030705ef2c";

  /** @brief Decode fixed lowercase oracle bytes independently of the production parser. */
  std::vector<std::uint8_t> unhex(std::string_view text) {
    std::vector<std::uint8_t> result;
    const auto digit = [](char ch) {
      return ch <= '9' ? ch - '0' : ch - 'a' + 10;
    };
    for (std::size_t i = 0; i < text.size(); i += 2) {
      result.push_back(static_cast<std::uint8_t>((digit(text[i]) << 4) | digit(text[i + 1])));
    }
    return result;
  }

  /** @brief Recompute a trailer after a deliberate grammar mutation. */
  void seal(std::span<std::uint8_t> bytes) {
    b::put32(bytes, bytes.size() - 4, gamebub::v20::crc32(bytes.first(bytes.size() - 4)));
  }

  /** @brief Repair nested integrity without repairing deliberately invalid grammar. */
  void repair_pair(std::vector<std::uint8_t> &bytes, bool inner = false) {
    const auto nb = b::u32(bytes, 13), nh = b::u32(bytes, 17);
    auto base = std::span(bytes).subspan(53, nb);
    auto hud = std::span(bytes).subspan(53 + nb, nh);
    if (inner) {
      seal(base.subspan(61, b::u32(base, 52)));
    }
    seal(base);
    seal(hud);
    const auto base_tag = c::digest(base), hud_tag = c::digest(hud);
    std::copy(base_tag.begin(), base_tag.end(), bytes.begin() + 21);
    std::copy(hud_tag.begin(), hud_tag.end(), bytes.begin() + 37);
    seal(bytes);
  }

  /** @brief Repair fixed nested acknowledgement CRCs after grammar changes. */
  void repair_ack(std::vector<std::uint8_t> &bytes) {
    seal(std::span(bytes).subspan(33, 43));
    seal(std::span(bytes).subspan(76, 54));
    seal(bytes);
  }

  /** @brief Produce the valid reference-HUD/P-base syntax variant without decoding payloads. */
  std::vector<std::uint8_t> referenced_pair() {
    auto bytes = unhex(pair_hex);
    auto base = std::span(bytes).subspan(53, 194);
    auto hud = std::span(bytes).subspan(247, 87);
    b::put32(bytes, 9, 1);
    base[5] = 0;
    b::put32(base, 10, 1);
    base[14] = 0;
    base[15] = 255;
    b::put32(base, 16, 0);
    std::fill(base.begin() + 20, base.begin() + 36, 17);
    std::fill(base.begin() + 36, base.begin() + 52, 0);
    base[61 + 5] = 0;
    b::put32(base, 61 + 10, 1);
    b::put32(base, 61 + 14, 0);
    b::put32(hud, 9, 1);
    b::put32(hud, 13, 2);
    hud[17] = 1;
    hud[18] = 0;
    b::put32(hud, 19, 0);
    b::put32(hud, 23, 1);
    std::fill(hud.begin() + 27, hud.begin() + 43, 34);
    repair_pair(bytes, true);
    return bytes;
  }
}  // namespace

TEST(GamebubComposedWire, IndependentStructHashAndCrcOraclesRoundTripExactly) {
  const auto bytes = unhex(pair_hex), ack = unhex(ack_hex);
  ASSERT_EQ(bytes.size(), 338);
  ASSERT_EQ(ack.size(), c::ack_bytes);
  const auto pair = c::parse_pair(bytes);
  EXPECT_EQ(pair.epoch, 1);
  EXPECT_EQ(pair.frame, 0);
  EXPECT_EQ(pair.base.size(), 194);
  EXPECT_EQ(pair.hud.size(), 87);
  EXPECT_EQ(c::serialize_pair(pair), bytes);
  const auto base = c::base_identity(pair.base);
  EXPECT_TRUE(base.key);
  EXPECT_EQ(base.width, 2);
  EXPECT_EQ(base.height, 2);
  const auto hud = c::hud_identity(pair.hud);
  EXPECT_EQ(hud.reference, 255);
  EXPECT_EQ(hud.destination, 0);
  EXPECT_EQ(hud.sizes, (std::array<std::uint32_t, 4> {1, 1, 1, 1}));
  const auto response = c::parse_ack(ack);
  EXPECT_EQ(response.pair_digest, c::digest(bytes));
  const auto encoded = c::serialize_ack(response);
  EXPECT_TRUE(std::equal(encoded.begin(), encoded.end(), ack.begin(), ack.end()));
  EXPECT_EQ(c::parse_ack(encoded), response);
}

TEST(GamebubComposedWire, EveryTruncationTrailingByteAndSingleBitCorruptionRejects) {
  for (bool feedback : {false, true}) {
    const auto oracle = unhex(feedback ? ack_hex : pair_hex);
    const auto rejects = [&](std::span<const std::uint8_t> bytes) {
      if (feedback) {
        EXPECT_THROW(c::parse_ack(bytes), std::invalid_argument);
      } else {
        EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument);
      }
    };
    for (std::size_t size = 0; size < oracle.size(); ++size) {
      rejects(std::span(oracle).first(size));
    }
    auto extra = oracle;
    extra.push_back(0);
    rejects(extra);
    for (std::size_t at = 0; at < oracle.size(); ++at) {
      for (unsigned bit = 0; bit < 8; ++bit) {
        auto bytes = oracle;
        bytes[at] ^= static_cast<std::uint8_t>(1U << bit);
        rejects(bytes);
      }
    }
  }
}

TEST(GamebubComposedWire, ResealedOuterProfilesLengthsDigestsAndIdentitiesReject) {
  for (unsigned at = 0; at < 5; ++at) {
    auto bytes = unhex(pair_hex);
    bytes[at] ^= 1;
    seal(bytes);
    EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument);
  }
  for (unsigned offset : {13U, 17U}) {
    for (std::uint32_t size : {0U, 1U, 49153U, 0xffffffffU}) {
      auto bytes = unhex(pair_hex);
      b::put32(bytes, offset, size);
      seal(bytes);
      EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument);
    }
  }
  for (unsigned at : {5U, 9U, 21U, 37U}) {
    auto bytes = unhex(pair_hex);
    bytes[at] ^= 1;
    seal(bytes);
    EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument);
  }
  std::vector<std::uint8_t> oversized(c::frame_cap + 1);
  EXPECT_THROW(c::parse_pair(oversized), std::invalid_argument);
  auto pair = c::parse_pair(unhex(pair_hex));
  ++pair.epoch;
  EXPECT_THROW(c::serialize_pair(pair), std::invalid_argument);
  pair = c::parse_pair(unhex(pair_hex));
  pair.base.clear();
  EXPECT_THROW(c::serialize_pair(pair), std::invalid_argument);
  pair.base.resize(c::frame_cap + 1);
  EXPECT_THROW(c::serialize_pair(pair), std::invalid_argument);
  pair = c::parse_pair(unhex(pair_hex));
  pair.hud.resize(c::frame_cap + 1);
  EXPECT_THROW(c::serialize_pair(pair), std::invalid_argument);
}

TEST(GamebubComposedWire, HudGrammarRejectsResealedFullReferenceAndPatchErrors) {
  constexpr unsigned h = 247;
  for (unsigned scenario = 0; scenario < 16; ++scenario) {
    auto bytes = unhex(pair_hex);
    switch (scenario) {
      case 0:
        bytes[h] ^= 1;
        break;
      case 1:
        bytes[h + 4] = 2;
        break;
      case 2:
        b::put32(bytes, h + 5, 0);
        break;
      case 3:
        b::put32(bytes, h + 9, 0xffffffffU);
        break;
      case 4:
        b::put32(bytes, h + 13, 0xffffffffU);
        break;
      case 5:
        bytes[h + 17] = 2;
        break;
      case 6:
        bytes[h + 18] = 2;
        break;
      case 7:
        std::fill(bytes.begin() + h + 43, bytes.begin() + h + 59, 0);
        break;
      case 8:
        b::put32(bytes, h + 19, 0);
        break;
      case 9:
        b::put32(bytes, h + 23, 0);
        break;
      case 10:
        bytes[h + 27] = 1;
        break;
      case 11:
        bytes[h + 17] = 1;
        break;
      case 12:
        b::put32(bytes, h + 59, 0);
        break;
      case 13:
        b::put32(bytes, h + 59, 49153);
        break;
      case 14:
        bytes[h + 75] = 2;
        break;
      case 15:
        b::put32(bytes, h + 59, 2);
        break;
    }
    repair_pair(bytes);
    EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument) << scenario;
  }
  EXPECT_EQ(c::parse_pair(referenced_pair()).frame, 1);
  for (unsigned scenario = 0; scenario < 4; ++scenario) {
    auto bytes = referenced_pair();
    switch (scenario) {
      case 0:
        bytes[h + 17] = 0;
        break;
      case 1:
        b::put32(bytes, h + 19, 1);
        break;
      case 2:
        b::put32(bytes, h + 23, 2);
        break;
      case 3:
        std::fill(bytes.begin() + h + 27, bytes.begin() + h + 43, 0);
        break;
    }
    repair_pair(bytes);
    EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument);
  }
}

TEST(GamebubComposedWire, BaseIdentityAndInnerGeometryMapAndPlaneBoundsReject) {
  constexpr unsigned a = 53, i = a + 61;
  for (unsigned scenario = 0; scenario < 21; ++scenario) {
    auto bytes = unhex(pair_hex);
    switch (scenario) {
      case 0:
        bytes[a + 5] = 3;
        break;
      case 1:
        b::put32(bytes, a + 6, 0xffffffffU);
        break;
      case 2:
        b::put32(bytes, a + 10, 0xffffffffU);
        break;
      case 3:
        bytes[a + 56] = 1;
        break;
      case 4:
        bytes[a + 14] = 0;
        break;
      case 5:
        bytes[a + 15] = 1;
        break;
      case 6:
        b::put32(bytes, a + 16, 0);
        break;
      case 7:
        bytes[a + 20] = 1;
        break;
      case 8:
        std::fill(bytes.begin() + a + 36, bytes.begin() + a + 52, 0);
        break;
      case 9:
        bytes[i] = 'Z';
        break;
      case 10:
        bytes[i + 4] = 2;
        break;
      case 11:
        bytes[i + 5] = 2;
        break;
      case 12:
        b::put32(bytes, i + 6, 2);
        break;
      case 13:
        b::put32(bytes, i + 10, 1);
        break;
      case 14:
        b::put32(bytes, i + 14, 0);
        break;
      case 15:
        bytes[i + 22] = 1;
        break;
      case 16:
        bytes[i + 18] = 3;
        break;
      case 17:
        bytes[i + 26] = 0;
        break;
      case 18:
        bytes[i + 46] = 0xc0;
        break;
      case 19:
        bytes[i + 46] = 1;
        break;
      case 20:
        b::put32(bytes, i + 34, 25);
        b::put32(bytes, i + 38, 27);
        break;
    }
    repair_pair(bytes, true);
    EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument) << scenario;
  }
  auto promoted = referenced_pair();
  promoted[a + 5] = 2;
  promoted[a + 15] = 1;
  std::fill(promoted.begin() + a + 36, promoted.begin() + a + 52, 17);
  repair_pair(promoted, true);
  EXPECT_NO_THROW(c::parse_pair(promoted));
  for (unsigned flag : {0U, 2U, 4U}) {
    auto split = referenced_pair();
    split[i] = 'S';
    split[i + 1] = 'R';
    split[i + 5] = static_cast<std::uint8_t>(flag);
    repair_pair(split, true);
    EXPECT_NO_THROW(c::parse_pair(split));
  }
  auto split_key = unhex(pair_hex);
  split_key[i] = 'S';
  split_key[i + 1] = 'R';
  repair_pair(split_key, true);
  EXPECT_NO_THROW(c::parse_pair(split_key));
  split_key[i + 5] = 3;
  repair_pair(split_key, true);
  EXPECT_THROW(c::parse_pair(split_key), std::invalid_argument);
  auto base = c::parse_pair(unhex(pair_hex)).base;
  std::vector<std::uint8_t> inner(base.begin() + 61, base.end() - 4);
  inner.resize(258);
  b::put32(inner, 34, 155);
  seal(inner);
  base.resize(61 + inner.size() + 4);
  b::put32(base, 52, static_cast<std::uint32_t>(inner.size()));
  std::copy(inner.begin(), inner.end(), base.begin() + 61);
  seal(base);
  EXPECT_THROW(c::base_identity(base), std::invalid_argument);
}

TEST(GamebubComposedWire, ExactWholePairCapIncludesBothComponentsAndFraming) {
  auto pair = c::parse_pair(unhex(pair_hex));
  pair.hud.resize(c::frame_cap - c::pair_overhead - pair.base.size());
  b::put32(pair.hud, 59, static_cast<std::uint32_t>(pair.hud.size() - 86));
  seal(pair.hud);
  const auto bytes = c::serialize_pair(pair);
  EXPECT_EQ(bytes.size(), c::frame_cap);
  EXPECT_EQ(c::parse_pair(bytes), pair);
  pair.hud.push_back(0);
  EXPECT_THROW(c::serialize_pair(pair), std::invalid_argument);
}

TEST(GamebubComposedWire, AckGrammarAndNestedCrossIdentityRejectAfterCrcRepair) {
  for (unsigned scenario = 0; scenario < 20; ++scenario) {
    auto bytes = unhex(ack_hex);
    switch (scenario) {
      case 0:
        bytes[0] ^= 1;
        break;
      case 1:
        bytes[4] = 2;
        break;
      case 2:
        b::put32(bytes, 5, 0);
        break;
      case 3:
        b::put32(bytes, 9, 0xffffffffU);
        break;
      case 4:
        bytes[29] = 42;
        break;
      case 5:
        bytes[31] = 53;
        break;
      case 6:
        bytes[33] ^= 1;
        break;
      case 7:
        bytes[37] = 2;
        break;
      case 8:
        bytes[38] = 0;
        break;
      case 9:
        b::put32(bytes, 39, 0xffffffffU);
        break;
      case 10:
        b::put32(bytes, 43, 0xffffffffU);
        break;
      case 11:
        bytes[76] ^= 1;
        break;
      case 12:
        bytes[80] = 2;
        break;
      case 13:
        bytes[93] = 2;
        break;
      case 14:
        b::put32(bytes, 81, 0);
        break;
      case 15:
        b::put32(bytes, 85, 0xffffffffU);
        break;
      case 16:
        b::put32(bytes, 89, 0xffffffffU);
        break;
      case 17:
        b::put32(bytes, 39, 2);
        break;
      case 18:
        b::put32(bytes, 43, 1);
        break;
      case 19:
        b::put32(bytes, 85, 1);
        break;
    }
    repair_ack(bytes);
    EXPECT_THROW(c::parse_ack(bytes), std::invalid_argument) << scenario;
  }
  auto ack = c::parse_ack(unhex(ack_hex));
  ++ack.epoch;
  EXPECT_THROW(c::serialize_ack(ack), std::invalid_argument);
}

TEST(GamebubComposedWire, AckSyntaxDoesNotClaimExactOutstandingOrPublicationValidation) {
  auto bytes = unhex(ack_hex);
  std::fill(bytes.begin() + 13, bytes.begin() + 29, 0);
  bytes[38] = 2;
  bytes[51] = 255;
  std::fill(bytes.begin() + 94, bytes.begin() + 126, 0);
  repair_ack(bytes);
  const auto ack = c::parse_ack(bytes);
  EXPECT_EQ(ack.pair_digest, c::Tag {});
  EXPECT_EQ(ack.base_ack[5], 2);
  const auto encoded = c::serialize_ack(ack);
  EXPECT_TRUE(std::equal(encoded.begin(), encoded.end(), bytes.begin(), bytes.end()));
}

TEST(GamebubComposedWire, NestedComponentCrcAndPublicShortBoundsAreChecked) {
  for (unsigned length : {0U, 82U, 49153U}) {
    const std::vector<std::uint8_t> bytes(length);
    EXPECT_THROW(c::hud_identity(bytes), std::invalid_argument);
    EXPECT_THROW(c::base_identity(bytes), std::invalid_argument);
  }
  for (unsigned at : {33U, 76U}) {
    auto bytes = unhex(ack_hex);
    bytes[at] ^= 1;
    seal(bytes);
    EXPECT_THROW(c::parse_ack(bytes), std::invalid_argument);
  }
  auto bytes = unhex(pair_hex);
  bytes[53 + 61 + 47] ^= 1;
  repair_pair(bytes);
  EXPECT_THROW(c::parse_pair(bytes), std::invalid_argument);
  bytes = unhex(pair_hex);
  bytes[247 + 75] = 1;
  repair_pair(bytes);
  EXPECT_EQ(c::hud_identity(c::parse_pair(bytes).hud).modes[0], 1);
}
