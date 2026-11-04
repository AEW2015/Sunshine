/**
 * @file tools/gamebub/native/packet_ledger.h
 * @brief Bounded sender packet permits for the pinned GF03/PC18/QC18 laboratory model.
 * @note Packet accounting is independent of frame-slot release, physical drain and AF03.
 */
#pragma once

// standard includes
#include <array>
#include <bitset>
#include <limits>
#include <optional>
#include <vector>

// local includes
#include "transport.h"

namespace gamebub::v20::transport {
  /** @brief Advance a local generation without ever wrapping to a stale wire identity. */
  inline std::optional<std::uint64_t> next_packet_sequence(std::uint64_t last) {
    return last == std::numeric_limits<std::uint64_t>::max() ? std::nullopt : std::optional(last + 1);
  }

  /** @brief Exact local data reservation, including its received-header route binding. */
  struct Token {
    std::uint16_t slot {};  ///< One of five DATA slots; the sixth mailbox position is reserved.
    std::uint64_t sequence {};  ///< Nonzero, nonwrapping generation for this packet slot.
    std::uint32_t route_crc {};  ///< CRC32 of TOKEN plus GF03 header, excluding payload.
    std::uint32_t frame {};  ///< Sender bookkeeping identity, not a reference acknowledgement.
    std::uint16_t index {};  ///< Unique fragment index within the registered frame.
    /** @brief Compare every local ownership and route field. */
    bool operator==(const Token &) const = default;
  };

  /** @brief Owned bytes plus the exact reservation required before enqueueing them. */
  struct Outbound {
    Token token;  ///< Reservation identity retained while the packet outcome is unresolved.
    std::vector<std::uint8_t> bytes;  ///< Complete bounded TOKEN/GF03 datagram.
  };

  /** @brief Opaque local permit for one externally validated FG19 request/reply exchange. */
  struct ControlPermit {
    std::uint64_t generation {};  ///< Nonzero local mailbox generation; never sent as a new wire field.
    /** @brief Compare exact local mailbox ownership. */
    bool operator==(const ControlPermit &) const = default;
  };

  /** @brief Independent effects of a syntactically valid PC18 receipt. */
  struct ReceiptResult {
    bool data_released = false;  ///< Exact consumed/rejected DATA token returned.
    bool query_released = false;  ///< Exact queried response freed only its control mailbox.
    bool rejected = false;  ///< The returned DATA token reported rejection, not frame acceptance.
    bool unknown = false;  ///< A matching status2 retained DATA ownership.
  };

  /** @brief Read-only bounded per-frame packet accounting, not decoder/scanout state. */
  struct FrameStats {
    unsigned fragments {};  ///< Number declared by the complete frame's GF03 geometry.
    unsigned enqueued {};  ///< Unique DATA packets handed to a sender queue/socket.
    unsigned resolved {};  ///< Unique DATA packets with consumed/rejected PC18 receipts.
    unsigned queries {};  ///< QC18 attempts charged to this frame, bounded to three.
    unsigned rejected {};  ///< Resolved DATA packets with status1.
  };

  /**
   * @brief Five DATA permits, one shared control mailbox and at most three frame accounts.
   * @note Derived from gateway.py at MoonBub27a4dde. It does not authenticate grants,
   * prove hardware drain or implement reconnect/reset. A fresh object is a fresh lab model,
   * not permission to reset a live peer. Unknown outcomes never fabricate capacity.
   */
  class PacketLedger {
    /** @brief Packet metadata retained independently of its caller-owned bytes. */
    struct Entry {
      Token token;  ///< Exact active slot generation and packet route.
      bool enqueued = false;  ///< Once true, local cancellation cannot return its permit.
    };

    /** @brief Fixed-size bitsets prevent duplicate enqueue/resolution and unbounded histories. */
    struct Frame {
      FrameControl grant;  ///< Externally validated grant used only as a route declaration here.
      std::bitset<49> reserved, enqueued, resolved;  ///< At most ceil(49152/1008) fragments.
      unsigned fragments {}, queries {}, rejected {};  ///< Bounded accounting counters.
    };

    std::array<std::optional<Entry>, 5> tokens_;  ///< Five DATA positions; never the reserved sixth slot.
    std::array<std::uint64_t, 5> sequences_ {};  ///< Per-slot generations survive unsent cancellation.
    std::array<std::optional<Frame>, 3> frames_;  ///< Sender accounts, not three receiver frame grants.
    std::optional<Token> query_;  ///< Exact QC18 target owns the shared control mailbox.
    std::optional<ControlPermit> frame_control_;  ///< Alternative FG19 owner of that mailbox.
    std::uint64_t control_sequence_ {};  ///< Local generation guards stale mailbox releases.
    unsigned maximum_queries_;  ///< Configured bound from the pinned 0..3 range.
    bool stopped_ = false;  ///< Stops new work while retaining unresolved reservations.

    /** @brief Find a registered frame without allocating or creating state. */
    Frame *find(std::uint32_t id) {
      for (auto &frame : frames_) {
        if (frame && frame->grant.frame == id) {
          return &*frame;
        }
      }
      return nullptr;
    }

    /** @brief Find a read-only registered frame without creating state. */
    const Frame *find(std::uint32_t id) const {
      for (const auto &frame : frames_) {
        if (frame && frame->grant.frame == id) {
          return &*frame;
        }
      }
      return nullptr;
    }

    /** @brief Require exact local token identity rather than only a reused packet slot. */
    Entry *entry(const Token &token) {
      if (token.slot >= tokens_.size() || !tokens_[token.slot] || tokens_[token.slot]->token != token) {
        return nullptr;
      }
      return &*tokens_[token.slot];
    }

  public:
    /**
     * @brief Construct an empty laboratory packet account with a fixed query bound.
     * @param maximum_queries Maximum QC18 attempts per frame, from0 through3.
     */
    explicit PacketLedger(unsigned maximum_queries = 3):
        maximum_queries_(maximum_queries) {
      require(maximum_queries <= 3, "packet query bound0..3");
    }

    /** @brief Packet and mailbox ownership cannot be forked into a second ledger. */
    PacketLedger(const PacketLedger &) = delete;
    /** @brief Moving must not leave a second ledger claiming the same permits. */
    PacketLedger(PacketLedger &&) = delete;
    /** @brief Assignment must not duplicate or replace outstanding packet ownership. */
    PacketLedger &operator=(const PacketLedger &) = delete;
    /** @brief Move assignment cannot discard or fork retained unknown outcomes. */
    PacketLedger &operator=(PacketLedger &&) = delete;

    /**
     * @brief Register a bounded packet route after a caller validates its exact FG19 grant.
     * @param grant Granted identity from the separate sender frame ledger.
     * @return False for duplicate/exhausted/stopped accounts; malformed declarations throw.
     * @note This is not an additional receiver frame grant or proof of a live endpoint.
     */
    bool register_frame(const FrameControl &grant) {
      validate(grant);
      require(grant.kind == Kind::grant && grant.frame != 0xffffffffU, "packet account requires grant route");
      if (stopped_ || find(grant.frame)) {
        return false;
      }
      for (auto &frame : frames_) {
        if (!frame) {
          frame = Frame {grant, {}, {}, {}, (grant.total + payload_cap - 1) / payload_cap, 0, 0};
          return true;
        }
      }
      return false;
    }

    /**
     * @brief Reserve a free DATA permit and wrap one registered GF03 fragment atomically.
     * @param packet Exact GF03 datagram; no sender queue has received it yet.
     * @return Owned wrapped bytes/identity, or no value for exhausted/stale/stopped work.
     */
    std::optional<Outbound> reserve(std::span<const std::uint8_t> packet) {
      const auto chunk = parse_chunk(packet);
      auto *frame = find(chunk.frame);
      require(chunk.epoch == 1 && frame && chunk.total == frame->grant.total && chunk.content_crc == frame->grant.content_crc, "packet frame route");
      if (stopped_ || frame->reserved[chunk.index] || frame->enqueued[chunk.index]) {
        return std::nullopt;
      }
      for (unsigned slot = 0; slot < tokens_.size(); ++slot) {
        const auto sequence = next_packet_sequence(sequences_[slot]);
        if (!tokens_[slot] && sequence) {
          auto bytes = wrap(packet, slot, *sequence);
          const auto decoded = unwrap(bytes);
          const Token token {static_cast<std::uint16_t>(slot), *sequence, decoded.route_crc, chunk.frame, chunk.index};
          tokens_[slot] = Entry {token};
          sequences_[slot] = *sequence;
          frame->reserved.set(chunk.index);
          return Outbound {token, std::move(bytes)};
        }
      }
      return std::nullopt;
    }

    /**
     * @brief Mark the conservative sender-queue handoff; subsequent cancellation cannot free it.
     * @param token Exact active reservation.
     * @return True only for its first handoff, not duplicate or stale intents.
     */
    bool mark_enqueued(const Token &token) {
      auto *owned = entry(token);
      if (stopped_ || !owned || owned->enqueued) {
        return false;
      }
      owned->enqueued = true;
      find(token.frame)->enqueued.set(token.index);
      return true;
    }

    /**
     * @brief Return only a reservation which has never reached a sender queue/socket.
     * @param token Exact active reservation; canceled generations are never reused.
     * @return False once transmission may have occurred or after unknown-outcome stop.
     */
    bool cancel_unsent(const Token &token) {
      auto *owned = entry(token);
      if (stopped_ || !owned || owned->enqueued) {
        return false;
      }
      find(token.frame)->reserved.reset(token.index);
      tokens_[token.slot].reset();
      return true;
    }

    /**
     * @brief Apply PC18 independently to DATA and QC18 mailbox ownership.
     * @param receipt Parsed exact PC18 value; syntactic validation is repeated here.
     * @return Explicit release effects; a matching status2 never frees DATA.
     * @note A matching unqueried status0/1 can return DATA while a query remains owned.
     */
    ReceiptResult credit(const PacketCredit &receipt) {
      serialize(receipt);
      ReceiptResult result;
      if (receipt.slot >= tokens_.size()) {
        return result;
      }
      const auto matches = [&](const Token &token) {
        return token.slot == receipt.slot && token.sequence == receipt.sequence && token.route_crc == receipt.route_crc;
      };
      if (receipt.queried && query_ && matches(*query_)) {
        query_.reset();
        result.query_released = true;
      }
      auto &owned = tokens_[receipt.slot];
      if (owned && owned->enqueued && matches(owned->token)) {
        if (receipt.status == 2) {
          result.unknown = true;
        } else {
          auto *frame = find(owned->token.frame);
          frame->reserved.reset(owned->token.index);
          frame->resolved.set(owned->token.index);
          frame->rejected += receipt.status == 1;
          result.data_released = true;
          result.rejected = receipt.status == 1;
          owned.reset();
        }
      }
      return result;
    }

    /**
     * @brief Reserve the shared control mailbox for an exact unresolved packet query.
     * @param token Enqueued DATA token whose original receipt did not arrive.
     * @return Frozen QC18 value, or no value if stopped, stale, busy or query-budget exhausted.
     */
    std::optional<CreditQuery> query(const Token &token) {
      auto *owned = entry(token);
      if (stopped_ || !owned || !owned->enqueued || mailbox_owned()) {
        return std::nullopt;
      }
      auto *frame = find(token.frame);
      if (frame->queries >= maximum_queries_) {
        return std::nullopt;
      }
      ++frame->queries;
      query_ = token;
      return CreditQuery {token.slot, token.sequence, token.route_crc};
    }

    /** @brief Reserve the sixth mailbox position for one caller-managed FG19 exchange. */
    std::optional<ControlPermit> acquire_control() {
      const auto sequence = next_packet_sequence(control_sequence_);
      if (stopped_ || mailbox_owned() || !sequence) {
        return std::nullopt;
      }
      control_sequence_ = *sequence;
      frame_control_ = ControlPermit {*sequence};
      return frame_control_;
    }

    /**
     * @brief Release only an exact caller-managed FG19 mailbox permit.
     * @param permit Local generation after the caller validates its exact FG19 reply.
     * @return False for stale/duplicate/query permits; this does not free frame storage.
     */
    bool release_control(const ControlPermit &permit) {
      if (!frame_control_ || *frame_control_ != permit) {
        return false;
      }
      frame_control_.reset();
      return true;
    }

    /** @brief Check all declared DATA was enqueued and consumed/rejected; not physical drain. */
    bool packets_resolved(std::uint32_t id) const {
      const auto *frame = find(id);
      return frame && frame->enqueued.count() == frame->fragments && frame->resolved.count() == frame->fragments;
    }

    /** @brief Check no DATA reached a sender queue and all local reservations were canceled. */
    bool may_cancel(std::uint32_t id) const {
      const auto *frame = find(id);
      return frame && frame->enqueued.none() && frame->reserved.none();
    }

    /**
     * @brief Forget only resolved or never-enqueued packet bookkeeping with no query outstanding.
     * @param id Exact registered frame.
     * @return False while packets/query remain; caller separately proves FG19 RELEASE/CANCELED.
     */
    bool forget_frame(std::uint32_t id) {
      for (auto &frame : frames_) {
        if (frame && frame->grant.frame == id) {
          if ((query_ && query_->frame == id) || (!packets_resolved(id) && !may_cancel(id))) {
            return false;
          }
          frame.reset();
          return true;
        }
      }
      return false;
    }

    /** @brief Read bounded frame packet counters without exposing mutable ledger storage. */
    std::optional<FrameStats> frame_stats(std::uint32_t id) const {
      const auto *frame = find(id);
      if (!frame) {
        return std::nullopt;
      }
      return FrameStats {frame->fragments, static_cast<unsigned>(frame->enqueued.count()), static_cast<unsigned>(frame->resolved.count()), frame->queries, frame->rejected};
    }

    /** @brief Read the number of outstanding DATA permits, at most five. */
    unsigned owned_data() const {
      unsigned count = 0;
      for (const auto &token : tokens_) {
        count += token.has_value();
      }
      return count;
    }

    /** @brief Read registered sender accounts, independently of receiver frame-slot ownership. */
    unsigned registered_frames() const {
      unsigned count = 0;
      for (const auto &frame : frames_) {
        count += frame.has_value();
      }
      return count;
    }

    /** @brief Read whether QC18 or an external FG19 exchange owns the one reserved mailbox. */
    bool mailbox_owned() const {
      return query_.has_value() || frame_control_.has_value();
    }

    /** @brief Stop new work after an ambiguous outcome without clearing any owned permit. */
    void stop() {
      stopped_ = true;
    }

    /** @brief Read the sticky admission stop; no production reset/resume is invented. */
    bool stopped() const {
      return stopped_;
    }
  };
}  // namespace gamebub::v20::transport
