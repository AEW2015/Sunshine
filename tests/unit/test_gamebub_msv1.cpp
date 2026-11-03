/**
 * @file tests/unit/test_gamebub_msv1.cpp
 * @brief Tests for the optional Game Bub MSV1 packet serializer.
 */
#if defined(SUNSHINE_GAMEBUB_EXPERIMENTAL)
  // test includes
  #include "../tests_common.h"

  // standard includes
  #include <cstdint>
  #include <filesystem>
  #include <fstream>
  #include <iterator>
  #include <stdexcept>
  #include <vector>

  // local includes
  #include "src/gamebub/msv1.h"

namespace {
  /**
   * @brief Read a binary receiver fixture from the checked-out source tree.
   * @param filename Name under tools/gamebub/fixtures.
   * @return Complete binary file bytes.
   */
  std::vector<std::uint8_t> fixture(const char *filename) {
    const auto path = std::filesystem::path {SUNSHINE_SOURCE_DIR} / "tools" / "gamebub" / "fixtures" / filename;
    std::ifstream input {path, std::ios::binary};
    if (!input) {
      throw std::runtime_error {"Cannot open receiver fixture"};
    }
    return {std::istreambuf_iterator<char> {input}, std::istreambuf_iterator<char> {}};
  }
}  // namespace

TEST(GameBubMsv1, PacketsMatchPinnedReceiverFixtureByteForByte) {
  const auto image = fixture("receiver-pattern-720x480-420-q65.jpg");
  const auto golden = fixture("receiver-pattern-msv1-packets.bin");
  gamebub::msv1::packetizer_t sender {image, 0x12345678, 1234567890123ULL};
  std::vector<std::uint8_t> actual;
  for (std::size_t offset = 0; offset < image.size(); offset += gamebub::msv1::max_payload) {
    const auto packet = sender.packet_at(offset);
    actual.push_back(static_cast<std::uint8_t>(packet.size() >> 8));
    actual.push_back(static_cast<std::uint8_t>(packet.size()));
    actual.insert(actual.end(), packet.begin(), packet.end());
  }
  ASSERT_EQ(actual, golden);
}

TEST(GameBubMsv1, RejectsInvalidFrameAndChunkBounds) {
  const std::vector<std::uint8_t> empty;
  const std::vector<std::uint8_t> one {42};
  const std::vector<std::uint8_t> too_large(gamebub::msv1::max_frame + 1, 42);
  EXPECT_THROW((gamebub::msv1::packetizer_t {empty, 0, 0}), std::invalid_argument);
  EXPECT_THROW((gamebub::msv1::packetizer_t {too_large, 0, 0}), std::invalid_argument);
  EXPECT_THROW((gamebub::msv1::packetizer_t {one, 0, 0, 0}), std::invalid_argument);
  EXPECT_THROW((gamebub::msv1::packetizer_t {one, 0, 0, gamebub::msv1::max_payload + 1}), std::invalid_argument);
  const std::vector<std::uint8_t> maximum(gamebub::msv1::max_frame, 42);
  EXPECT_NO_THROW((gamebub::msv1::packetizer_t {maximum, 0, 0}));
}

TEST(GameBubMsv1, SmallFrameAndOffsetsSetCorrectFlagsAndSizes) {
  const std::vector<std::uint8_t> image {'a', 'b', 'c'};
  gamebub::msv1::packetizer_t sender {image, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFFULL, 2};
  const auto first = sender.packet_at(0);
  const auto last = sender.packet_at(2);
  ASSERT_EQ(first.size(), gamebub::msv1::header_size + 2);
  ASSERT_EQ(last.size(), gamebub::msv1::header_size + 1);
  EXPECT_EQ(first[7], 1);
  EXPECT_EQ(last[7], 2);
  EXPECT_EQ(first[27], 0);
  EXPECT_EQ(last[23], 2);
  EXPECT_EQ(first[40], 'a');
  EXPECT_EQ(last[40], 'c');
  EXPECT_THROW(static_cast<void>(sender.packet_at(1)), std::invalid_argument);
  EXPECT_THROW(static_cast<void>(sender.packet_at(3)), std::invalid_argument);
  gamebub::msv1::packetizer_t single {image, 0, 0};
  EXPECT_EQ(single.packet_at(0)[7], 3);
}
#endif
