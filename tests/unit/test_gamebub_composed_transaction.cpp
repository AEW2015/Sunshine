/**
 * @file tests/unit/test_gamebub_composed_transaction.cpp
 * @brief Exact offline JA23 binding, immutable retry and failed-ACK retention regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <filesystem>
#include <span>
#include <vector>

// local includes
#include "tools/gamebub/native/body_case.h"
#include "tools/gamebub/native/composed_transaction.h"

namespace {
  namespace b = gamebub::v20::body;
  namespace c = gamebub::v24::composed;
  namespace t = gamebub::v24::transaction;

  /**
   * @brief Read the independent pinned first-frame fixtures without native regeneration.
   */
  std::vector<std::uint8_t> fixture(const char *name) {
    const auto root = std::filesystem::path(__FILE__).parent_path().parent_path().parent_path();
    return gamebub::v20::body_case::read_file(root / "tools/gamebub/fixtures" / name, c::frame_cap);
  }

  /**
   * @brief Load the independent source-model CP23 packet.
   */
  std::vector<std::uint8_t> packet() {
    auto bytes = fixture("v24-independent-refresh-epoch1.cp23");
    b::require(gamebub::v20::body_case::digest(bytes) == "a44fcd4a62027dc9c609c4b64a68145ee9f915880a7ec312ade811525eceb24b", "transaction fixture hash");
    return bytes;
  }

  /**
   * @brief Load exact JA23 bytes independently frozen by MoonBub4025d355.
   */
  std::vector<std::uint8_t> ack() {
    auto bytes = fixture("v24-independent-refresh-epoch1.ja23");
    b::require(gamebub::v20::body_case::digest(bytes) == "d9372f51eb797f5c369d359ca700c6ae36c6a7a499bf600ef78018696f5fa530", "transaction ACK hash");
    return bytes;
  }

  /**
   * @brief Restore a CRC after a deliberate identity mutation.
   */
  void seal(std::span<std::uint8_t> bytes) {
    b::put32(bytes, bytes.size() - 4, gamebub::v20::crc32(bytes.first(bytes.size() - 4)));
  }

  /**
   * @brief Restore nested and outer CRCs without repairing deliberately wrong ACK fields.
   */
  void repair_ack(std::vector<std::uint8_t> &bytes) {
    seal(std::span(bytes).subspan(33, 43));
    seal(std::span(bytes).subspan(76, 54));
    seal(bytes);
  }

  /**
   * @brief Retag an admitted syntax-only pair after changing owned component headers.
   */
  std::vector<std::uint8_t> reseal(c::Pair pair) {
    seal(std::span(pair.base).subspan(61, b::u32(pair.base, 52)));
    seal(pair.base);
    seal(pair.hud);
    return c::serialize_pair(pair);
  }

  /**
   * @brief Build a later syntax-only P pair without claiming valid predictor pixels.
   */
  std::vector<std::uint8_t> referenced(bool promoted) {
    auto pair = c::parse_pair(packet());
    pair.frame = 1;
    b::put32(pair.base, 10, 1);
    pair.base[5] = promoted ? 2 : 0;
    pair.base[14] = 0;
    pair.base[15] = promoted ? 1 : 255;
    b::put32(pair.base, 16, 0);
    std::copy_n(pair.base.begin() + 36, 16, pair.base.begin() + 20);
    if (!promoted) {
      std::fill(pair.base.begin() + 36, pair.base.begin() + 52, 0);
    }
    pair.base[66] = 0;
    b::put32(pair.base, 71, 1);
    b::put32(pair.base, 75, 0);
    b::put32(pair.hud, 9, 1);
    b::put32(pair.hud, 13, 2);
    pair.hud[17] = 1;
    pair.hud[18] = 0;
    b::put32(pair.hud, 19, 0);
    b::put32(pair.hud, 23, 1);
    std::copy_n(pair.hud.begin() + 43, 16, pair.hud.begin() + 27);
    return reseal(std::move(pair));
  }
}  // namespace

TEST(GamebubComposedTransaction, IndependentGoldenAckBindsAndRetiresOnlyPrivateRetryBytes) {
  const auto bytes = packet(), expected = ack();
  const auto constructed = t::expected_ack(bytes);
  EXPECT_TRUE(std::equal(constructed.begin(), constructed.end(), expected.begin(), expected.end()));
  t::PendingPair transaction(1);
  EXPECT_FALSE(transaction.has_pending());
  EXPECT_FALSE(transaction.acknowledged_frame());
  EXPECT_THROW(transaction.retry(), std::invalid_argument);
  EXPECT_THROW(transaction.acknowledge(expected), std::invalid_argument);
  transaction.begin(bytes);
  EXPECT_TRUE(transaction.has_pending());
  EXPECT_EQ(std::vector(transaction.retry().begin(), transaction.retry().end()), bytes);
  transaction.acknowledge(expected);
  EXPECT_FALSE(transaction.has_pending());
  ASSERT_TRUE(transaction.acknowledged_frame());
  EXPECT_EQ(*transaction.acknowledged_frame(), 0);
  EXPECT_THROW(transaction.retry(), std::invalid_argument);
  EXPECT_THROW(transaction.acknowledge(expected), std::invalid_argument);
  EXPECT_THROW(transaction.begin(bytes), std::invalid_argument);
}

TEST(GamebubComposedTransaction, CallerMutationsAndSecondSubmissionCannotReplaceOutstandingBytes) {
  auto bytes = packet();
  const auto original = bytes;
  t::PendingPair transaction(1);
  transaction.begin(bytes);
  std::fill(bytes.begin(), bytes.end(), 0);
  EXPECT_EQ(std::vector(transaction.retry().begin(), transaction.retry().end()), original);
  EXPECT_THROW(transaction.begin(referenced(false)), std::invalid_argument);
  EXPECT_EQ(std::vector(transaction.retry().begin(), transaction.retry().end()), original);
  transaction.acknowledge(ack());
}

TEST(GamebubComposedTransaction, BoundedEpochCanvasAndFramingRejectBeforeStateChanges) {
  EXPECT_THROW(t::PendingPair(0), std::invalid_argument);
  EXPECT_THROW(t::PendingPair(0xffffffffU), std::invalid_argument);
  t::PendingPair wrong_epoch(2);
  EXPECT_THROW(wrong_epoch.begin(packet()), std::invalid_argument);
  EXPECT_FALSE(wrong_epoch.has_pending());
  t::PendingPair transaction(1);
  for (unsigned length : {0U, 56U, 49153U}) {
    const std::vector<std::uint8_t> bytes(length);
    EXPECT_THROW(transaction.begin(bytes), std::invalid_argument);
    EXPECT_FALSE(transaction.has_pending());
  }
  for (bool width : {false, true}) {
    auto pair = c::parse_pair(packet());
    const auto at = 61 + (width ? 18 : 20);
    pair.base[at] = width ? 0xce : 0xde;
    pair.base[at + 1] = width ? 2 : 1;
    const auto changed_canvas = reseal(pair);
    EXPECT_THROW(transaction.begin(changed_canvas), std::invalid_argument);
    EXPECT_FALSE(transaction.has_pending());
  }
  transaction.begin(packet());
  transaction.acknowledge(ack());
}

TEST(GamebubComposedTransaction, EveryTruncationCorruptionAndTrailingByteRetainsPendingBinding) {
  const auto bytes = packet(), correct = ack();
  t::PendingPair transaction(1);
  transaction.begin(bytes);
  for (std::size_t length = 0; length < correct.size(); ++length) {
    EXPECT_THROW(transaction.acknowledge(std::span(correct).first(length)), std::invalid_argument) << length;
  }
  for (std::size_t at = 0; at < correct.size(); ++at) {
    auto bad = correct;
    bad[at] ^= 1;
    EXPECT_THROW(transaction.acknowledge(bad), std::invalid_argument) << at;
  }
  auto extra = correct;
  extra.push_back(0);
  EXPECT_THROW(transaction.acknowledge(extra), std::invalid_argument);
  EXPECT_TRUE(transaction.has_pending());
  EXPECT_FALSE(transaction.acknowledged_frame());
  EXPECT_EQ(std::vector(transaction.retry().begin(), transaction.retry().end()), bytes);
  transaction.acknowledge(correct);
}

TEST(GamebubComposedTransaction, ResealedSyntaxValidWrongWholeAndComponentAcksNeverConfirm) {
  const auto bytes = packet(), correct = ack();
  t::PendingPair transaction(1);
  transaction.begin(bytes);
  for (unsigned scenario = 0; scenario < 10; ++scenario) {
    auto bad = correct;
    switch (scenario) {
      case 0:
        bad[13] ^= 1;
        break;
      case 1:
        bad[33 + 5] = 2;
        break;
      case 2:
        bad[33 + 14] ^= 1;
        break;
      case 3:
        bad[33 + 23] ^= 1;
        break;
      case 4:
        bad[76 + 13] ^= 1;
        break;
      case 5:
        bad[76 + 17] ^= 1;
        break;
      case 6:
        bad[76 + 18] ^= 1;
        break;
      case 7:
        bad[76 + 34] ^= 1;
        break;
      case 8:
        b::put32(bad, 5, 2);
        b::put32(bad, 33 + 6, 2);
        b::put32(bad, 76 + 5, 2);
        break;
      case 9:
        b::put32(bad, 9, 1);
        b::put32(bad, 33 + 10, 1);
        b::put32(bad, 76 + 9, 1);
        break;
    }
    repair_ack(bad);
    EXPECT_NO_THROW(c::parse_ack(bad)) << scenario;
    EXPECT_THROW(transaction.acknowledge(bad), std::invalid_argument) << scenario;
    EXPECT_TRUE(transaction.has_pending());
    EXPECT_FALSE(transaction.acknowledged_frame());
    EXPECT_EQ(std::vector(transaction.retry().begin(), transaction.retry().end()), bytes);
  }
  transaction.acknowledge(correct);
}

TEST(GamebubComposedTransaction, PAndPromotedReplyFieldsMatchTheirOwnOutstandingPair) {
  for (bool promoted : {false, true}) {
    t::PendingPair transaction(1);
    transaction.begin(packet());
    transaction.acknowledge(ack());
    const auto next = referenced(promoted);
    const auto expected = t::expected_ack(next);
    const auto parsed = c::parse_ack(expected);
    EXPECT_EQ(parsed.frame, 1);
    EXPECT_EQ(parsed.base_ack[18], promoted ? 1 : 255);
    EXPECT_EQ(b::u32(parsed.base_ack, 19), promoted ? 1 : 0xffffffffU);
    EXPECT_EQ(parsed.hud_ack[17], 1);
    if (!promoted) {
      EXPECT_EQ(b::tag_at(parsed.base_ack, 23), b::Tag {});
    }
    transaction.begin(next);
    EXPECT_THROW(transaction.acknowledge(ack()), std::invalid_argument);
    EXPECT_EQ(*transaction.acknowledged_frame(), 0);
    transaction.acknowledge(expected);
    EXPECT_EQ(*transaction.acknowledged_frame(), 1);
    EXPECT_THROW(transaction.begin(packet()), std::invalid_argument);
    EXPECT_THROW(transaction.begin(next), std::invalid_argument);
    EXPECT_FALSE(transaction.has_pending());
  }
}

TEST(GamebubComposedTransaction, FinalLegalFrameDoesNotWrapOrAdmitReservedSentinel) {
  auto pair = c::parse_pair(packet());
  pair.frame = 0xfffffffeU;
  b::put32(pair.base, 10, pair.frame);
  b::put32(pair.base, 61 + 10, pair.frame);
  b::put32(pair.hud, 9, pair.frame);
  const auto last = reseal(pair);
  t::PendingPair transaction(1);
  transaction.begin(last);
  transaction.acknowledge(t::expected_ack(last));
  EXPECT_EQ(*transaction.acknowledged_frame(), 0xfffffffeU);
  EXPECT_THROW(transaction.begin(packet()), std::invalid_argument);
  EXPECT_THROW(transaction.begin(last), std::invalid_argument);
  pair.frame = 0xffffffffU;
  b::put32(pair.base, 10, pair.frame);
  b::put32(pair.base, 61 + 10, pair.frame);
  b::put32(pair.hud, 9, pair.frame);
  seal(std::span(pair.base).subspan(61, b::u32(pair.base, 52)));
  seal(pair.base);
  seal(pair.hud);
  EXPECT_THROW(c::serialize_pair(pair), std::invalid_argument);
  EXPECT_EQ(*transaction.acknowledged_frame(), 0xfffffffeU);
  EXPECT_FALSE(transaction.has_pending());
}
