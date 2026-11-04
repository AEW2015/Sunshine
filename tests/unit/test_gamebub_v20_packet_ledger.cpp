/**
 * @file tests/unit/test_gamebub_v20_packet_ledger.cpp
 * @brief Bounded DATA/control ownership and exact PC18/QC18 identity regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <cstdint>
#include <limits>
#include <type_traits>
#include <vector>

// local includes
#include "tools/gamebub/native/packet_ledger.h"

namespace {
  namespace t = gamebub::v20::transport;

  /** @brief Generate actual GF03 chunks and their separately granted route declaration. */
  struct Sample {
    std::vector<std::vector<std::uint8_t>> chunks;  ///< Exact wire datagrams, not synthetic counts.
    t::FrameControl grant;  ///< Model grant; tests do not establish a live receiver grant.

    /** @brief Bind deterministic bytes to one frame identity and frozen fragment geometry. */
    explicit Sample(std::uint32_t frame = 1, unsigned total = 100) {
      std::vector<std::uint8_t> body(total);
      for (unsigned i = 0; i < total; ++i) {
        body[i] = static_cast<std::uint8_t>(i + frame);
      }
      chunks = t::datagrams(body, 1, frame);
      grant = {t::Kind::grant, static_cast<std::uint16_t>(frame % 2), 1, frame, frame + 1, total, t::parse_chunk(chunks[0]).content_crc};
    }
  };

  /** @brief Reserve and conservatively enqueue an exact datagram before receiver replies. */
  t::Outbound queued(t::PacketLedger &ledger, const std::vector<std::uint8_t> &packet) {
    auto outbound = ledger.reserve(packet);
    EXPECT_TRUE(outbound.has_value());
    EXPECT_TRUE(ledger.mark_enqueued(outbound.value().token));
    return std::move(outbound.value());
  }

  /** @brief Exercise the actual PC18 serializer/parser before applying a receipt. */
  t::PacketCredit receipt(const t::Token &token, unsigned status = 0, bool queried = false) {
    return t::parse_credit(t::serialize(t::PacketCredit {token.slot, queried, token.sequence, static_cast<std::uint8_t>(status), token.route_crc}));
  }
}  // namespace

TEST(GamebubV20PacketLedger, QueryConfigurationAndSequencesNeverWrap) {
  static_assert(std::is_default_constructible_v<t::PacketLedger>);
  static_assert(!std::is_copy_constructible_v<t::PacketLedger>);
  static_assert(!std::is_move_constructible_v<t::PacketLedger>);
  static_assert(!std::is_copy_assignable_v<t::PacketLedger>);
  static_assert(!std::is_move_assignable_v<t::PacketLedger>);
  static_assert(std::is_default_constructible_v<t::SenderFrames>);
  static_assert(!std::is_copy_constructible_v<t::SenderFrames>);
  static_assert(!std::is_move_constructible_v<t::SenderFrames>);
  static_assert(!std::is_copy_assignable_v<t::SenderFrames>);
  static_assert(!std::is_move_assignable_v<t::SenderFrames>);
  EXPECT_EQ(t::next_packet_sequence(0), 1);
  EXPECT_EQ(t::next_packet_sequence(std::numeric_limits<std::uint64_t>::max() - 1), std::numeric_limits<std::uint64_t>::max());
  EXPECT_FALSE(t::next_packet_sequence(std::numeric_limits<std::uint64_t>::max()));
  EXPECT_THROW(t::PacketLedger(4), std::invalid_argument);
  t::PacketLedger ledger(0);
  Sample sample;
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  const auto outbound = queued(ledger, sample.chunks[0]);
  EXPECT_FALSE(ledger.query(outbound.token));
  EXPECT_EQ(ledger.frame_stats(1)->queries, 0);
}

TEST(GamebubV20PacketLedger, FrameAccountsAreBoundedAndDoNotInventGrants) {
  t::PacketLedger ledger;
  for (unsigned id = 1; id <= 3; ++id) {
    EXPECT_TRUE(ledger.register_frame(Sample(id).grant));
  }
  EXPECT_EQ(ledger.registered_frames(), 3);
  EXPECT_FALSE(ledger.register_frame(Sample(4).grant));
  EXPECT_FALSE(ledger.register_frame(Sample(1).grant));
  auto bad = Sample(4).grant;
  bad.kind = t::Kind::request;
  EXPECT_THROW(ledger.register_frame(bad), std::invalid_argument);
  bad = Sample(4).grant;
  bad.frame = 0xffffffffU;
  EXPECT_THROW(ledger.register_frame(bad), std::invalid_argument);
  bad = Sample(4).grant;
  bad.epoch = 0;
  EXPECT_THROW(ledger.register_frame(bad), std::invalid_argument);
  EXPECT_FALSE(ledger.frame_stats(99));
  EXPECT_FALSE(ledger.may_cancel(99));
  EXPECT_FALSE(ledger.packets_resolved(99));
  EXPECT_FALSE(ledger.forget_frame(99));
  for (unsigned id = 1; id <= 3; ++id) {
    EXPECT_TRUE(ledger.may_cancel(id));
    EXPECT_TRUE(ledger.forget_frame(id));
  }
  EXPECT_EQ(ledger.registered_frames(), 0);
}

TEST(GamebubV20PacketLedger, FiveDataSlotsLeaveOneSharedControlMailbox) {
  t::PacketLedger ledger;
  Sample sample(1, 6100);
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  std::vector<t::Outbound> data;
  for (unsigned i = 0; i < 5; ++i) {
    data.push_back(ledger.reserve(sample.chunks[i]).value());
    EXPECT_EQ(data.back().token.slot, i);
    const auto wrapped = t::unwrap(data.back().bytes);
    EXPECT_EQ(wrapped.sequence, data.back().token.sequence);
    EXPECT_EQ(wrapped.route_crc, data.back().token.route_crc);
  }
  EXPECT_EQ(ledger.owned_data(), 5);
  EXPECT_FALSE(ledger.reserve(sample.chunks[5]));
  auto control = ledger.acquire_control();
  ASSERT_TRUE(control);
  EXPECT_TRUE(ledger.mailbox_owned());
  EXPECT_FALSE(ledger.acquire_control());
  EXPECT_FALSE(ledger.query(data[0].token));
  EXPECT_FALSE(ledger.release_control({control->generation + 1}));
  EXPECT_TRUE(ledger.release_control(*control));
  EXPECT_FALSE(ledger.release_control(*control));
  ASSERT_TRUE(ledger.mark_enqueued(data[0].token));
  auto query = ledger.query(data[0].token);
  ASSERT_TRUE(query);
  EXPECT_EQ(t::parse_query(t::serialize(*query)), *query);
  EXPECT_FALSE(ledger.acquire_control());
  EXPECT_FALSE(ledger.release_control(*control));
  const auto unknown = ledger.credit(receipt(data[0].token, 2, true));
  EXPECT_TRUE(unknown.query_released);
  EXPECT_TRUE(unknown.unknown);
  EXPECT_FALSE(unknown.data_released);
  EXPECT_EQ(ledger.owned_data(), 5);
  EXPECT_FALSE(ledger.cancel_unsent(data[0].token));
  for (unsigned i = 1; i < 5; ++i) {
    EXPECT_TRUE(ledger.cancel_unsent(data[i].token));
  }
  EXPECT_EQ(ledger.owned_data(), 1);
}

TEST(GamebubV20PacketLedger, UnsentCancellationConsumesGenerationAndCannotCancelEnqueuedData) {
  t::PacketLedger ledger;
  Sample sample;
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  auto first = ledger.reserve(sample.chunks[0]).value();
  EXPECT_FALSE(ledger.may_cancel(1));
  auto forged = first.token;
  forged.frame = 99;
  EXPECT_FALSE(ledger.mark_enqueued(forged));
  EXPECT_FALSE(ledger.cancel_unsent(forged));
  forged = first.token;
  forged.slot = 5;
  EXPECT_FALSE(ledger.mark_enqueued(forged));
  EXPECT_TRUE(ledger.cancel_unsent(first.token));
  EXPECT_TRUE(ledger.may_cancel(1));
  EXPECT_FALSE(ledger.cancel_unsent(first.token));
  auto second = ledger.reserve(sample.chunks[0]).value();
  EXPECT_EQ(second.token.slot, first.token.slot);
  EXPECT_EQ(second.token.sequence, first.token.sequence + 1);
  EXPECT_FALSE(ledger.credit(receipt(first.token)).data_released);
  EXPECT_FALSE(ledger.credit(receipt(second.token)).data_released);
  EXPECT_FALSE(ledger.query(second.token));
  EXPECT_TRUE(ledger.mark_enqueued(second.token));
  EXPECT_FALSE(ledger.mark_enqueued(second.token));
  EXPECT_FALSE(ledger.cancel_unsent(second.token));
  EXPECT_TRUE(ledger.credit(receipt(second.token)).data_released);
  EXPECT_TRUE(ledger.packets_resolved(1));
  EXPECT_FALSE(ledger.may_cancel(1));
  EXPECT_TRUE(ledger.forget_frame(1));
}

TEST(GamebubV20PacketLedger, ReceiptsBindExactRouteSequenceAndStatusWithoutFrameAcceptance) {
  t::PacketLedger ledger;
  Sample sample;
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  const auto outbound = queued(ledger, sample.chunks[0]);
  auto wrong = receipt(outbound.token);
  wrong.route_crc ^= 1;
  EXPECT_FALSE(ledger.credit(wrong).data_released);
  wrong = receipt(outbound.token);
  ++wrong.sequence;
  EXPECT_FALSE(ledger.credit(wrong).data_released);
  wrong = receipt(outbound.token);
  wrong.slot = 1;
  EXPECT_FALSE(ledger.credit(wrong).data_released);
  wrong.slot = 5;
  EXPECT_FALSE(ledger.credit(wrong).data_released);
  wrong.slot = 6;
  EXPECT_THROW(ledger.credit(wrong), std::invalid_argument);
  wrong = receipt(outbound.token);
  wrong.sequence = 0;
  EXPECT_THROW(ledger.credit(wrong), std::invalid_argument);
  wrong = receipt(outbound.token);
  wrong.status = 3;
  EXPECT_THROW(ledger.credit(wrong), std::invalid_argument);
  auto malformed = t::serialize(receipt(outbound.token));
  malformed.back() ^= 1;
  EXPECT_THROW(t::parse_credit(malformed), std::invalid_argument);
  EXPECT_EQ(ledger.owned_data(), 1);
  const auto unknown = ledger.credit(receipt(outbound.token, 2));
  EXPECT_TRUE(unknown.unknown);
  EXPECT_FALSE(unknown.data_released);
  const auto rejected = ledger.credit(receipt(outbound.token, 1));
  EXPECT_TRUE(rejected.data_released);
  EXPECT_TRUE(rejected.rejected);
  EXPECT_FALSE(ledger.credit(receipt(outbound.token, 1)).data_released);
  EXPECT_EQ(ledger.frame_stats(1)->rejected, 1);
  EXPECT_EQ(ledger.frame_stats(1)->resolved, 1);
}

TEST(GamebubV20PacketLedger, QueryAndDataReceiptsReleaseIndependentOwnersAndBoundRetries) {
  t::PacketLedger ledger;
  Sample sample(1, 2000);
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  const auto first = queued(ledger, sample.chunks[0]);
  const auto second = queued(ledger, sample.chunks[1]);
  ASSERT_TRUE(ledger.query(first.token));
  EXPECT_FALSE(ledger.query(second.token));
  auto wrong = receipt(first.token, 0, true);
  ++wrong.route_crc;
  EXPECT_FALSE(ledger.credit(wrong).query_released);
  const auto original = ledger.credit(receipt(first.token));
  EXPECT_TRUE(original.data_released);
  EXPECT_FALSE(original.query_released);
  EXPECT_TRUE(ledger.mailbox_owned());
  EXPECT_FALSE(ledger.forget_frame(1));
  EXPECT_TRUE(ledger.credit(receipt(first.token, 2, true)).query_released);
  EXPECT_FALSE(ledger.mailbox_owned());
  ASSERT_TRUE(ledger.query(second.token));
  const auto unknown = ledger.credit(receipt(second.token, 2, true));
  EXPECT_TRUE(unknown.query_released);
  EXPECT_TRUE(unknown.unknown);
  EXPECT_EQ(ledger.owned_data(), 1);
  ASSERT_TRUE(ledger.query(second.token));
  EXPECT_TRUE(ledger.credit(receipt(second.token)).data_released);
  EXPECT_TRUE(ledger.packets_resolved(1));
  EXPECT_FALSE(ledger.forget_frame(1));
  EXPECT_TRUE(ledger.credit(receipt(second.token, 0, true)).query_released);
  EXPECT_FALSE(ledger.query(second.token));
  EXPECT_EQ(ledger.frame_stats(1)->queries, 3);
  EXPECT_TRUE(ledger.forget_frame(1));

  t::PacketLedger bounded(1);
  ASSERT_TRUE(bounded.register_frame(sample.grant));
  const auto missing = queued(bounded, sample.chunks[0]);
  ASSERT_TRUE(bounded.query(missing.token));
  EXPECT_TRUE(bounded.credit(receipt(missing.token, 2, true)).query_released);
  EXPECT_FALSE(bounded.query(missing.token));
  EXPECT_EQ(bounded.owned_data(), 1);
}

TEST(GamebubV20PacketLedger, FrameControlPermitIsGenerationBoundAndCannotBeReleasedByPc18) {
  t::PacketLedger ledger;
  Sample sample;
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  const auto data = queued(ledger, sample.chunks[0]);
  auto control = ledger.acquire_control().value();
  EXPECT_FALSE(ledger.query(data.token));
  EXPECT_FALSE(ledger.release_control({0}));
  EXPECT_TRUE(ledger.credit(receipt(data.token, 0, true)).data_released);
  EXPECT_TRUE(ledger.mailbox_owned());
  EXPECT_TRUE(ledger.release_control(control));
  const auto next = ledger.acquire_control().value();
  EXPECT_GT(next.generation, control.generation);
  EXPECT_FALSE(ledger.release_control(control));
  EXPECT_TRUE(ledger.release_control(next));
}

TEST(GamebubV20PacketLedger, LateQueryResponseCannotFreeNewDataGenerationInReusedSlot) {
  t::PacketLedger ledger;
  Sample sample(1, 2000);
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  const auto first = queued(ledger, sample.chunks[0]);
  ASSERT_TRUE(ledger.query(first.token));
  ASSERT_TRUE(ledger.credit(receipt(first.token)).data_released);
  const auto second = queued(ledger, sample.chunks[1]);
  EXPECT_EQ(first.token.slot, second.token.slot);
  EXPECT_GT(second.token.sequence, first.token.sequence);
  const auto late = ledger.credit(receipt(first.token, 0, true));
  EXPECT_TRUE(late.query_released);
  EXPECT_FALSE(late.data_released);
  EXPECT_EQ(ledger.owned_data(), 1);
  EXPECT_FALSE(ledger.credit(receipt(first.token, 0, true)).data_released);
  EXPECT_TRUE(ledger.credit(receipt(second.token)).data_released);
  EXPECT_TRUE(ledger.packets_resolved(1));
}

TEST(GamebubV20PacketLedger, StopRetainsUnknownReservationsAndAllowsOnlyExactLateReceipts) {
  t::PacketLedger ledger;
  Sample sample(1, 3000);
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  const auto sent = queued(ledger, sample.chunks[0]);
  const auto unsent = ledger.reserve(sample.chunks[1]).value();
  ASSERT_TRUE(ledger.query(sent.token));
  ledger.stop();
  EXPECT_TRUE(ledger.stopped());
  EXPECT_EQ(ledger.owned_data(), 2);
  EXPECT_TRUE(ledger.mailbox_owned());
  EXPECT_FALSE(ledger.reserve(sample.chunks[2]));
  EXPECT_FALSE(ledger.register_frame(Sample(2).grant));
  EXPECT_FALSE(ledger.mark_enqueued(unsent.token));
  EXPECT_FALSE(ledger.cancel_unsent(unsent.token));
  EXPECT_FALSE(ledger.acquire_control());
  EXPECT_FALSE(ledger.query(sent.token));
  EXPECT_FALSE(ledger.forget_frame(1));
  EXPECT_TRUE(ledger.credit(receipt(sent.token, 2, true)).query_released);
  EXPECT_EQ(ledger.owned_data(), 2);
  EXPECT_TRUE(ledger.credit(receipt(sent.token)).data_released);
  EXPECT_EQ(ledger.owned_data(), 1);
  EXPECT_FALSE(ledger.credit(receipt(unsent.token)).data_released);
  EXPECT_TRUE(ledger.stopped());
}

TEST(GamebubV20PacketLedger, FinishEligibilityRequiresEveryUniqueFragmentAndKeepsFramesIndependent) {
  t::PacketLedger ledger;
  Sample first(1, 2000), second(2);
  ASSERT_TRUE(ledger.register_frame(first.grant));
  ASSERT_TRUE(ledger.register_frame(second.grant));
  const auto a = queued(ledger, first.chunks[0]);
  const auto b = queued(ledger, second.chunks[0]);
  EXPECT_TRUE(ledger.credit(receipt(a.token)).data_released);
  EXPECT_FALSE(ledger.packets_resolved(1));
  EXPECT_FALSE(ledger.forget_frame(1));
  EXPECT_TRUE(ledger.credit(receipt(b.token)).data_released);
  EXPECT_TRUE(ledger.packets_resolved(2));
  EXPECT_TRUE(ledger.forget_frame(2));
  const auto last = queued(ledger, first.chunks[1]);
  EXPECT_FALSE(ledger.packets_resolved(1));
  EXPECT_TRUE(ledger.credit(receipt(last.token)).data_released);
  EXPECT_TRUE(ledger.packets_resolved(1));
  EXPECT_EQ(ledger.frame_stats(1)->fragments, 2);
  EXPECT_EQ(ledger.frame_stats(1)->enqueued, 2);
  EXPECT_EQ(ledger.frame_stats(1)->resolved, 2);
  EXPECT_TRUE(ledger.forget_frame(1));
  EXPECT_EQ(ledger.registered_frames(), 0);
}

TEST(GamebubV20PacketLedger, RoutesAndDuplicatesCannotConsumeAdditionalPermits) {
  t::PacketLedger ledger;
  Sample sample;
  EXPECT_THROW(ledger.reserve(sample.chunks[0]), std::invalid_argument);
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  auto wrong = t::parse_chunk(sample.chunks[0]);
  wrong.epoch = 0;
  EXPECT_THROW(ledger.reserve(t::serialize(wrong)), std::invalid_argument);
  wrong = t::parse_chunk(sample.chunks[0]);
  ++wrong.content_crc;
  EXPECT_THROW(ledger.reserve(t::serialize(wrong)), std::invalid_argument);
  Sample different(1, 200);
  EXPECT_THROW(ledger.reserve(different.chunks[0]), std::invalid_argument);
  EXPECT_THROW(ledger.reserve({}), std::invalid_argument);
  const auto reserved = ledger.reserve(sample.chunks[0]).value();
  EXPECT_FALSE(ledger.reserve(sample.chunks[0]));
  ASSERT_TRUE(ledger.mark_enqueued(reserved.token));
  EXPECT_FALSE(ledger.reserve(sample.chunks[0]));
  EXPECT_TRUE(ledger.credit(receipt(reserved.token)).data_released);
  EXPECT_FALSE(ledger.reserve(sample.chunks[0]));
  EXPECT_EQ(ledger.owned_data(), 0);
}

TEST(GamebubV20PacketLedger, MaximumFrameCompletesWithoutReusingHeldStorageOrAcknowledgingDecode) {
  t::PacketLedger ledger;
  Sample sample(1, t::frame_cap);
  t::SenderFrames frame_owners;
  auto request = frame_owners.request(1, sample.grant.total, sample.grant.content_crc).value();
  sample.grant = request;
  sample.grant.kind = t::Kind::grant;
  ASSERT_TRUE(frame_owners.reply(sample.grant));
  ASSERT_TRUE(ledger.register_frame(sample.grant));
  EXPECT_EQ(sample.chunks.size(), 49);
  for (const auto &chunk : sample.chunks) {
    const auto data = queued(ledger, chunk);
    EXPECT_TRUE(ledger.credit(receipt(data.token)).data_released);
  }
  EXPECT_TRUE(ledger.packets_resolved(1));
  EXPECT_EQ(ledger.owned_data(), 0);
  EXPECT_EQ(frame_owners.owned(), 1);
  auto finish = frame_owners.control(1, t::Kind::finish).value();
  finish.kind = t::Kind::finished;
  EXPECT_TRUE(frame_owners.reply(finish));
  EXPECT_EQ(frame_owners.owned(), 1);
  finish.kind = t::Kind::release;
  EXPECT_TRUE(frame_owners.reply(finish));
  EXPECT_EQ(frame_owners.owned(), 0);
  EXPECT_TRUE(ledger.forget_frame(1));
}
