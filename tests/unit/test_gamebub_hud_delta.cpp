/**
 * @file tests/unit/test_gamebub_hud_delta.cpp
 * @brief HD22 independent vectors, canonical spans, exact-reference and bounded-input regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <cstdint>
#include <limits>
#include <span>
#include <stdexcept>
#include <string_view>
#include <vector>

// local includes
#include "tools/gamebub/native/hud_delta.h"

namespace {
  namespace h = gamebub::v24::hud_delta;
  namespace b = gamebub::v20::body;

  /** @brief Decode fixed lowercase hexadecimal oracle literals generated with Python struct/hashlib/zlib. */
  std::vector<std::uint8_t> hex(std::string_view text) {
    const auto digit = [](char c) {
      return unsigned(c <= '9' ? c - '0' : c - 'a' + 10);
    };
    std::vector<std::uint8_t> out;
    for (std::size_t i = 0; i < text.size(); i += 2) {
      out.push_back(static_cast<std::uint8_t>((digit(text[i]) << 4) | digit(text[i + 1])));
    }
    return out;
  }

  /** @brief Build the independently declared8x2 RGB565 reference pixels. */
  h::Patch reference() {
    h::Patch patch {8, 2, {}};
    for (unsigned i = 0; i < 16; ++i) {
      patch.words.push_back(static_cast<std::uint16_t>(4096 + i));
    }
    return patch;
  }

  /** @brief Frozen Python RAW packet with exact independent canonical tag and CRC. */
  std::vector<std::uint8_t> raw() {
    return hex("48443232010008000200200000000000000000000000000000000000000036a262a4ebf9da6b7d7380de6f336e0900100110021003100410051006100710081009100a100b100c100d100e100f101b8ed321");
  }

  /** @brief Frozen Python COPY packet. */
  std::vector<std::uint8_t> copy() {
    return hex("484432320101080002000000000036a262a4ebf9da6b7d7380de6f336e0936a262a4ebf9da6b7d7380de6f336e09c0527178");
  }

  /** @brief Frozen Python SPAN_XOR packet with an interior two-word zero gap and a second row. */
  std::vector<std::uint8_t> span() {
    return hex("484432320102080002001800000036a262a4ebf9da6b7d7380de6f336e09ab6ae47b96f3462b7835d71ab66c5b9a0200000001000400010000000000020001000600010004003338da63");
  }

  /** @brief Recompute an outer CRC while keeping a deliberately malformed grammar. */
  void seal(std::vector<std::uint8_t> &packet) {
    b::put32(packet, packet.size() - 4, gamebub::v20::crc32(std::span(packet).first(packet.size() - 4)));
  }

  /** @brief Append one explicit little-endian16 payload field. */
  void word(std::vector<std::uint8_t> &out, unsigned value) {
    out.push_back(static_cast<std::uint8_t>(value));
    out.push_back(static_cast<std::uint8_t>(value >> 8));
  }

  /** @brief Create a packet whose content tag matches the declared result despite malformed span syntax. */
  std::vector<std::uint8_t> spans(const h::Patch &result, const h::Patch &ref, std::initializer_list<unsigned> values) {
    std::vector<std::uint8_t> payload;
    for (auto value : values) {
      word(payload, value);
    }
    std::vector<std::uint8_t> out(50 + payload.size());
    std::copy_n("HD22", 4, out.begin());
    out[4] = 1;
    out[5] = 2;
    out[6] = static_cast<std::uint8_t>(result.width);
    out[7] = static_cast<std::uint8_t>(result.width >> 8);
    out[8] = static_cast<std::uint8_t>(result.height);
    out[9] = static_cast<std::uint8_t>(result.height >> 8);
    b::put32(out, 10, static_cast<std::uint32_t>(payload.size()));
    const auto rt = h::tag(ref), ct = h::tag(result);
    std::copy(rt.begin(), rt.end(), out.begin() + 14);
    std::copy(ct.begin(), ct.end(), out.begin() + 30);
    std::copy(payload.begin(), payload.end(), out.begin() + 46);
    seal(out);
    return out;
  }
}  // namespace

TEST(GamebubHudDelta, IndependentRawCopyAndMergedGapOraclesReconstructExactWords) {
  const auto ref = reference();
  const auto snapshot = ref;
  EXPECT_EQ(h::decode(raw()), ref);
  EXPECT_EQ(h::decode(raw(), &ref), ref);
  EXPECT_EQ(h::decode(copy(), &ref), ref);
  auto expected = ref;
  expected.words[1] ^= 1;
  expected.words[4] ^= 2;
  expected.words[14] ^= 4;
  EXPECT_EQ(h::decode(span(), &ref), expected);
  EXPECT_EQ(ref, snapshot);
  const auto expected_tag = hex("36a262a4ebf9da6b7d7380de6f336e09");
  const auto tag = h::tag(ref);
  EXPECT_EQ(std::vector(tag.begin(), tag.end()), expected_tag);
}

TEST(GamebubHudDelta, EveryTruncationTrailingByteAndSingleBitCorruptionIsRejected) {
  const auto ref = reference();
  for (const auto &packet : {raw(), copy(), span()}) {
    for (std::size_t size = 0; size < packet.size(); ++size) {
      EXPECT_THROW(h::decode(std::span(packet).first(size), &ref), std::invalid_argument);
    }
    auto extra = packet;
    extra.push_back(0);
    EXPECT_THROW(h::decode(extra, &ref), std::invalid_argument);
    for (std::size_t at = 0; at < packet.size(); ++at) {
      for (unsigned bit = 0; bit < 8; ++bit) {
        auto bad = packet;
        bad[at] ^= static_cast<std::uint8_t>(1U << bit);
        EXPECT_THROW(h::decode(bad, &ref), std::invalid_argument);
      }
    }
  }
}

TEST(GamebubHudDelta, GeometryTagAndStorageBoundsIncludeOddSingleAndMaximumPatches) {
  EXPECT_NO_THROW(h::geometry(1, 1));
  EXPECT_NO_THROW(h::geometry(3, 7));
  EXPECT_NO_THROW(h::geometry(720, 1));
  EXPECT_NO_THROW(h::geometry(44, 480));
  for (auto dims : {std::array<unsigned, 2> {0, 1}, {1, 0}, {721, 1}, {1, 481}, {720, 480}, {std::numeric_limits<unsigned>::max(), 1}}) {
    EXPECT_THROW(h::geometry(dims[0], dims[1]), std::invalid_argument);
  }
  EXPECT_THROW(h::tag(h::Patch {1, 1, {}}), std::invalid_argument);
  EXPECT_THROW(h::tag(h::Patch {0, 0, {}}), std::invalid_argument);
  h::Patch maximum {44, 480, std::vector<std::uint16_t>(21120, 0xabcd)};
  auto packet = raw();
  packet.resize(h::max_packet);
  packet[6] = 44;
  packet[7] = 0;
  packet[8] = 0xe0;
  packet[9] = 1;
  b::put32(packet, 10, 42240);
  const auto tag = h::tag(maximum);
  std::copy(tag.begin(), tag.end(), packet.begin() + 30);
  for (unsigned i = 0; i < 21120; ++i) {
    packet[46 + 2 * i] = 0xcd;
    packet[47 + 2 * i] = 0xab;
  }
  seal(packet);
  EXPECT_EQ(h::decode(packet), maximum);
  packet.push_back(0);
  EXPECT_THROW(h::decode(packet), std::invalid_argument);
}

TEST(GamebubHudDelta, ResealedMagicVersionModeLengthAndRawReferenceFieldsReject) {
  for (unsigned at : {0U, 1U, 2U, 3U, 4U, 5U}) {
    auto packet = raw();
    packet[at] = at == 5 ? 3 : 0;
    seal(packet);
    EXPECT_THROW(h::decode(packet), std::invalid_argument);
  }
  for (unsigned size : {0U, 31U, 33U, 42241U, 0xffffffffU}) {
    auto packet = raw();
    b::put32(packet, 10, size);
    seal(packet);
    EXPECT_THROW(h::decode(packet), std::invalid_argument);
  }
  auto packet = raw();
  packet[14] = 1;
  seal(packet);
  EXPECT_THROW(h::decode(packet), std::invalid_argument);
  packet = raw();
  packet[30] ^= 1;
  seal(packet);
  EXPECT_THROW(h::decode(packet), std::invalid_argument);
  packet = raw();
  packet[5] = 1;
  seal(packet);
  const auto ref = reference();
  EXPECT_THROW(h::decode(packet, &ref), std::invalid_argument);
}

TEST(GamebubHudDelta, ExactReferencesAreRequiredAndNeverMutatedOnFailure) {
  const auto ref = reference();
  for (const auto &packet : {copy(), span()}) {
    EXPECT_THROW(h::decode(packet), std::invalid_argument);
    auto wrong = ref;
    wrong.words[0] ^= 1;
    const auto snapshot = wrong;
    EXPECT_THROW(h::decode(packet, &wrong), std::invalid_argument);
    EXPECT_EQ(wrong, snapshot);
    wrong = {4, 4, ref.words};
    EXPECT_THROW(h::decode(packet, &wrong), std::invalid_argument);
    wrong = ref;
    wrong.words.pop_back();
    EXPECT_THROW(h::decode(packet, &wrong), std::invalid_argument);
    auto bad = packet;
    bad[30] ^= 1;
    seal(bad);
    EXPECT_THROW(h::decode(bad, &ref), std::invalid_argument);
    EXPECT_EQ(ref, reference());
  }
}

TEST(GamebubHudDelta, CanonicalSeparateGapThreeIsAcceptedButGapTwoAndOverlapAreRejected) {
  const auto ref = reference();
  auto result = ref;
  result.words[0] ^= 1;
  result.words[4] ^= 2;
  const auto legal = spans(result, ref, {2, 0, 0, 1, 1, 0, 4, 1, 2});
  EXPECT_EQ(h::decode(legal, &ref), result);
  result = ref;
  result.words[0] ^= 1;
  result.words[3] ^= 2;
  EXPECT_THROW(h::decode(spans(result, ref, {2, 0, 0, 1, 1, 0, 3, 1, 2}), &ref), std::invalid_argument);
  EXPECT_THROW(h::decode(spans(ref, ref, {2, 0, 0, 1, 1, 0, 0, 1, 1}), &ref), std::invalid_argument);
}

TEST(GamebubHudDelta, ZeroEndpointsAndLongInteriorZeroGapsRejectEvenWithMatchingResultTags) {
  const auto ref = reference();
  EXPECT_THROW(h::decode(spans(ref, ref, {1, 0, 0, 1, 0}), &ref), std::invalid_argument);
  auto result = ref;
  result.words[1] ^= 1;
  EXPECT_THROW(h::decode(spans(result, ref, {1, 0, 0, 2, 0, 1}), &ref), std::invalid_argument);
  result = ref;
  result.words[0] ^= 1;
  EXPECT_THROW(h::decode(spans(result, ref, {1, 0, 0, 2, 1, 0}), &ref), std::invalid_argument);
  result = ref;
  result.words[0] ^= 1;
  result.words[4] ^= 2;
  EXPECT_THROW(h::decode(spans(result, ref, {1, 0, 0, 5, 1, 0, 0, 0, 2}), &ref), std::invalid_argument);
}

TEST(GamebubHudDelta, SpanCountsGeometryOrderingPayloadAndTrailingBytesAreBounded) {
  const auto ref = reference();
  for (auto values : {std::vector<unsigned> {0}, {17}, {1}, {2, 0, 0, 1, 1}, {1, 2, 0, 1, 1}, {1, 0, 0, 0, 1}, {1, 0, 0, 9, 1}, {1, 0, 8, 1, 1}, {1, 0, 7, 2, 1}, {1, 0, 0, 2, 1}, {2, 0, 0, 4, 1, 0, 0, 2, 1}, {2, 1, 0, 1, 1, 0, 0, 1, 1}}) {
    auto packet = span();
    packet.resize(50 + 2 * values.size());
    b::put32(packet, 10, static_cast<std::uint32_t>(2 * values.size()));
    for (unsigned i = 0; i < values.size(); ++i) {
      packet[46 + 2 * i] = static_cast<std::uint8_t>(values[i]);
      packet[47 + 2 * i] = static_cast<std::uint8_t>(values[i] >> 8);
    }
    seal(packet);
    EXPECT_THROW(h::decode(packet, &ref), std::invalid_argument);
  }
  auto packet = span();
  packet.erase(packet.begin() + 46, packet.end() - 4);
  b::put32(packet, 10, 0);
  seal(packet);
  EXPECT_THROW(h::decode(packet, &ref), std::invalid_argument);
  auto result = ref;
  result.words[0] ^= 1;
  EXPECT_THROW(h::decode(spans(result, ref, {1, 0, 0, 1, 1, 123}), &ref), std::invalid_argument);
}
