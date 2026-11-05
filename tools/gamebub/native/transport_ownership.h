/**
 * @file tools/gamebub/native/transport_ownership.h
 * @brief Couple frozen epoch-one packet and frame ledgers without inferring physical drain.
 * @note The inherited GF03/FG19/PC18/QC18 laboratory contract remains unchanged.
 * This is not a live endpoint, codec validator, reference publisher or RS24 epoch bridge.
 */
#pragma once

// standard includes
#include <array>
#include <cstdint>
#include <optional>
#include <span>

// local includes
#include "packet_ledger.h"
#include "recovery_host.h"

namespace gamebub::v20::transport {
  /** @brief Read-only coupled ownership; no field is a physical-drain certificate. */
  struct OwnershipSnapshot {
    unsigned frame_owners {};  ///< Exact GRANT owners retained through FINISHED.
    unsigned packet_owners {};  ///< Reserved or enqueued DATA permits not yet returned.
    unsigned registered_frames {};  ///< Packet accounts coupled to granted frame owners.
    bool mailbox_owned {};  ///< One QC18 or FG19 exchange retains the shared mailbox.
    bool frame_control_pending {};  ///< An exact FG19 request awaits its matching reply.
    bool stopped {};  ///< Sticky stop blocks new intents but does not invent release.
  };

  /**
   * @brief Enforce caller-side ownership preconditions across the existing bounded ledgers.
   * @note Only epoch one is supported by the inherited transport. Late exact replies may
   * settle already-issued work after stop; they never resume admission. Source/candidate/
   * reference owners and real transport drain remain explicit external evidence.
   */
  class SenderOwnership {
    /** @brief Mirror one exact granted route and prevent DATA after CANCEL/FINISH intent. */
    struct Owner {
      FrameControl grant;  ///< Exact route already accepted by the frame ledger.
      bool retiring {};  ///< Freeze new DATA until CANCEL BUSY or eventual release.
    };

    /** @brief One FG19 intent owns the same mailbox until its exact accepted response. */
    struct Pending {
      FrameControl intent;  ///< Existing wire identity; no additional protocol field.
      ControlPermit permit;  ///< Existing local mailbox generation.
    };

    PacketLedger packets_;  ///< Five DATA slots and one shared control mailbox.
    SenderFrames frames_;  ///< Two independent acknowledged frame slots.
    std::array<std::optional<Owner>, 2> owners_;  ///< Fixed mirrors, never mutable externally.
    std::optional<Pending> pending_;  ///< At most one FG19 exchange.
    bool stopped_ {};  ///< Admission stop is local; reply settlement remains possible.

    /** @brief Find a granted route without creating ownership. */
    const Owner *owner(std::uint32_t frame) const {
      for (const auto &entry : owners_) {
        if (entry && entry->grant.frame == frame) {
          return &*entry;
        }
      }
      return nullptr;
    }

    /** @brief Reserve the mailbox before allowing a frame-control state mutation. */
    std::optional<FrameControl> begin_control(std::uint32_t frame, Kind kind) {
      const auto *held = owner(frame);
      if (stopped_ || !held || held->retiring) {
        return std::nullopt;
      }
      const auto permit = packets_.acquire_control();
      if (!permit) {
        return std::nullopt;
      }
      const auto intent = frames_.control(frame, kind);
      require(intent.has_value(), "coupled granted frame-control invariant");
      pending_ = Pending {*intent, *permit};
      owners_[held->grant.slot]->retiring = true;
      return intent;
    }

  public:
    /** @brief Start empty; preserve the pinned zero-to-three per-frame query budget. */
    explicit SenderOwnership(unsigned maximum_queries = 3):
        packets_(maximum_queries) {}

    /** @brief Copying cannot duplicate owned packet/frame identities. */
    SenderOwnership(const SenderOwnership &) = delete;
    /** @brief Moving cannot leave a second object claiming the same reservations. */
    SenderOwnership(SenderOwnership &&) = delete;
    /** @brief Assignment cannot discard or fork unresolved ownership. */
    SenderOwnership &operator=(const SenderOwnership &) = delete;
    /** @brief Move assignment cannot replace retained unknown outcomes. */
    SenderOwnership &operator=(SenderOwnership &&) = delete;

    /**
     * @brief Reserve one exact existing FG19 REQUEST and its shared control mailbox.
     * @param frame Bounded frame identity, excluding the GF03 all-ones sentinel.
     * @param total Complete frame bytes, within the inherited 49,152-byte cap.
     * @param content_crc Existing content checksum, not a decoder/reference acknowledgement.
     * @return Request or no value under bounded backpressure/sticky stop.
     */
    std::optional<FrameControl> request(std::uint32_t frame, std::uint32_t total, std::uint32_t content_crc) {
      if (stopped_) {
        return std::nullopt;
      }
      require(frame != 0xffffffffU && total > 0 && total <= frame_cap, "coupled request identity/bound");
      const auto permit = packets_.acquire_control();
      if (!permit) {
        return std::nullopt;
      }
      const auto intent = frames_.request(frame, total, content_crc);
      if (!intent) {
        require(packets_.release_control(*permit), "coupled unused mailbox invariant");
        return std::nullopt;
      }
      pending_ = Pending {*intent, *permit};
      return intent;
    }

    /** @brief Reserve DATA only for an active granted frame, not one retiring or stopped. */
    std::optional<Outbound> reserve(std::span<const std::uint8_t> packet) {
      const auto chunk = parse_chunk(packet);
      const auto *held = owner(chunk.frame);
      if (stopped_ || !held || held->retiring) {
        return std::nullopt;
      }
      return packets_.reserve(packet);
    }

    /** @brief Conservatively mark a queue handoff; never hand off after retirement intent. */
    bool mark_enqueued(const Token &token) {
      const auto *held = owner(token.frame);
      return !stopped_ && held && !held->retiring && packets_.mark_enqueued(token);
    }

    /** @brief Return only an exact reservation never handed to a sender queue/socket. */
    bool cancel_unsent(const Token &token) {
      return !stopped_ && packets_.cancel_unsent(token);
    }

    /** @brief Apply actual validated PC18 bytes, including exact late settlement after stop. */
    ReceiptResult credit(std::span<const std::uint8_t> bytes) {
      return packets_.credit(parse_credit(bytes));
    }

    /** @brief Reserve QC18 only when admission and the shared mailbox permit it. */
    std::optional<CreditQuery> query(const Token &token) {
      return stopped_ ? std::nullopt : packets_.query(token);
    }

    /** @brief FINISH requires every fragment enqueued/resolved and no outstanding query mailbox. */
    std::optional<FrameControl> finish(std::uint32_t frame) {
      return packets_.packets_resolved(frame) ? begin_control(frame, Kind::finish) : std::nullopt;
    }

    /** @brief CANCEL requires no reserved or ever-enqueued DATA for the granted frame. */
    std::optional<FrameControl> cancel(std::uint32_t frame) {
      return packets_.may_cancel(frame) ? begin_control(frame, Kind::cancel) : std::nullopt;
    }

    /**
     * @brief Validate and couple exact FG19 effects without releasing a frame on FINISHED.
     * @param bytes Complete existing FG19 reply, with CRC and identity checked first.
     * @return True only for an accepted exact outstanding reply or confirmed frame RELEASE.
     */
    bool reply(std::span<const std::uint8_t> bytes) {
      const auto value = parse_frame(bytes);
      if (value.kind == Kind::release) {
        if (!owner(value.frame) || !packets_.packets_resolved(value.frame) || !frames_.reply(value)) {
          return false;
        }
        require(packets_.forget_frame(value.frame), "coupled RELEASE packet-account invariant");
        owners_[value.slot].reset();
        return true;
      }
      if (!pending_) {
        return false;
      }
      const auto pending = *pending_;
      if (!identity(pending.intent, value) || (value.kind != Kind::busy && value.slot != pending.intent.slot)) {
        return false;
      }
      const bool expected = (pending.intent.kind == Kind::request && (value.kind == Kind::grant || value.kind == Kind::busy)) ||
                            (pending.intent.kind == Kind::cancel && (value.kind == Kind::canceled || value.kind == Kind::busy)) ||
                            (pending.intent.kind == Kind::finish && value.kind == Kind::finished);
      if (!expected || !frames_.reply(value)) {
        return false;
      }
      // After exact prevalidation, the following fixed-size operations cannot fail for
      // caller input: both ledgers are private, frame accounts have capacity three
      // for only two grants, and retiring frames admit no intervening DATA mutation.
      if (pending.intent.kind == Kind::request && value.kind == Kind::grant) {
        require(packets_.register_frame(value), "coupled GRANT packet-account invariant");
        owners_[value.slot] = Owner {value};
      } else if (pending.intent.kind == Kind::cancel) {
        if (value.kind == Kind::canceled) {
          require(packets_.forget_frame(value.frame), "coupled CANCELED packet-account invariant");
          owners_[pending.intent.slot].reset();
        } else {
          owners_[pending.intent.slot]->retiring = false;
        }
      }
      require(packets_.release_control(pending.permit), "coupled FG19 mailbox invariant");
      pending_.reset();
      return true;
    }

    /** @brief Stop new work while retaining every outstanding intent and acknowledged owner. */
    void stop() {
      stopped_ = true;
    }

    /** @brief Copy bounded ownership counts without exposing mutable component ledgers. */
    OwnershipSnapshot snapshot() const {
      return {frames_.owned(), packets_.owned_data(), packets_.registered_frames(), packets_.mailbox_owned(), pending_.has_value(), stopped_};
    }

    /** @brief Read existing per-frame counts; no receive/drain inference is added. */
    std::optional<FrameStats> frame_stats(std::uint32_t frame) const {
      return packets_.frame_stats(frame);
    }

    /**
     * @brief Derive local reset blockers while preserving explicit external owner/drain facts.
     * @param transport_drained Explicit model signal, never inferred from credits or FINISHED.
     * @param source_owners Immutable source owners outside this transport component.
     * @param candidate_owners Private codec candidates/scratch outside this component.
     * @param reference_readers Outstanding reference-bank readers outside this component.
     * @return RS24 model evidence; this does not negotiate another transport epoch.
     */
    v24::recovery::DrainEvidence drain_evidence(bool transport_drained = false, unsigned source_owners = 0, unsigned candidate_owners = 0, unsigned reference_readers = 0) const {
      return {transport_drained, source_owners, candidate_owners, reference_readers, frames_.owned(), packets_.owned_data(), packets_.mailbox_owned() ? 1U : 0U};
    }
  };
}  // namespace gamebub::v20::transport
