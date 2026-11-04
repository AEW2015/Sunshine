/**
 * @file tests/unit/test_gamebub_recovery_wire.cpp
 * @brief Offline RS24 grammar and exact-byte regressions; no state or hardware claims.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <cstdint>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>

// local includes
#include "tools/gamebub/native/recovery_wire.h"

namespace {
  namespace r = gamebub::v24::recovery;

  /** @brief SHA256[:16] of the pinned PROFILE JSON with sorted keys and compact separators. */
  constexpr std::array<std::uint8_t, 16> profile {0xd7, 0xbf, 0x1a, 0x16, 0x9b, 0x4f, 0x75, 0xff, 0xd9, 0xb3, 0x6a, 0x54, 0x29, 0xc4, 0xc9, 0x4d};

  /** @brief Frozen OFFER encoded independently by Python struct.pack and zlib.crc32. */
  constexpr std::array<std::uint8_t, r::control_bytes> offer_bytes {
    0x52,
    0x53,
    0x32,
    0x34,
    0x01,
    0x03,
    0x78,
    0x56,
    0x34,
    0x12,
    0x08,
    0x07,
    0x06,
    0x05,
    0x04,
    0x03,
    0x02,
    0x01,
    0x18,
    0x17,
    0x16,
    0x15,
    0x14,
    0x13,
    0x12,
    0x11,
    0xd7,
    0xbf,
    0x1a,
    0x16,
    0x9b,
    0x4f,
    0x75,
    0xff,
    0xd9,
    0xb3,
    0x6a,
    0x54,
    0x29,
    0xc4,
    0xc9,
    0x4d,
    0xad,
    0xfe,
    0x96,
    0xa4
  };

  /** @brief Construct the independent OFFER oracle's semantic fields. */
  r::Control offer() {
    return {r::Kind::offer, 0x12345678U, 0x0102030405060708ULL, 0x1112131415161718ULL, profile};
  }

  /** @brief Recompute a packet CRC after deliberately changing grammar fields. */
  std::array<std::uint8_t, r::control_bytes> reseal(std::array<std::uint8_t, r::control_bytes> bytes) {
    const auto checksum = gamebub::v20::crc32(std::span(bytes).first(42));
    for (unsigned i = 0; i < 4; ++i) {
      bytes[42 + i] = static_cast<std::uint8_t>(checksum >> (8 * i));
    }
    return bytes;
  }
}  // namespace

TEST(GamebubRecoveryWire, OfferMatchesIndependentLittleEndianOracle) {
  EXPECT_EQ(r::serialize(offer()), offer_bytes);
  EXPECT_EQ(r::parse(offer_bytes), offer());
}

TEST(GamebubRecoveryWire, AllKindsRoundTripAtLegalEpochAndNonceBoundaries) {
  for (unsigned kind = 1; kind <= 9; ++kind) {
    for (auto epoch : {0U, 1U, r::maximum_epoch}) {
      if ((kind == 1 && epoch != 0) || (kind >= 3 && epoch == 0)) {
        continue;
      }
      for (auto nonce : {std::uint64_t {1}, std::numeric_limits<std::uint64_t>::max()}) {
        const r::Control value {static_cast<r::Kind>(kind), epoch, nonce, kind == 1 ? 0 : nonce, profile};
        EXPECT_EQ(r::parse(r::serialize(value)), value);
      }
    }
  }
}

TEST(GamebubRecoveryWire, ProfileRemainsOpaqueToSyntaxLayer) {
  auto value = offer();
  value.profile.fill(0);
  EXPECT_EQ(r::parse(r::serialize(value)), value);
  value.profile.fill(255);
  EXPECT_EQ(r::parse(r::serialize(value)), value);
}

TEST(GamebubRecoveryWire, EverySingleBitCorruptionFailsCrc) {
  for (unsigned at = 0; at < offer_bytes.size(); ++at) {
    for (unsigned bit = 0; bit < 8; ++bit) {
      auto bytes = offer_bytes;
      bytes[at] ^= static_cast<std::uint8_t>(1U << bit);
      EXPECT_THROW(r::parse(bytes), std::invalid_argument) << at << ":" << bit;
    }
  }
}

TEST(GamebubRecoveryWire, ExactLengthRejectsEveryTruncationAndTrailingBytes) {
  for (unsigned size = 0; size < offer_bytes.size(); ++size) {
    EXPECT_THROW(r::parse(std::span(offer_bytes).first(size)), std::invalid_argument) << size;
  }
  std::vector<std::uint8_t> extra(offer_bytes.begin(), offer_bytes.end());
  extra.push_back(0);
  EXPECT_THROW(r::parse(extra), std::invalid_argument);
}

TEST(GamebubRecoveryWire, ResealedInvalidHeaderAndFieldValuesAreRejected) {
  for (unsigned at = 0; at < 5; ++at) {
    auto bytes = offer_bytes;
    bytes[at] ^= 1;
    EXPECT_THROW(r::parse(reseal(bytes)), std::invalid_argument) << at;
  }
  for (auto kind : {0U, 10U, 255U}) {
    auto bytes = offer_bytes;
    bytes[5] = static_cast<std::uint8_t>(kind);
    EXPECT_THROW(r::parse(reseal(bytes)), std::invalid_argument);
  }
  auto bytes = offer_bytes;
  for (unsigned at = 6; at < 10; ++at) {
    bytes[at] = 255;
  }
  EXPECT_THROW(r::parse(reseal(bytes)), std::invalid_argument);
  for (unsigned start : {10U, 18U}) {
    bytes = offer_bytes;
    for (unsigned at = start; at < start + 8; ++at) {
      bytes[at] = 0;
    }
    EXPECT_THROW(r::parse(reseal(bytes)), std::invalid_argument);
  }
  bytes = offer_bytes;
  for (unsigned at = 6; at < 10; ++at) {
    bytes[at] = 0;
  }
  EXPECT_THROW(r::parse(reseal(bytes)), std::invalid_argument);
  bytes = offer_bytes;
  bytes[5] = 1;
  EXPECT_THROW(r::parse(reseal(bytes)), std::invalid_argument);
  auto hello = r::serialize(r::Control {r::Kind::hello, 0, 1, 0, profile});
  hello[18] = 1;
  EXPECT_THROW(r::parse(reseal(hello)), std::invalid_argument);
}

TEST(GamebubRecoveryWire, SerializerRejectsInvalidLocalFields) {
  for (auto kind : {0U, 10U, 255U}) {
    auto value = offer();
    value.kind = static_cast<r::Kind>(kind);
    EXPECT_THROW(r::serialize(value), std::invalid_argument);
  }
  auto value = offer();
  value.epoch = 0xffffffffU;
  EXPECT_THROW(r::serialize(value), std::invalid_argument);
  value = offer();
  value.host_nonce = 0;
  EXPECT_THROW(r::serialize(value), std::invalid_argument);
  for (unsigned kind = 2; kind <= 9; ++kind) {
    value = offer();
    value.kind = static_cast<r::Kind>(kind);
    value.target_nonce = 0;
    EXPECT_THROW(r::serialize(value), std::invalid_argument);
  }
  for (unsigned kind = 3; kind <= 9; ++kind) {
    value = offer();
    value.kind = static_cast<r::Kind>(kind);
    value.epoch = 0;
    EXPECT_THROW(r::serialize(value), std::invalid_argument);
  }
  value = {r::Kind::hello, 1, 1, 0, profile};
  EXPECT_THROW(r::serialize(value), std::invalid_argument);
  value = {r::Kind::hello, 0, 1, 1, profile};
  EXPECT_THROW(r::serialize(value), std::invalid_argument);
}
