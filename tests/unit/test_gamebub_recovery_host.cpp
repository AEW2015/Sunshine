/**
 * @file tests/unit/test_gamebub_recovery_host.cpp
 * @brief Offline RS24 phase, bounded retry and explicit ownership regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <cstdint>
#include <limits>
#include <type_traits>
#include <vector>

// local includes
#include "tools/gamebub/native/packet_ledger.h"
#include "tools/gamebub/native/recovery_host.h"

namespace {
  namespace r = gamebub::v24::recovery;
  namespace t = gamebub::v20::transport;

  /** @brief Explicit modeled drain; no test here observes actual hardware/DMA completion. */
  constexpr r::DrainEvidence drained {true};

  /** @brief Build one exact matching reply without implementing a receiver state machine. */
  std::array<std::uint8_t, r::control_bytes> reply(const r::Host &host, r::Kind kind) {
    auto value = r::parse(host.outstanding().value());
    value.kind = kind;
    if (kind == r::Kind::hello_reply) {
      value.target_nonce = 202;
    }
    return r::serialize(value);
  }

  /** @brief Move through HELLO to an outstanding OFFER using explicitly modeled drain. */
  void offer(r::Host &host) {
    host.start(drained);
    host.accept(reply(host, r::Kind::hello_reply), drained);
  }

  /** @brief Complete the exact four host stages using a reply oracle, not a target decoder. */
  void running(r::Host &host) {
    offer(host);
    host.accept(reply(host, r::Kind::ready), drained);
    host.accept(reply(host, r::Kind::committed), drained);
    host.accept(reply(host, r::Kind::go_ack), drained);
  }

  /** @brief Enumerate each independently blocking owner and absent explicit drain. */
  std::array<r::DrainEvidence, 7> blockers() {
    std::array<r::DrainEvidence, 7> values;
    values.fill(drained);
    values[0].transport_drained = false;
    values[1].source_owners = 1;
    values[2].candidate_owners = 1;
    values[3].reference_readers = 1;
    values[4].frame_owners = 1;
    values[5].packet_owners = 1;
    values[6].control_owners = 1;
    return values;
  }
}  // namespace

TEST(GamebubRecoveryHost, LedgerReservesAboveBothSidesAndNeverWrapsOrResets) {
  EXPECT_THROW(r::EpochLedger(0xffffffffU), std::invalid_argument);
  r::EpochLedger ledger;
  EXPECT_EQ(ledger.last(), 0);
  EXPECT_EQ(ledger.reserve(0), 1);
  EXPECT_EQ(ledger.reserve(5), 6);
  EXPECT_EQ(ledger.reserve(2), 7);
  EXPECT_THROW(ledger.reserve(0xffffffffU), std::invalid_argument);
  EXPECT_EQ(ledger.last(), 7);
  EXPECT_THROW(ledger.reserve(r::maximum_epoch), std::invalid_argument);
  EXPECT_EQ(ledger.last(), 7);
  r::EpochLedger terminal(r::maximum_epoch - 1);
  EXPECT_EQ(terminal.reserve(0), r::maximum_epoch);
  EXPECT_THROW(terminal.reserve(0), std::invalid_argument);
  EXPECT_EQ(terminal.last(), r::maximum_epoch);
}

TEST(GamebubRecoveryHost, ConstructionAndStoppedStateRejectInvalidOrPrematureWork) {
  static_assert(!std::is_copy_constructible_v<r::Host>);
  static_assert(!std::is_move_constructible_v<r::Host>);
  static_assert(!std::is_copy_assignable_v<r::Host>);
  static_assert(!std::is_move_assignable_v<r::Host>);
  r::EpochLedger ledger;
  EXPECT_THROW(r::Host(0, ledger), std::invalid_argument);
  EXPECT_THROW(r::Host(1, ledger, 9), std::invalid_argument);
  EXPECT_THROW(r::Host(1, ledger, std::numeric_limits<unsigned>::max()), std::invalid_argument);
  r::Host host(101, ledger);
  EXPECT_EQ(host.phase(), r::Phase::stopped);
  EXPECT_EQ(host.phase_name(), "STOPPED");
  EXPECT_FALSE(host.outstanding());
  EXPECT_FALSE(host.proposed_epoch());
  EXPECT_FALSE(host.data_allowed());
  EXPECT_EQ(host.retries(), 0);
  EXPECT_THROW(host.retry(), std::invalid_argument);
  const auto premature = r::serialize({r::Kind::hello_reply, 0, 101, 202, r::profile_tag});
  EXPECT_THROW(host.accept(premature, drained), std::invalid_argument);
  EXPECT_EQ(host.phase(), r::Phase::stopped);
}

TEST(GamebubRecoveryHost, NominalAgreementKeepsDataBlockedUntilExactGoAck) {
  r::EpochLedger ledger;
  r::Host host(101, ledger);
  const auto hello = host.start(drained);
  EXPECT_EQ(r::parse(hello), (r::Control {r::Kind::hello, 0, 101, 0, r::profile_tag}));
  EXPECT_EQ(host.phase_name(), "HELLO");
  EXPECT_FALSE(host.data_allowed());
  const std::array<r::Kind, 3> kinds {r::Kind::hello_reply, r::Kind::ready, r::Kind::committed};
  const std::array<std::string_view, 3> phases {"OFFER", "COMMIT", "GO"};
  for (unsigned i = 0; i < kinds.size(); ++i) {
    const auto next = host.accept(reply(host, kinds[i]), drained);
    EXPECT_EQ(next, host.outstanding());
    EXPECT_EQ(host.phase_name(), phases[i]);
    EXPECT_EQ(host.proposed_epoch(), 1);
    EXPECT_FALSE(host.data_allowed());
    EXPECT_EQ(host.retries(), 0);
  }
  const auto ack = reply(host, r::Kind::go_ack);
  EXPECT_FALSE(host.accept(ack, drained));
  EXPECT_EQ(host.phase(), r::Phase::running);
  EXPECT_EQ(host.phase_name(), "RUNNING");
  EXPECT_TRUE(host.data_allowed());
  EXPECT_FALSE(host.outstanding());
  EXPECT_THROW(host.retry(), std::invalid_argument);
  EXPECT_THROW(host.accept(ack, drained), std::invalid_argument);
}

TEST(GamebubRecoveryHost, EveryOwnerBlocksStartAndLateCommitResetWithoutDiscardingState) {
  for (const auto &blocked : blockers()) {
    r::EpochLedger ledger;
    r::Host host(101, ledger);
    EXPECT_FALSE(blocked.drained());
    EXPECT_THROW(host.start(blocked), std::invalid_argument);
    EXPECT_EQ(host.phase(), r::Phase::stopped);
    offer(host);
    auto outstanding = host.outstanding();
    const auto ready = reply(host, r::Kind::ready);
    EXPECT_THROW(host.accept(ready, blocked), std::invalid_argument);
    EXPECT_EQ(host.outstanding(), outstanding);
    EXPECT_EQ(host.phase(), r::Phase::offer);
    EXPECT_EQ(ledger.last(), 1);
    host.accept(ready, drained);
    outstanding = host.outstanding();
    const auto committed = reply(host, r::Kind::committed);
    EXPECT_THROW(host.accept(committed, blocked), std::invalid_argument);
    EXPECT_EQ(host.outstanding(), outstanding);
    EXPECT_EQ(host.phase(), r::Phase::commit);
    host.accept(committed, drained);
    host.accept(reply(host, r::Kind::go_ack), drained);
    EXPECT_THROW(host.start(blocked), std::invalid_argument);
    EXPECT_EQ(host.phase(), r::Phase::running);
  }
}

TEST(GamebubRecoveryHost, AllEightSingleControlLossesRetransmitExactOutstandingBytes) {
  const std::array<r::Kind, 4> replies {r::Kind::hello_reply, r::Kind::ready, r::Kind::committed, r::Kind::go_ack};
  for (unsigned lost_kind = 1; lost_kind <= 8; ++lost_kind) {
    r::EpochLedger ledger;
    r::Host host(101, ledger);
    host.start(drained);
    bool lost = false;
    for (const auto kind : replies) {
      const auto outbound = host.outstanding().value();
      if (static_cast<unsigned>(r::parse(outbound).kind) == lost_kind) {
        EXPECT_EQ(host.retry(), outbound);
        lost = true;
      }
      const auto incoming = reply(host, kind);
      if (static_cast<unsigned>(kind) == lost_kind) {
        EXPECT_EQ(host.retry(), outbound);
        EXPECT_EQ(reply(host, kind), incoming);
        lost = true;
      }
      EXPECT_FALSE(host.data_allowed());
      host.accept(incoming, drained);
      // GO_ACK creates no next phase to reset the final GO retry count in the pinned model.
      EXPECT_EQ(host.retries(), kind == r::Kind::go_ack && lost_kind >= 7 ? 1U : 0U);
    }
    EXPECT_TRUE(lost);
    EXPECT_TRUE(host.data_allowed());
    EXPECT_EQ(host.phase(), r::Phase::running);
  }
}

TEST(GamebubRecoveryHost, BusyAndRetryExhaustionRetainProposalAndBlockLateGoAck) {
  for (unsigned budget : {0U, 2U, 8U}) {
    r::EpochLedger ledger;
    r::Host host(101, ledger, budget);
    offer(host);
    const auto outbound = host.outstanding();
    const auto busy = reply(host, r::Kind::busy);
    for (unsigned i = 0; i < budget; ++i) {
      EXPECT_EQ(host.accept(busy, drained), outbound);
      EXPECT_EQ(host.retries(), i + 1);
    }
    EXPECT_THROW(host.accept(busy, drained), std::invalid_argument);
    EXPECT_EQ(host.phase_name(), "SAFE_STOP");
    EXPECT_EQ(host.outstanding(), outbound);
    EXPECT_EQ(host.proposed_epoch(), 1);
    EXPECT_FALSE(host.data_allowed());
    EXPECT_THROW(host.retry(), std::invalid_argument);
    EXPECT_THROW(host.accept(reply(host, r::Kind::ready), drained), std::invalid_argument);
    host.start(drained);
    EXPECT_EQ(ledger.last(), 1);
    EXPECT_FALSE(host.proposed_epoch());
    host.accept(reply(host, r::Kind::hello_reply), drained);
    EXPECT_EQ(host.proposed_epoch(), 2);
  }
  r::EpochLedger ledger;
  r::Host host(101, ledger);
  offer(host);
  host.accept(reply(host, r::Kind::ready), drained);
  host.accept(reply(host, r::Kind::committed), drained);
  const auto go = host.outstanding().value();
  const auto lost_ack = reply(host, r::Kind::go_ack);
  for (unsigned i = 0; i < 4; ++i) {
    EXPECT_EQ(host.retry(), go);
  }
  EXPECT_THROW(host.retry(), std::invalid_argument);
  EXPECT_THROW(host.accept(lost_ack, drained), std::invalid_argument);
  EXPECT_EQ(host.outstanding(), go);
  EXPECT_EQ(host.phase(), r::Phase::safe_stop);
  EXPECT_FALSE(host.data_allowed());
}

TEST(GamebubRecoveryHost, CorruptionWrongBindingAndUnexpectedKindsCannotAdvance) {
  r::EpochLedger ledger;
  r::Host host(101, ledger);
  offer(host);
  const auto outstanding = host.outstanding();
  auto corrupt = reply(host, r::Kind::ready);
  corrupt[0] ^= 1;
  EXPECT_THROW(host.accept(corrupt, drained), std::invalid_argument);
  for (unsigned change = 0; change < 5; ++change) {
    auto value = r::parse(reply(host, r::Kind::ready));
    switch (change) {
      case 0:
        ++value.host_nonce;
        break;
      case 1:
        value.profile[0] ^= 1;
        break;
      case 2:
        ++value.target_nonce;
        break;
      case 3:
        ++value.epoch;
        break;
      case 4:
        value.kind = r::Kind::committed;
        break;
    }
    EXPECT_THROW(host.accept(r::serialize(value), drained), std::invalid_argument);
    EXPECT_EQ(host.outstanding(), outstanding);
    EXPECT_EQ(host.phase(), r::Phase::offer);
    EXPECT_EQ(ledger.last(), 1);
  }
}

TEST(GamebubRecoveryHost, RebootAndAbandonedProposalNeverReuseReservedEpoch) {
  r::EpochLedger ledger;
  {
    r::Host host(101, ledger);
    running(host);
    EXPECT_EQ(host.proposed_epoch(), 1);
    host.start(drained);
    host.accept(r::serialize({r::Kind::hello_reply, 8, 101, 303, r::profile_tag}), drained);
    EXPECT_EQ(host.proposed_epoch(), 9);
  }
  r::Host rebooted(404, ledger);
  rebooted.start(drained);
  rebooted.accept(r::serialize({r::Kind::hello_reply, 1, 404, 303, r::profile_tag}), drained);
  EXPECT_EQ(rebooted.proposed_epoch(), 10);
  EXPECT_EQ(ledger.last(), 10);
  r::EpochLedger exhausted(r::maximum_epoch);
  r::Host terminal(1, exhausted);
  terminal.start(drained);
  const auto outstanding = terminal.outstanding();
  EXPECT_THROW(terminal.accept(reply(terminal, r::Kind::hello_reply), drained), std::invalid_argument);
  EXPECT_EQ(terminal.phase(), r::Phase::hello);
  EXPECT_EQ(terminal.outstanding(), outstanding);
  EXPECT_FALSE(terminal.proposed_epoch());
}

TEST(GamebubRecoveryHost, ActualPacketAndFrameLedgersRemainIndependentOfExplicitDrain) {
  t::SenderFrames frames;
  t::PacketLedger packets;
  std::vector<std::uint8_t> body(100, 7);
  const auto chunks = t::datagrams(body, 1, 1);
  const auto crc = t::parse_chunk(chunks[0]).content_crc;
  auto request = frames.request(1, static_cast<std::uint32_t>(body.size()), crc).value();
  auto grant = request;
  grant.kind = t::Kind::grant;
  ASSERT_TRUE(frames.reply(grant));
  ASSERT_TRUE(packets.register_frame(grant));
  const auto outbound = packets.reserve(chunks[0]).value();
  ASSERT_TRUE(packets.mark_enqueued(outbound.token));
  const auto evidence = [&]() {
    r::DrainEvidence owners {true};
    owners.frame_owners = std::max(frames.owned(), packets.registered_frames());
    owners.packet_owners = packets.owned_data();
    owners.control_owners = static_cast<unsigned>(frames.pending().has_value()) + static_cast<unsigned>(packets.mailbox_owned());
    return owners;
  };
  r::EpochLedger ledger;
  r::Host host(101, ledger);
  EXPECT_THROW(host.start(evidence()), std::invalid_argument);
  const auto &token = outbound.token;
  packets.credit({token.slot, false, token.sequence, 0, token.route_crc});
  EXPECT_EQ(packets.owned_data(), 0);
  EXPECT_THROW(host.start(evidence()), std::invalid_argument);
  auto finish = frames.control(1, t::Kind::finish).value();
  finish.kind = t::Kind::finished;
  ASSERT_TRUE(frames.reply(finish));
  EXPECT_EQ(frames.owned(), 1);
  EXPECT_THROW(host.start(evidence()), std::invalid_argument);
  auto release = grant;
  release.kind = t::Kind::release;
  ASSERT_TRUE(frames.reply(release));
  EXPECT_THROW(host.start(evidence()), std::invalid_argument);
  ASSERT_TRUE(packets.forget_frame(1));
  auto owners = evidence();
  EXPECT_TRUE(owners.drained());
  owners.transport_drained = false;
  EXPECT_THROW(host.start(owners), std::invalid_argument);
  const auto mailbox = packets.acquire_control().value();
  EXPECT_THROW(host.start(evidence()), std::invalid_argument);
  ASSERT_TRUE(packets.release_control(mailbox));
  EXPECT_NO_THROW(host.start(evidence()));
}
