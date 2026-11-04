/**
 * @file tests/unit/test_gamebub_v20_patch_encoder.cpp
 * @brief Exact patch search, row-boundary and immutable-source regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <numeric>
#include <vector>

// local includes
#include "tools/gamebub/native/patch_encoder.h"

namespace {
  namespace e = gamebub::v20::encoder;
  namespace b = gamebub::v20::body;
  namespace c = gamebub::v20::candidate;
}  // namespace

TEST(GamebubV20PatchEncoder, LiteralAndRunTokensMatchFrozenGreedyOrdering) {
  EXPECT_EQ(e::patch_detail::tokens(std::vector<std::uint16_t> {1, 1, 2, 3, 3, 3, 4}, 1), (std::vector<std::uint8_t> {2, 1, 1, 2, 130, 3, 0, 4}));
  EXPECT_EQ(e::patch_detail::tokens(std::vector<std::uint16_t> {0x1234, 0x1234, 0x1234}, 2), (std::vector<std::uint8_t> {130, 0x34, 0x12}));
  const std::vector<std::uint16_t> solid(130, 7);
  EXPECT_EQ(e::patch_detail::tokens(solid, 1), (std::vector<std::uint8_t> {255, 7, 1, 7, 7}));
  std::vector<std::uint16_t> literal(130);
  std::iota(literal.begin(), literal.end(), 0);
  auto tokens = e::patch_detail::tokens(literal, 1);
  ASSERT_EQ(tokens.size(), 132);
  EXPECT_EQ(tokens[0], 127);
  EXPECT_EQ(tokens[129], 1);
  EXPECT_EQ(tokens[130], 128);
  EXPECT_EQ(tokens[131], 129);
}

TEST(GamebubV20PatchEncoder, FrozenFormatAndModeTiesAndRawSelection) {
  // One pixel's palette expands HP01; HR01 raw wins without inventing a palette.
  auto packet = e::encode_patch(std::vector<std::uint16_t> {0x1234}, {1, 1, 1, 1}, 2, 2);
  EXPECT_TRUE(b::magic(packet, "HR01"));
  EXPECT_EQ(packet[5], 0);
  EXPECT_EQ(b::decode_patch(packet, 2, 2).words, (std::vector<std::uint16_t> {0x1234}));
  // Seventeen equal pixels produce equal HP01/HR01 sizes; HP01 wins the format tie.
  packet = e::encode_patch(std::vector<std::uint16_t>(17, 7), {0, 0, 17, 1}, 18, 2);
  EXPECT_TRUE(b::magic(packet, "HP01"));
  EXPECT_EQ(packet[5], 1);
  std::vector<std::uint16_t> unique(258);
  std::iota(unique.begin(), unique.end(), 0);
  packet = e::encode_patch(unique, {0, 0, 258, 1}, 258, 2);
  EXPECT_TRUE(b::magic(packet, "HP01"));
  EXPECT_EQ(packet[5], 0);
  EXPECT_EQ(b::decode_patch(packet, 258, 2).words, unique);
  // The three-word run saves exactly the row prefix and literal-token costs.
  std::vector<std::uint16_t> tied_rows(131);
  std::iota(tied_rows.begin() + 3, tied_rows.end(), 1);
  packet = e::encode_patch(tied_rows, {0, 0, 131, 1}, 132, 2);
  EXPECT_TRUE(b::magic(packet, "HR01"));
  EXPECT_EQ(packet[5], 0);
}

TEST(GamebubV20PatchEncoder, PalettePackingAndRowsPreserveExactWords) {
  for (unsigned colors : {2, 4, 16, 17, 256}) {
    std::vector<std::uint16_t> words(512);
    for (unsigned i = 0; i < words.size(); ++i) {
      words[i] = static_cast<std::uint16_t>((i % colors) * 13);
    }
    const auto packet = e::encode_patch(words, {0, 0, 256, 2}, 256, 2);
    EXPECT_EQ(b::decode_patch(packet, 256, 2).words, words);
    if (colors <= 17) {
      EXPECT_TRUE(b::magic(packet, "HP01"));
      EXPECT_EQ(packet[5], colors <= 2 ? 1 : colors <= 4 ? 2 :
                                           colors <= 16  ? 4 :
                                                           8);
    }
  }
  const std::vector<std::uint16_t> solid(256, 0x1234);
  auto packet = e::encode_patch(solid, {0, 0, 128, 2}, 128, 2);
  EXPECT_TRUE(b::magic(packet, "HR01"));
  EXPECT_EQ(packet[5], 1);
  EXPECT_EQ(b::u16(packet, 24), 3);
  EXPECT_EQ(b::u16(packet, 29), 3);
  EXPECT_EQ(b::decode_patch(packet, 128, 2).words, solid);
  std::vector<std::uint16_t> runs(1440);
  for (unsigned i = 0; i < runs.size(); ++i) {
    runs[i] = static_cast<std::uint16_t>((i / 20) % 32);
  }
  packet = e::encode_patch(runs, {0, 0, 720, 2}, 720, 2);
  EXPECT_TRUE(b::magic(packet, "HR01"));
  EXPECT_EQ(packet[5], 2);
  EXPECT_EQ(b::decode_patch(packet, 720, 2).words, runs);
}

TEST(GamebubV20PatchEncoder, RejectsInvalidGeometryBeforeEncoding) {
  const std::vector<std::uint16_t> words(4);
  EXPECT_THROW(e::encode_patch(words, {0, 0, 2, 2}, 1, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {0, 0, 0, 2}, 2, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {0, 0, 2, 0}, 2, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {2, 0, 2, 2}, 2, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {0, 2, 2, 2}, 2, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {1, 0, 2, 2}, 2, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {0, 1, 2, 2}, 2, 2), std::invalid_argument);
  EXPECT_THROW(e::encode_patch(words, {0, 0, 1, 2}, 2, 2), std::invalid_argument);
}

TEST(GamebubV20PatchEncoder, MandatoryRectanglesAreOrderedAndSourceIsImmutable) {
  std::vector<std::uint16_t> words(c::width * c::height);
  for (unsigned i = 0; i < words.size(); ++i) {
    words[i] = static_cast<std::uint16_t>(i);
  }
  const c::Source source(words);
  auto packets = e::encode_patches(source);
  ASSERT_EQ(packets.size(), c::rectangles.size());
  for (unsigned i = 0; i < packets.size(); ++i) {
    const auto decoded = b::decode_patch(packets[i], c::width, c::height);
    const auto rect = c::rectangles[i];
    EXPECT_EQ(decoded.x, rect.x);
    EXPECT_EQ(decoded.y, rect.y);
    EXPECT_EQ(decoded.width, rect.width);
    EXPECT_EQ(decoded.height, rect.height);
    for (unsigned y = 0; y < rect.height; ++y) {
      for (unsigned x = 0; x < rect.width; ++x) {
        EXPECT_EQ(decoded.words[y * rect.width + x], words[(rect.y + y) * c::width + rect.x + x]);
      }
    }
  }
  EXPECT_TRUE(std::equal(words.begin(), words.end(), source.words().begin(), source.words().end()));
  EXPECT_EQ(e::encode_patches(source), packets);
}
