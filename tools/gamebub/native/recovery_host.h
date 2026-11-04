/**
 * @file tools/gamebub/native/recovery_host.h
 * @brief Bounded offline RS24 host agreement from MoonBub4025d355.
 * @note Drain snapshots and the epoch ledger are model inputs, not DMA completion,
 * durable storage, authentication or permission to reset a live codec pipeline.
 */
#pragma once

// standard includes
#include <optional>
#include <string_view>

// local includes
#include "recovery_wire.h"

namespace gamebub::v24::recovery {
  inline constexpr std::array<std::uint8_t, 16> profile_tag {0xd7, 0xbf, 0x1a, 0x16, 0x9b, 0x4f, 0x75, 0xff, 0xd9, 0xb3, 0x6a, 0x54, 0x29, 0xc4, 0xc9, 0x4d};  ///< Pinned CP23/JA23 profile, not the active v20 media format.

  /**
   * @brief Monotonic in-memory epoch ledger whose lifetime can span modeled host reboots.
   * @note The caller must separately implement durable atomic storage before deployment.
   */
  class EpochLedger {
    std::uint32_t last_;  ///< Last reserved epoch, including abandoned proposals.

  public:
    /**
     * @brief Restore a modeled ledger without accepting the reserved wrap sentinel.
     * @param last Last reserved epoch, or zero for an initially empty ledger.
     */
    explicit EpochLedger(std::uint32_t last = 0):
        last_(last) {
      if (last > maximum_epoch) {
        throw std::invalid_argument("RS24 epoch ledger");
      }
    }

    /** @brief Return the last reservation without clearing it. */
    std::uint32_t last() const {
      return last_;
    }

    /**
     * @brief Reserve one epoch above both local and peer ledgers, without wrapping.
     * @param peer_epoch Peer ledger from a grammar-valid HELLO_REPLY.
     * @return Newly reserved epoch; failure leaves the ledger unchanged.
     */
    std::uint32_t reserve(std::uint32_t peer_epoch) {
      if (peer_epoch > maximum_epoch || std::max(last_, peer_epoch) == maximum_epoch) {
        throw std::invalid_argument("RS24 epoch exhausted or invalid peer ledger");
      }
      last_ = std::max(last_, peer_epoch) + 1;
      return last_;
    }
  };

  /**
   * @brief Explicit modeled ownership snapshot supplied afresh at reset decision points.
   * @note Counts cover media/private owners and transport operations to retire before
   * reset. They exclude the agreement's own synchronously returned control bytes.
   * A PC18 receipt, FINISHED reply or empty software queue does not establish drain.
   */
  struct DrainEvidence {
    bool transport_drained = false;  ///< Explicit modeled transport/DMA drain signal.
    unsigned source_owners {};  ///< Immutable source buffers still in use.
    unsigned candidate_owners {};  ///< Uncommitted/private candidates, including analysis scratch.
    unsigned reference_readers {};  ///< Readers of any banks that reset would invalidate.
    unsigned frame_owners {};  ///< Granted frame slots not yet explicitly released or canceled.
    unsigned packet_owners {};  ///< Unresolved packet reservations or local send operations.
    unsigned control_owners {};  ///< Unresolved media-control operations, not RS24 bytes.

    /** @brief Require every modeled owner to retire as well as an explicit drain signal. */
    bool drained() const {
      return transport_drained && source_owners == 0 && candidate_owners == 0 && reference_readers == 0 && frame_owners == 0 && packet_owners == 0 && control_owners == 0;
    }
  };

  /** @brief Host control phases; only RUNNING permits the agreement-layer data gate. */
  enum class Phase {
    stopped,  ///< No agreement has begun.
    hello,  ///< Awaiting a boot-bound HELLO_REPLY.
    offer,  ///< Awaiting READY for one reserved proposal.
    commit,  ///< Awaiting COMMITTED for that proposal.
    go,  ///< Awaiting GO_ACK; data remains blocked.
    running,  ///< Control agreement completed; media validation remains separate.
    safe_stop  ///< Retry budget exhausted; unresolved identity is retained.
  };

  /**
   * @brief Noncopyable synchronous host control model with one bounded outstanding packet.
   * @note This does not instantiate CP23 banks, consume JA23, reset v20 owners, or
   * authorize hardware transmission. A future media layer must independently enforce
   * the fresh-epoch independent key/full-HUD requirement and real ownership checks.
   */
  class Host {
    std::uint64_t nonce_;  ///< Nonzero modeled host boot identity.
    EpochLedger &ledger_;  ///< Caller-owned persistent-lifetime model ledger.
    unsigned maximum_retries_;  ///< Bounded 0..8 retransmissions per outstanding phase.
    Phase phase_ = Phase::stopped;  ///< Data starts blocked.
    std::optional<Control> proposal_;  ///< Exact epoch/host/target/profile agreement identity.
    std::optional<std::array<std::uint8_t, control_bytes>> outstanding_;  ///< Exact retransmission bytes.
    unsigned retries_ {};  ///< Retransmissions since the latest successful phase advance.

    /** @brief Match proposal identity without conflating its message kind with a reply. */
    bool matches(const Control &reply) const {
      return proposal_ && proposal_->epoch == reply.epoch && proposal_->host_nonce == reply.host_nonce && proposal_->target_nonce == reply.target_nonce && proposal_->profile == reply.profile;
    }

    /** @brief Advance a known proposal while resetting only the phase-local retry budget. */
    void advance(Kind kind, Phase phase) {
      auto next = *proposal_;
      next.kind = kind;
      outstanding_ = serialize(next);
      phase_ = phase;
      retries_ = 0;
    }

  public:
    /**
     * @brief Construct one offline boot instance referencing a caller-owned epoch ledger.
     * @param boot_nonce Nonzero host identity; generation/randomness is outside this model.
     * @param ledger In-memory epoch reservations retained across modeled reboot instances.
     * @param maximum_retries Maximum retransmissions in each phase, in the range 0..8.
     */
    explicit Host(std::uint64_t boot_nonce, EpochLedger &ledger, unsigned maximum_retries = 4):
        nonce_(boot_nonce),
        ledger_(ledger),
        maximum_retries_(maximum_retries) {
      if (nonce_ == 0 || maximum_retries_ > 8) {
        throw std::invalid_argument("RS24 host nonce or retry bound");
      }
    }

    /** @brief Copying cannot fork one outstanding agreement into independent owners. */
    Host(const Host &) = delete;
    /** @brief Assignment cannot discard an existing unresolved agreement. */
    Host &operator=(const Host &) = delete;
    /** @brief Moving cannot leave a second object with the same agreement identity. */
    Host(Host &&) = delete;
    /** @brief Move assignment cannot replace retained unknown outcomes. */
    Host &operator=(Host &&) = delete;

    /**
     * @brief Begin or restart only after explicitly modeled prior owners have drained.
     * @param owners Fresh modeled ownership/drain evidence; not inferred from receipts.
     * @return HELLO bytes with epoch/target zero; existing ledger reservations survive.
     */
    std::array<std::uint8_t, control_bytes> start(const DrainEvidence &owners) {
      if (!owners.drained()) {
        throw std::invalid_argument("RS24 host owners must explicitly drain");
      }
      outstanding_ = serialize({Kind::hello, 0, nonce_, 0, profile_tag});
      proposal_.reset();
      phase_ = Phase::hello;
      retries_ = 0;
      return *outstanding_;
    }

    /**
     * @brief Return exactly the outstanding bytes within a finite retry budget.
     * @return Identical packet, or throw after entering SAFE_STOP on exhaustion.
     * @note Exhaustion retains the outstanding identity and invents no returned owners.
     */
    std::array<std::uint8_t, control_bytes> retry() {
      if (!outstanding_ || phase_ == Phase::running || phase_ == Phase::stopped || phase_ == Phase::safe_stop) {
        throw std::invalid_argument("RS24 no outstanding retry");
      }
      if (retries_ >= maximum_retries_) {
        phase_ = Phase::safe_stop;
        throw std::invalid_argument("RS24 retry exhausted; data remains blocked");
      }
      ++retries_;
      return *outstanding_;
    }

    /**
     * @brief Accept one control under exact phase, boot, profile and proposal binding.
     * @param bytes Complete peer RS24 packet; malformed or unrelated input cannot advance.
     * @param owners Fresh modeled drain evidence, rechecked before COMMIT and modeled reset.
     * @return Next outstanding packet, or no packet after GO_ACK completes agreement.
     */
    std::optional<std::array<std::uint8_t, control_bytes>> accept(std::span<const std::uint8_t> bytes, const DrainEvidence &owners) {
      const auto reply = parse(bytes);
      if (reply.host_nonce != nonce_ || reply.profile != profile_tag) {
        throw std::invalid_argument("RS24 host boot/profile binding");
      }
      if (phase_ == Phase::hello && reply.kind == Kind::hello_reply) {
        const auto epoch = ledger_.reserve(reply.epoch);
        proposal_ = Control {Kind::offer, epoch, nonce_, reply.target_nonce, profile_tag};
        advance(Kind::offer, Phase::offer);
      } else {
        if (!matches(reply)) {
          throw std::invalid_argument("RS24 host outstanding identity");
        }
        if (reply.kind == Kind::busy && phase_ == Phase::offer) {
          return retry();
        }
        if (phase_ == Phase::offer && reply.kind == Kind::ready) {
          if (!owners.drained()) {
            throw std::invalid_argument("RS24 late owner before COMMIT");
          }
          advance(Kind::commit, Phase::commit);
        } else if (phase_ == Phase::commit && reply.kind == Kind::committed) {
          if (!owners.drained()) {
            throw std::invalid_argument("RS24 late owner before modeled reset");
          }
          advance(Kind::go, Phase::go);
        } else if (phase_ == Phase::go && reply.kind == Kind::go_ack) {
          phase_ = Phase::running;
          outstanding_.reset();
        } else {
          throw std::invalid_argument("RS24 host unexpected phase/kind");
        }
      }
      return outstanding_;
    }

    /** @brief Return the current control phase without changing ownership. */
    Phase phase() const {
      return phase_;
    }

    /** @brief Return the phase spelling used by the pinned Python transcript. */
    std::string_view phase_name() const {
      constexpr std::array<std::string_view, 7> names {"STOPPED", "HELLO", "OFFER", "COMMIT", "GO", "RUNNING", "SAFE_STOP"};
      return names[static_cast<unsigned>(phase_)];
    }

    /** @brief Observe retained exact control bytes; this is not a local DMA completion. */
    const std::optional<std::array<std::uint8_t, control_bytes>> &outstanding() const {
      return outstanding_;
    }

    /** @brief Return retransmissions charged to the current phase. */
    unsigned retries() const {
      return retries_;
    }

    /** @brief Observe the reserved proposal epoch, including one retained after SAFE_STOP. */
    std::optional<std::uint32_t> proposed_epoch() const {
      return proposal_ ? std::optional(proposal_->epoch) : std::nullopt;
    }

    /** @brief Report only the control gate; no actual media/key/HUD validation is performed. */
    bool data_allowed() const {
      return phase_ == Phase::running;
    }
  };
}  // namespace gamebub::v24::recovery
