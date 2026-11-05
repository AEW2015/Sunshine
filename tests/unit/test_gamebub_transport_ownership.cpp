/**
 * @file tests/unit/test_gamebub_transport_ownership.cpp
 * @brief Coupled epoch-one packet/frame ownership without network or physical-drain claims.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <cstdint>
#include <type_traits>
#include <vector>

// local includes
#include "tools/gamebub/native/transport_ownership.h"

namespace {
  namespace t = gamebub::v20::transport;

  /** @brief Use real frozen packet formats around deterministic non-codec payload bytes. */
  struct Sample {
    std::uint32_t id;  ///< Frame identity shared by request and chunks.
    std::vector<std::vector<std::uint8_t>> chunks;  ///< Actual GF03 datagrams.
    std::uint32_t total;  ///< Complete payload length, not a JPEG or CP23 assertion.
    std::uint32_t crc;  ///< Existing content checksum excluding the final four bytes.

    /** @brief Prepare one or more fixed-size chunks under the inherited epoch-one contract. */
    explicit Sample(std::uint32_t frame = 1, std::uint32_t bytes = 2 * t::payload_cap + 17):
        id(frame),
        total(bytes) {
      const std::vector<std::uint8_t> body(bytes, static_cast<std::uint8_t>(frame));
      chunks = t::datagrams(body, 1, frame);
      crc = t::parse_chunk(chunks.front()).content_crc;
    }
  };

  /** @brief Return one existing FG19 reply with exact CRC-bound request identity. */
  std::vector<std::uint8_t> response(t::FrameControl request, t::Kind kind) {
    request.kind = kind;
    if (kind == t::Kind::busy) {
      request.slot = t::no_slot;
    }
    return t::serialize(request);
  }

  /** @brief Grant an actual request without modeling decoder or physical receiver state. */
  t::FrameControl grant(t::SenderOwnership &owner, const Sample &sample) {
    const auto request = owner.request(sample.id, sample.total, sample.crc);
    EXPECT_TRUE(request);
    EXPECT_TRUE(owner.reply(response(request.value(), t::Kind::grant)));
    return t::parse_frame(response(request.value(), t::Kind::grant));
  }

  /** @brief Serialize an exact existing PC18 reply for a reserved packet token. */
  std::vector<std::uint8_t> credit(const t::Token &token, bool queried = false, std::uint8_t status = 0) {
    return t::serialize(t::PacketCredit {token.slot, queried, token.sequence, status, token.route_crc});
  }

  /** @brief Reserve, enqueue and return every DATA token through exact PC18 bytes. */
  void resolve(t::SenderOwnership &owner, const Sample &sample) {
    for (const auto &chunk : sample.chunks) {
      const auto outbound = owner.reserve(chunk);
      ASSERT_TRUE(outbound);
      ASSERT_TRUE(owner.mark_enqueued(outbound->token));
      ASSERT_TRUE(owner.credit(credit(outbound->token)).data_released);
    }
  }
}  // namespace

TEST(GamebubTransportOwnership, BoundedDefaultsAndInvalidRequestsNeverReserveMailbox) {
  static_assert(!std::is_copy_constructible_v<t::SenderOwnership>);
  static_assert(!std::is_move_constructible_v<t::SenderOwnership>);
  static_assert(!std::is_copy_assignable_v<t::SenderOwnership>);
  static_assert(!std::is_move_assignable_v<t::SenderOwnership>);
  EXPECT_THROW(t::SenderOwnership(4), std::invalid_argument);
  t::SenderOwnership owner;
  EXPECT_FALSE(owner.drain_evidence().drained());
  EXPECT_TRUE(owner.drain_evidence(true).drained());
  EXPECT_THROW(owner.request(0xffffffffU, 100, 0), std::invalid_argument);
  EXPECT_THROW(owner.request(1, 0, 0), std::invalid_argument);
  EXPECT_THROW(owner.request(1, t::frame_cap + 1, 0), std::invalid_argument);
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  EXPECT_FALSE(owner.finish(1));
  EXPECT_FALSE(owner.cancel(1));
  EXPECT_FALSE(owner.frame_stats(1));
}

TEST(GamebubTransportOwnership, RequestMailboxAndTwoFrameSlotsAreCoupled) {
  t::SenderOwnership owner;
  Sample a(1), b(2), c(3);
  const auto request = owner.request(a.id, a.total, a.crc);
  ASSERT_TRUE(request);
  EXPECT_TRUE(owner.snapshot().mailbox_owned);
  EXPECT_TRUE(owner.snapshot().frame_control_pending);
  EXPECT_FALSE(owner.drain_evidence(true).drained());
  EXPECT_FALSE(owner.request(b.id, b.total, b.crc));
  EXPECT_TRUE(owner.reply(response(*request, t::Kind::grant)));
  EXPECT_FALSE(owner.reply(response(*request, t::Kind::grant)));
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  EXPECT_EQ(owner.snapshot().registered_frames, 1);
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  EXPECT_FALSE(owner.request(a.id, a.total, a.crc));
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  grant(owner, b);
  EXPECT_FALSE(owner.request(c.id, c.total, c.crc));
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  EXPECT_EQ(owner.snapshot().registered_frames, 2);
}

TEST(GamebubTransportOwnership, BusyRequestReturnsOnlyControlMailboxAndInventsNoGrant) {
  t::SenderOwnership owner;
  Sample sample;
  const auto request = owner.request(sample.id, sample.total, sample.crc);
  ASSERT_TRUE(request);
  EXPECT_TRUE(owner.reply(response(*request, t::Kind::busy)));
  EXPECT_EQ(owner.snapshot().frame_owners, 0);
  EXPECT_EQ(owner.snapshot().registered_frames, 0);
  EXPECT_TRUE(owner.drain_evidence(true).drained());
  EXPECT_FALSE(owner.reserve(sample.chunks.front()));
  EXPECT_FALSE(owner.mark_enqueued({}));
}

TEST(GamebubTransportOwnership, MalformedAndWrongIdentityControlCannotMutateOwnership) {
  t::SenderOwnership owner;
  Sample sample;
  const auto request = owner.request(sample.id, sample.total, sample.crc);
  ASSERT_TRUE(request);
  auto bad = response(*request, t::Kind::grant);
  bad.back() ^= 1;
  EXPECT_THROW(owner.reply(bad), std::invalid_argument);
  auto wrong = *request;
  ++wrong.sequence;
  EXPECT_FALSE(owner.reply(response(wrong, t::Kind::grant)));
  EXPECT_FALSE(owner.reply(response(*request, t::Kind::finished)));
  EXPECT_EQ(owner.snapshot().frame_owners, 0);
  EXPECT_TRUE(owner.snapshot().frame_control_pending);
  EXPECT_TRUE(owner.reply(response(*request, t::Kind::grant)));
  auto foreign_epoch = sample.chunks.front();
  foreign_epoch[8] = 2;
  EXPECT_THROW(owner.reserve(foreign_epoch), std::invalid_argument);
  EXPECT_EQ(owner.snapshot().packet_owners, 0);
}

TEST(GamebubTransportOwnership, CancelRequiresNoReservedOrEverEnqueuedPacket) {
  t::SenderOwnership owner;
  Sample sample;
  grant(owner, sample);
  const auto reserved = owner.reserve(sample.chunks.front());
  ASSERT_TRUE(reserved);
  EXPECT_FALSE(owner.cancel(sample.id));
  EXPECT_TRUE(owner.cancel_unsent(reserved->token));
  EXPECT_FALSE(owner.cancel_unsent(reserved->token));
  const auto cancel = owner.cancel(sample.id);
  ASSERT_TRUE(cancel);
  EXPECT_FALSE(owner.reserve(sample.chunks.front()));
  EXPECT_FALSE(owner.mark_enqueued(reserved->token));
  EXPECT_FALSE(owner.cancel(sample.id));
  EXPECT_TRUE(owner.reply(response(*cancel, t::Kind::busy)));
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  const auto next = owner.reserve(sample.chunks.front());
  ASSERT_TRUE(next);
  EXPECT_TRUE(owner.mark_enqueued(next->token));
  EXPECT_FALSE(owner.mark_enqueued(next->token));
  EXPECT_FALSE(owner.cancel_unsent(next->token));
  EXPECT_FALSE(owner.cancel(sample.id));
  EXPECT_TRUE(owner.credit(credit(next->token)).data_released);
  EXPECT_FALSE(owner.cancel(sample.id));
}

TEST(GamebubTransportOwnership, CanceledReplyReleasesPacketAccountAndFrameTogether) {
  t::SenderOwnership owner;
  Sample sample;
  grant(owner, sample);
  const auto cancel = owner.cancel(sample.id);
  ASSERT_TRUE(cancel);
  EXPECT_FALSE(owner.reserve(sample.chunks.front()));
  EXPECT_TRUE(owner.reply(response(*cancel, t::Kind::canceled)));
  EXPECT_EQ(owner.snapshot().frame_owners, 0);
  EXPECT_EQ(owner.snapshot().registered_frames, 0);
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  EXPECT_TRUE(owner.drain_evidence(true).drained());
  EXPECT_FALSE(owner.reply(response(*cancel, t::Kind::canceled)));
}

TEST(GamebubTransportOwnership, FinishWaitsForEveryPacketAndOutstandingQueryReply) {
  t::SenderOwnership owner;
  Sample sample(1, 100);
  const auto granted = grant(owner, sample);
  EXPECT_FALSE(owner.finish(sample.id));
  const auto outbound = owner.reserve(sample.chunks.front());
  ASSERT_TRUE(outbound);
  EXPECT_FALSE(owner.finish(sample.id));
  ASSERT_TRUE(owner.mark_enqueued(outbound->token));
  EXPECT_FALSE(owner.finish(sample.id));
  const auto query = owner.query(outbound->token);
  ASSERT_TRUE(query);
  EXPECT_TRUE(owner.credit(credit(outbound->token)).data_released);
  EXPECT_EQ(owner.snapshot().packet_owners, 0);
  EXPECT_TRUE(owner.snapshot().mailbox_owned);
  EXPECT_FALSE(owner.finish(sample.id));
  EXPECT_FALSE(owner.reply(response(granted, t::Kind::release)));
  EXPECT_TRUE(owner.credit(credit(outbound->token, true)).query_released);
  const auto finish = owner.finish(sample.id);
  ASSERT_TRUE(finish);
  EXPECT_TRUE(owner.snapshot().mailbox_owned);
  EXPECT_FALSE(owner.finish(sample.id));
  EXPECT_FALSE(owner.reserve(sample.chunks.front()));
  EXPECT_TRUE(owner.reply(response(*finish, t::Kind::finished)));
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  EXPECT_EQ(owner.snapshot().registered_frames, 1);
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  EXPECT_FALSE(owner.drain_evidence(true).drained());
  EXPECT_TRUE(owner.reply(response(*finish, t::Kind::release)));
  EXPECT_EQ(owner.snapshot().registered_frames, 0);
  EXPECT_TRUE(owner.drain_evidence(true).drained());
  EXPECT_FALSE(owner.reply(response(*finish, t::Kind::release)));
}

TEST(GamebubTransportOwnership, RejectedPacketReceiptDoesNotPublishOrReleaseFrame) {
  t::SenderOwnership owner;
  Sample sample(1, 100);
  grant(owner, sample);
  const auto outbound = owner.reserve(sample.chunks.front());
  ASSERT_TRUE(outbound);
  ASSERT_TRUE(owner.mark_enqueued(outbound->token));
  const auto rejected = owner.credit(credit(outbound->token, false, 1));
  EXPECT_TRUE(rejected.data_released);
  EXPECT_TRUE(rejected.rejected);
  EXPECT_EQ(owner.frame_stats(sample.id)->rejected, 1);
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  EXPECT_FALSE(owner.drain_evidence(true).drained());
  EXPECT_TRUE(owner.finish(sample.id));
}

TEST(GamebubTransportOwnership, ReleaseOfOldFrameDoesNotFreeAnotherPendingMailbox) {
  t::SenderOwnership owner;
  Sample a(1), b(2);
  grant(owner, a);
  resolve(owner, a);
  const auto finish = owner.finish(a.id);
  ASSERT_TRUE(finish);
  ASSERT_TRUE(owner.reply(response(*finish, t::Kind::finished)));
  const auto other = owner.request(b.id, b.total, b.crc);
  ASSERT_TRUE(other);
  EXPECT_TRUE(owner.reply(response(*finish, t::Kind::release)));
  EXPECT_TRUE(owner.snapshot().frame_control_pending);
  EXPECT_TRUE(owner.snapshot().mailbox_owned);
  EXPECT_EQ(owner.snapshot().registered_frames, 0);
  EXPECT_FALSE(owner.drain_evidence(true).drained());
  EXPECT_TRUE(owner.reply(response(*other, t::Kind::grant)));
  EXPECT_EQ(owner.snapshot().registered_frames, 1);
}

TEST(GamebubTransportOwnership, QueryAndFrameControlShareTheSingleMailbox) {
  t::SenderOwnership owner;
  Sample a(1, 100), b(2, 100);
  grant(owner, a);
  const auto outbound = owner.reserve(a.chunks.front());
  ASSERT_TRUE(outbound);
  ASSERT_TRUE(owner.mark_enqueued(outbound->token));
  ASSERT_TRUE(owner.query(outbound->token));
  EXPECT_FALSE(owner.request(b.id, b.total, b.crc));
  const auto unknown = owner.credit(credit(outbound->token, true, 2));
  EXPECT_TRUE(unknown.unknown);
  EXPECT_TRUE(unknown.query_released);
  EXPECT_FALSE(unknown.data_released);
  const auto other = owner.request(b.id, b.total, b.crc);
  ASSERT_TRUE(other);
  EXPECT_FALSE(owner.query(outbound->token));
  EXPECT_TRUE(owner.reply(response(*other, t::Kind::busy)));
  EXPECT_TRUE(owner.query(outbound->token));
}

TEST(GamebubTransportOwnership, StickyStopRetainsUnknownOwnersButPermitsExactLateSettlement) {
  t::SenderOwnership owner;
  Sample sample(1, 100);
  const auto granted = grant(owner, sample);
  const auto outbound = owner.reserve(sample.chunks.front());
  ASSERT_TRUE(outbound);
  ASSERT_TRUE(owner.mark_enqueued(outbound->token));
  owner.stop();
  EXPECT_TRUE(owner.snapshot().stopped);
  EXPECT_EQ(owner.snapshot().packet_owners, 1);
  EXPECT_FALSE(owner.request(2, 100, 0));
  EXPECT_FALSE(owner.reserve(sample.chunks.front()));
  EXPECT_FALSE(owner.mark_enqueued(outbound->token));
  EXPECT_FALSE(owner.cancel_unsent(outbound->token));
  EXPECT_FALSE(owner.query(outbound->token));
  EXPECT_FALSE(owner.finish(sample.id));
  EXPECT_FALSE(owner.cancel(sample.id));
  EXPECT_TRUE(owner.credit(credit(outbound->token)).data_released);
  EXPECT_FALSE(owner.finish(sample.id));
  EXPECT_FALSE(owner.reply(response(granted, t::Kind::release)));
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  EXPECT_FALSE(owner.drain_evidence(true).drained());
}

TEST(GamebubTransportOwnership, LateGrantAfterStopRemainsAnOwnedFrameWithoutResuming) {
  t::SenderOwnership owner;
  Sample sample;
  const auto request = owner.request(sample.id, sample.total, sample.crc);
  ASSERT_TRUE(request);
  owner.stop();
  EXPECT_TRUE(owner.reply(response(*request, t::Kind::grant)));
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  EXPECT_EQ(owner.snapshot().registered_frames, 1);
  EXPECT_FALSE(owner.snapshot().mailbox_owned);
  EXPECT_FALSE(owner.reserve(sample.chunks.front()));
  EXPECT_FALSE(owner.cancel(sample.id));
  EXPECT_TRUE(owner.snapshot().stopped);
}

TEST(GamebubTransportOwnership, ExplicitLateReleaseCanDrainStoppedFinishedFrameWithoutResuming) {
  t::SenderOwnership owner;
  Sample sample;
  grant(owner, sample);
  resolve(owner, sample);
  const auto finish = owner.finish(sample.id);
  ASSERT_TRUE(finish);
  owner.stop();
  EXPECT_TRUE(owner.reply(response(*finish, t::Kind::finished)));
  EXPECT_EQ(owner.snapshot().frame_owners, 1);
  EXPECT_TRUE(owner.reply(response(*finish, t::Kind::release)));
  EXPECT_TRUE(owner.drain_evidence(true).drained());
  EXPECT_TRUE(owner.snapshot().stopped);
  EXPECT_FALSE(owner.request(2, 100, 0));
}

TEST(GamebubTransportOwnership, ResetEvidencePreservesIndependentExternalOwnersAndDrainSignal) {
  t::SenderOwnership owner;
  EXPECT_FALSE(owner.drain_evidence(false).drained());
  EXPECT_FALSE(owner.drain_evidence(true, 1).drained());
  EXPECT_FALSE(owner.drain_evidence(true, 0, 1).drained());
  EXPECT_FALSE(owner.drain_evidence(true, 0, 0, 1).drained());
  Sample sample;
  grant(owner, sample);
  const auto cancel = owner.cancel(sample.id);
  ASSERT_TRUE(cancel);
  EXPECT_FALSE(owner.drain_evidence(true).drained());
  EXPECT_TRUE(owner.reply(response(*cancel, t::Kind::canceled)));
  EXPECT_FALSE(owner.drain_evidence(false).drained());
  EXPECT_TRUE(owner.drain_evidence(true).drained());
}
