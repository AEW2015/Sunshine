/**
 * @file tests/unit/test_gamebub_composed_refresh.cpp
 * @brief Independent-refresh software reconstruction and nested corruption regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <filesystem>
#include <span>
#include <stdexcept>
#include <vector>

// local includes
#include "tools/gamebub/native/body_case.h"
#include "tools/gamebub/native/composed_refresh.h"

namespace {
  namespace c = gamebub::v24::composed;
  namespace r = gamebub::v24::refresh;
  namespace b = gamebub::v20::body;

  /** @brief Load one checked-in synthetic vector independently published by MoonBub4025d355. */
  std::vector<std::uint8_t> fixture(const char *name) {
    const auto root = std::filesystem::path(__FILE__).parent_path().parent_path().parent_path();
    return gamebub::v20::body_case::read_file(root / "tools/gamebub/fixtures" / name, 49152);
  }

  /** @brief Load and hash-check the exact complete CP23 input. */
  std::vector<std::uint8_t> packet() {
    auto bytes = fixture("v24-independent-refresh-epoch1.cp23");
    b::require(gamebub::v20::body_case::digest(bytes) == "a44fcd4a62027dc9c609c4b64a68145ee9f915880a7ec312ade811525eceb24b", "refresh fixture hash");
    return bytes;
  }

  /** @brief Recompute the final CRC of an intentionally changed owned component. */
  void seal(std::span<std::uint8_t> bytes) {
    b::put32(bytes, bytes.size() - 4, gamebub::v20::crc32(bytes.first(bytes.size() - 4)));
  }
}  // namespace

TEST(GamebubComposedRefresh, GoldenRefreshMatchesCompleteDisplayExactHudAndJointAck) {
  const auto decoded = r::decode_legacy_refresh(packet());
  EXPECT_EQ(decoded.frame.width, 720);
  EXPECT_EQ(decoded.frame.height, 480);
  const auto expected = fixture("v24-independent-refresh-epoch1.ja23");
  EXPECT_EQ(std::vector(decoded.ack.begin(), decoded.ack.end()), expected);
  const auto bytes = r::display_le(decoded);
  EXPECT_EQ(bytes.size(), 691200);
  EXPECT_EQ(gamebub::v20::body_case::digest(bytes), "27842473cfb9a4c186041341e56ad3572d7ad34ea761c3d2fbdf6eadad1382d4");
  unsigned words = 0;
  // RGB(44,96,156) independently maps to RGB565 0x2b13 before any lossy base transform.
  for (const auto rectangle : gamebub::v20::candidate::rectangles) {
    for (unsigned y = rectangle.y; y < rectangle.y + rectangle.height; ++y) {
      for (unsigned x = rectangle.x; x < rectangle.x + rectangle.width; ++x) {
        ASSERT_EQ(decoded.frame.display565[y * 720 + x], 0x2b13);
        ++words;
      }
    }
  }
  EXPECT_EQ(words, 21120);
}

TEST(GamebubComposedRefresh, DeltaHudDispatchIsRejectedWithoutPretendingFullProfileSupport) {
  auto pair = c::parse_pair(packet());
  pair.hud[75] = 1;
  seal(pair.hud);
  EXPECT_THROW(r::decode_legacy_refresh(c::serialize_pair(pair)), std::invalid_argument);
}

TEST(GamebubComposedRefresh, ReferencedHudCannotEnterIndependentRefreshDecoder) {
  auto pair = c::parse_pair(packet());
  pair.frame = 1;
  b::put32(pair.base, 10, 1);
  b::put32(pair.base, 71, 1);
  const auto inner_bytes = b::u32(pair.base, 52);
  seal(std::span(pair.base).subspan(61, inner_bytes));
  seal(pair.base);
  b::put32(pair.hud, 9, 1);
  pair.hud[18] = 1;
  b::put32(pair.hud, 19, 0);
  b::put32(pair.hud, 23, 0);
  pair.hud[27] = 1;
  seal(pair.hud);
  EXPECT_THROW(r::decode_legacy_refresh(c::serialize_pair(pair)), std::invalid_argument);
}

TEST(GamebubComposedRefresh, EntropyFailureSurvivesRepairedOuterAndInnerCrcs) {
  auto pair = c::parse_pair(packet());
  const auto inner_bytes = b::u32(pair.base, 52);
  const auto map_bytes = b::u32(pair.base, 61 + 30);
  pair.base[61 + 46 + map_bytes] ^= 1;
  seal(std::span(pair.base).subspan(61, inner_bytes));
  seal(pair.base);
  EXPECT_THROW(r::decode_legacy_refresh(c::serialize_pair(pair)), std::invalid_argument);
}

TEST(GamebubComposedRefresh, ReconstructedHudTagMustMatchDecodedWords) {
  auto pair = c::parse_pair(packet());
  pair.hud[43] ^= 1;
  seal(pair.hud);
  EXPECT_THROW(r::decode_legacy_refresh(c::serialize_pair(pair)), std::invalid_argument);
}

TEST(GamebubComposedRefresh, LegacyRectangleAndPatchCrcAreCheckedBeyondOuterEnvelopes) {
  auto pair = c::parse_pair(packet());
  pair.hud[79 + 6] += 1;
  const auto patch_bytes = b::u32(pair.hud, 59);
  seal(std::span(pair.hud).subspan(79, patch_bytes));
  seal(pair.hud);
  EXPECT_THROW(r::decode_legacy_refresh(c::serialize_pair(pair)), std::invalid_argument);
  pair = c::parse_pair(packet());
  pair.hud[79 + 24] ^= 1;
  seal(pair.hud);
  EXPECT_THROW(r::decode_legacy_refresh(c::serialize_pair(pair)), std::invalid_argument);
}

TEST(GamebubComposedRefresh, DisplayExportRejectsMissingGeometryOrTruncatedWords) {
  EXPECT_THROW(r::display_le(r::Decoded {}), std::invalid_argument);
  auto decoded = r::decode_legacy_refresh(packet());
  decoded.frame.display565.pop_back();
  EXPECT_THROW(r::display_le(decoded), std::invalid_argument);
}
