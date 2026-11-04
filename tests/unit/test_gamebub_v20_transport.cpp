/**
 * @file tests/unit/test_gamebub_v20_transport.cpp
 * @brief Exact laboratory wire and sender-owner regressions, without hardware drain claims.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <cstdint>
#include <limits>
#include <span>
#include <string>
#include <utility>
#include <vector>

// local includes
#include "tools/gamebub/native/transport.h"

namespace {
  namespace t = gamebub::v20::transport;

  /** @brief Decode explicit frozen hex without reading ignored laboratory artifacts. */
  std::vector<std::uint8_t> unhex(std::string_view value) {
    std::vector<std::uint8_t> out;
    for (std::size_t i = 0; i < value.size(); i += 2) {
      out.push_back(static_cast<std::uint8_t>(std::stoul(std::string(value.substr(i, 2)), nullptr, 16)));
    }
    return out;
  }

  /** @brief Change a control byte while keeping its independent outer CRC valid. */
  std::vector<std::uint8_t> changed(std::vector<std::uint8_t> bytes, unsigned at, std::uint8_t value) {
    bytes[at] = value;
    bytes.resize(bytes.size() - 4);
    return t::seal(std::move(bytes));
  }

  /** @brief Turn a sender intent into an otherwise-identical receiver response. */
  t::FrameControl response(t::FrameControl value, t::Kind kind) {
    value.kind = kind;
    if (kind == t::Kind::busy) {
      value.slot = t::no_slot;
    }
    return value;
  }

  /** @brief Issue and acknowledge one grant, leaving exact sender ownership. */
  t::FrameControl granted(t::SenderFrames &sender, std::uint32_t id) {
    auto request = sender.request(id, 4096, 0x12345678);
    EXPECT_TRUE(request.has_value());
    EXPECT_TRUE(sender.reply(response(*request, t::Kind::grant)));
    return *request;
  }
}  // namespace

TEST(GamebubV20Transport, FrozenControlPacketsMatchPinnedBigEndianBytes) {
  const auto fg = unhex("46473139010100000000000100000000000000000000000100006bb1b60d24b1e76b3e10");
  const auto control = t::parse_frame(fg);
  EXPECT_EQ(control, (t::FrameControl {t::Kind::request, 0, 1, 0, 1, 0x6bb1, 0xb60d24b1}));
  EXPECT_EQ(t::serialize(control), fg);
  const auto pc = unhex("504331380000000100000000000000000000000100dfb696c7cd094ba1");
  EXPECT_EQ(t::parse_credit(pc), (t::PacketCredit {0, false, 1, 0, 0xdfb696c7}));
  EXPECT_EQ(t::serialize(t::parse_credit(pc)), pc);
  const auto qc = unhex("5143313800000001000000000000000000000001dfb696c7e0db3b93");
  EXPECT_EQ(t::parse_query(qc), (t::CreditQuery {0, 1, 0xdfb696c7}));
  EXPECT_EQ(t::serialize(t::parse_query(qc)), qc);
}

TEST(GamebubV20Transport, ControlParsersRejectCrcSizeAndResealedProfileMutations) {
  const auto fg = t::serialize(t::FrameControl {t::Kind::request, 0, 1, 7, 1, 1008, 3});
  for (unsigned size = 0; size < fg.size(); ++size) {
    EXPECT_THROW(t::parse_frame(std::span(fg).first(size)), std::invalid_argument);
  }
  auto extra = fg;
  extra.push_back(0);
  EXPECT_THROW(t::parse_frame(extra), std::invalid_argument);
  auto corrupt = fg;
  corrupt.back() ^= 1;
  EXPECT_THROW(t::parse_frame(corrupt), std::invalid_argument);
  for (const auto &[offset, byte] : {std::pair {0U, 0U}, {4U, 2U}, {5U, 0U}, {5U, 9U}, {7U, 2U}, {11U, 2U}, {23U, 0U}, {26U, 0xffU}}) {
    EXPECT_THROW(t::parse_frame(changed(fg, offset, byte)), std::invalid_argument);
  }
  auto none = changed(changed(fg, 6, 255), 7, 255);
  EXPECT_THROW(t::parse_frame(none), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::FrameControl {t::Kind::busy, 0, 1, 1, 1, 1, 1}), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::FrameControl {t::Kind::grant, 0, 1, 1, 1, 0, 1}), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::FrameControl {t::Kind::grant, 0, 1, 1, 1, 49153, 1}), std::invalid_argument);
  EXPECT_NO_THROW(t::parse_frame(t::serialize(t::FrameControl {t::Kind::cancel, t::no_slot, 1, 0xffffffffU, 1, 49152, 0xffffffffU})));
  const auto pc = t::serialize(t::PacketCredit {5, true, 3, 2, 17});
  const auto qc = t::serialize(t::CreditQuery {5, 3, 17});
  EXPECT_EQ(t::parse_credit(pc), (t::PacketCredit {5, true, 3, 2, 17}));
  EXPECT_EQ(t::parse_query(qc), (t::CreditQuery {5, 3, 17}));
  for (const auto &[offset, byte] : {std::pair {7U, 2U}, {9U, 6U}, {11U, 2U}, {19U, 0U}, {20U, 3U}}) {
    EXPECT_THROW(t::parse_credit(changed(pc, offset, byte)), std::invalid_argument);
  }
  for (const auto &[offset, byte] : {std::pair {7U, 2U}, {9U, 6U}, {11U, 1U}, {19U, 0U}}) {
    EXPECT_THROW(t::parse_query(changed(qc, offset, byte)), std::invalid_argument);
  }
  EXPECT_THROW(t::parse_credit(qc), std::invalid_argument);
  EXPECT_THROW(t::parse_query(pc), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::PacketCredit {6, false, 1, 0, 0}), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::PacketCredit {0, false, 0, 0, 0}), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::PacketCredit {0, false, 1, 3, 0}), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::CreditQuery {6, 1, 0}), std::invalid_argument);
  EXPECT_THROW(t::serialize(t::CreditQuery {0, 0, 0}), std::invalid_argument);
}

TEST(GamebubV20Transport, ChunkGeometryAndWholeFrameChecksumsMatchReference) {
  std::vector<std::uint8_t> frame(2017);
  for (unsigned i = 0; i < frame.size(); ++i) {
    frame[i] = static_cast<std::uint8_t>(i);
  }
  const auto packets = t::datagrams(frame, 1, 9);
  ASSERT_EQ(packets.size(), 3);
  std::vector<std::uint8_t> rebuilt;
  for (unsigned i = 0; i < packets.size(); ++i) {
    const auto chunk = t::parse_chunk(packets[i]);
    EXPECT_EQ(chunk.epoch, 1);
    EXPECT_EQ(chunk.frame, 9);
    EXPECT_EQ(chunk.total, frame.size());
    EXPECT_EQ(chunk.index, i);
    EXPECT_EQ(chunk.count, packets.size());
    EXPECT_EQ(chunk.whole_crc, gamebub::v20::crc32(frame));
    EXPECT_EQ(chunk.content_crc, gamebub::v20::crc32(std::span(frame).first(frame.size() - 4)));
    EXPECT_EQ(t::serialize(chunk), packets[i]);
    rebuilt.insert(rebuilt.end(), chunk.payload.begin(), chunk.payload.end());
  }
  EXPECT_EQ(rebuilt, frame);
  EXPECT_EQ(t::parse_chunk(packets.back()).payload.size(), 1);
  const std::array<std::uint8_t, 3> short_frame {1, 2, 3};
  EXPECT_EQ(t::parse_chunk(t::datagrams(short_frame, 0, 0)[0]).content_crc, 0);
  EXPECT_THROW(t::datagrams({}, 1, 1), std::invalid_argument);
  EXPECT_THROW(t::datagrams(std::vector<std::uint8_t>(49153), 1, 1), std::invalid_argument);
  EXPECT_THROW(t::datagrams(short_frame, 0xffffffffU, 1), std::invalid_argument);
  EXPECT_THROW(t::datagrams(short_frame, 1, 0xffffffffU), std::invalid_argument);
  EXPECT_EQ(t::datagrams(std::vector<std::uint8_t>(49152), 1, 1).size(), 49);
}

TEST(GamebubV20Transport, ChunkAndWrapperRejectMalformedGeometryWithoutClaimingPayloadIntegrity) {
  auto packet = t::datagrams(std::vector<std::uint8_t>(1009, 17), 1, 4)[0];
  EXPECT_THROW(t::parse_chunk(std::span(packet).first(30)), std::invalid_argument);
  for (const auto &[offset, byte] : {std::pair {0U, 0U}, {4U, 2U}, {13U, 1U}, {18U, 2U}, {20U, 3U}, {22U, 0U}}) {
    auto bad = packet;
    bad[offset] = byte;
    EXPECT_THROW(t::parse_chunk(bad), std::invalid_argument);
  }
  auto trailing = packet;
  trailing.push_back(0);
  EXPECT_THROW(t::parse_chunk(trailing), std::invalid_argument);
  auto changed_payload = packet;
  changed_payload.back() ^= 1;
  EXPECT_NO_THROW(t::parse_chunk(changed_payload));  // GF03 has no per-packet payload CRC.
  auto bad_view = t::parse_chunk(packet);
  bad_view.payload = {};
  EXPECT_THROW(t::serialize(bad_view), std::invalid_argument);
  const auto wrapped = t::wrap(packet, 5, 12);
  const auto parsed = t::unwrap(wrapped);
  EXPECT_EQ(parsed.slot, 5);
  EXPECT_EQ(parsed.sequence, 12);
  EXPECT_EQ(parsed.route_crc, gamebub::v20::crc32(std::span(wrapped).first(47)));
  EXPECT_EQ(t::serialize(parsed.chunk), packet);
  EXPECT_THROW(t::unwrap(std::span(wrapped).first(46)), std::invalid_argument);
  EXPECT_THROW(t::unwrap(std::vector<std::uint8_t>(1065)), std::invalid_argument);
  for (const auto &[offset, byte] : {std::pair {3U, 2U}, {5U, 6U}, {7U, 1U}, {15U, 0U}}) {
    auto bad = wrapped;
    bad[offset] = byte;
    EXPECT_THROW(t::unwrap(bad), std::invalid_argument);
  }
  EXPECT_THROW(t::wrap(packet, 6, 1), std::invalid_argument);
  EXPECT_THROW(t::wrap(packet, 0, 0), std::invalid_argument);
  EXPECT_THROW(t::wrap(t::datagrams(std::vector<std::uint8_t>(1), 2, 0)[0], 0, 1), std::invalid_argument);
}

TEST(GamebubV20Transport, IntegerHelpersRejectOverflowAndBounds) {
  std::vector<std::uint8_t> out;
  EXPECT_THROW(t::append(out, 256, 1), std::invalid_argument);
  EXPECT_THROW(t::append(out, 0, 0), std::invalid_argument);
  EXPECT_THROW(t::append(out, 0, 9), std::invalid_argument);
  t::append(out, std::numeric_limits<std::uint64_t>::max(), 8);
  EXPECT_EQ(t::read(out, 0, 8), std::numeric_limits<std::uint64_t>::max());
  EXPECT_THROW(t::read(out, 9, 1), std::invalid_argument);
  EXPECT_THROW(t::read(out, 7, 2), std::invalid_argument);
  EXPECT_THROW(t::read(out, 0, 9), std::invalid_argument);
  EXPECT_FALSE(t::magic({}, "GF03"));
}

TEST(GamebubV20Transport, FinishedFreesControlOnlyAndReleaseFreesExactSlot) {
  t::SenderFrames sender;
  const auto first = granted(sender, 1);
  EXPECT_EQ(sender.owned(), 1);
  EXPECT_FALSE(sender.pending());
  EXPECT_FALSE(sender.reply(response(first, t::Kind::release)));
  const auto finish = sender.control(1, t::Kind::finish);
  ASSERT_TRUE(finish);
  EXPECT_TRUE(sender.pending());
  EXPECT_EQ(sender.owned(), 1);
  EXPECT_FALSE(sender.control(1, t::Kind::finish));
  EXPECT_FALSE(sender.reply(response(*finish, t::Kind::busy)));
  EXPECT_FALSE(sender.reply(response(*finish, t::Kind::release)));
  EXPECT_TRUE(sender.reply(response(*finish, t::Kind::finished)));
  EXPECT_FALSE(sender.pending());
  EXPECT_EQ(sender.owned(), 1);
  EXPECT_FALSE(sender.control(1, t::Kind::finish));
  EXPECT_TRUE(sender.reply(response(first, t::Kind::release)));
  EXPECT_EQ(sender.owned(), 0);
  EXPECT_FALSE(sender.reply(response(first, t::Kind::release)));
}

TEST(GamebubV20Transport, WrongRepliesCannotResolvePendingOrReleaseAnotherSlot) {
  t::SenderFrames sender;
  const auto pending = sender.request(10, 20, 30);
  ASSERT_TRUE(pending);
  EXPECT_FALSE(sender.request(11, 20, 30));
  EXPECT_FALSE(sender.control(10, t::Kind::finish));
  EXPECT_FALSE(sender.reply(response(*pending, t::Kind::finished)));
  auto wrong = response(*pending, t::Kind::grant);
  wrong.slot = 1;
  EXPECT_FALSE(sender.reply(wrong));
  wrong = response(*pending, t::Kind::grant);
  ++wrong.sequence;
  EXPECT_FALSE(sender.reply(wrong));
  wrong = response(*pending, t::Kind::grant);
  ++wrong.content_crc;
  EXPECT_FALSE(sender.reply(wrong));
  EXPECT_EQ(sender.owned(), 0);
  EXPECT_EQ(sender.pending(), pending);
  EXPECT_TRUE(sender.reply(response(*pending, t::Kind::grant)));
  EXPECT_FALSE(sender.request(10, 20, 30));
  const auto second = granted(sender, 11);
  EXPECT_EQ(second.slot, 1);
  EXPECT_GT(second.sequence, pending->sequence);
  EXPECT_EQ(sender.owned(), 2);
  EXPECT_FALSE(sender.request(12, 20, 30));
  EXPECT_FALSE(sender.control(12, t::Kind::cancel));
  EXPECT_THROW(sender.control(10, t::Kind::request), std::invalid_argument);
  EXPECT_FALSE(sender.reply(response(second, t::Kind::grant)));
}

TEST(GamebubV20Transport, CancelBusyAndUnknownOutcomesPreserveOwners) {
  t::SenderFrames sender;
  auto request = sender.request(1, 1, 0);
  ASSERT_TRUE(request);
  EXPECT_TRUE(sender.reply(response(*request, t::Kind::busy)));
  EXPECT_EQ(sender.owned(), 0);
  EXPECT_FALSE(sender.pending());
  const auto first = granted(sender, 2);
  auto cancel = sender.control(2, t::Kind::cancel);
  ASSERT_TRUE(cancel);
  auto wrong = response(*cancel, t::Kind::canceled);
  wrong.slot = 1;
  EXPECT_FALSE(sender.reply(wrong));
  EXPECT_TRUE(sender.reply(response(*cancel, t::Kind::busy)));
  EXPECT_EQ(sender.owned(), 1);
  cancel = sender.control(2, t::Kind::cancel);
  ASSERT_TRUE(cancel);
  EXPECT_TRUE(sender.reply(response(*cancel, t::Kind::canceled)));
  EXPECT_EQ(sender.owned(), 0);
  EXPECT_FALSE(sender.reply(response(first, t::Kind::release)));
  const auto next = granted(sender, 3);
  const auto finish = sender.control(3, t::Kind::finish);
  ASSERT_TRUE(finish);
  sender.stop();  // A timeout is not proof that the receiver released frame storage.
  EXPECT_TRUE(sender.stopped());
  EXPECT_EQ(sender.pending(), finish);
  EXPECT_EQ(sender.owned(), 1);
  EXPECT_FALSE(sender.request(4, 1, 0));
  EXPECT_FALSE(sender.control(3, t::Kind::cancel));
  EXPECT_TRUE(sender.reply(response(*finish, t::Kind::finished)));
  EXPECT_TRUE(sender.reply(response(next, t::Kind::release)));
  EXPECT_TRUE(sender.stopped());
  EXPECT_EQ(sender.owned(), 0);
}

TEST(GamebubV20Transport, InvalidIntentIsAtomicAndIndependentSlotReleasePreservesPending) {
  t::SenderFrames sender;
  EXPECT_THROW(sender.request(1, 0, 0), std::invalid_argument);
  EXPECT_EQ(sender.owned(), 0);
  EXPECT_FALSE(sender.pending());
  const auto first = granted(sender, 1);
  EXPECT_EQ(first.sequence, 1);
  const auto finish = sender.control(1, t::Kind::finish);
  ASSERT_TRUE(finish);
  EXPECT_TRUE(sender.reply(response(*finish, t::Kind::finished)));
  const auto pending = sender.request(2, 16, 17);
  ASSERT_TRUE(pending);
  auto wrong = response(first, t::Kind::release);
  wrong.slot = 1;
  EXPECT_FALSE(sender.reply(wrong));
  EXPECT_TRUE(sender.reply(response(first, t::Kind::release)));
  EXPECT_EQ(sender.pending(), pending);
  EXPECT_TRUE(sender.reply(response(*pending, t::Kind::grant)));
  EXPECT_EQ(sender.owned(), 1);
}
