/**
 * @file tools/gamebub/native/transport.h
 * @brief Pinned offline GF03/FG19/PC18/QC18 wire codecs and sender frame ownership.
 * @note MoonBub27a4dde laboratory contract only: no live endpoint, recovery negotiation,
 * physical-drain inference, packet FIFO implementation or reference publication.
 */
#pragma once

// standard includes
#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <optional>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

// local includes
#include "v20.h"

namespace gamebub::v20::transport {
  inline constexpr unsigned frame_cap = 49152;  ///< Complete frame bytes, not a payload-only limit.
  inline constexpr unsigned payload_cap = 1008;  ///< Pinned GF03 chunk payload size.
  inline constexpr unsigned chunk_header = 31;  ///< Big-endian GF03 header size.
  inline constexpr std::uint16_t no_slot = 65535;  ///< FG19 absent slot sentinel.

  /** @brief Reject invalid local fields or received bytes before publishing a value. */
  inline void require(bool valid, const char *reason) {
    if (!valid) {
      throw std::invalid_argument(reason);
    }
  }

  /** @brief Read a bounded big-endian integer of at most eight bytes. */
  inline std::uint64_t read(std::span<const std::uint8_t> bytes, unsigned at, unsigned length) {
    require(length <= 8 && at <= bytes.size() && length <= bytes.size() - at, "transport field bounds");
    std::uint64_t value = 0;
    for (unsigned i = 0; i < length; ++i) {
      value = (value << 8) | bytes[at + i];
    }
    return value;
  }

  /** @brief Append a bounded big-endian integer without native-layout casts. */
  inline void append(std::vector<std::uint8_t> &bytes, std::uint64_t value, unsigned length) {
    require(length > 0 && length <= 8 && (length == 8 || value < (std::uint64_t(1) << (8 * length))), "transport integer bound");
    for (unsigned i = length; i != 0; --i) {
      bytes.push_back(static_cast<std::uint8_t>(value >> (8 * (i - 1))));
    }
  }

  /** @brief Match an exact four-byte packet family without unbounded string access. */
  inline bool magic(std::span<const std::uint8_t> bytes, const char *value) {
    return bytes.size() >= 4 && std::equal(bytes.begin(), bytes.begin() + 4, value);
  }

  /** @brief Validate an exact-size control packet and its trailing big-endian CRC32. */
  inline void sealed(std::span<const std::uint8_t> bytes, unsigned size, const char *family) {
    require(bytes.size() == size && magic(bytes, family), "transport control length/magic");
    require(crc32(bytes.first(size - 4)) == read(bytes, size - 4, 4), "transport control CRC");
  }

  /** @brief Append IEEE CRC32 in the control wire's big-endian order. */
  inline std::vector<std::uint8_t> seal(std::vector<std::uint8_t> bytes) {
    append(bytes, crc32(bytes), 4);
    return bytes;
  }

  /** @brief Frozen FG19 request/reply kinds; FINISHED does not release frame storage. */
  enum class Kind : std::uint8_t {
    request = 1,
    cancel,
    grant,
    busy,
    release,
    canceled,
    finish,
    finished
  };

  /** @brief One CRC-bound laboratory frame-control identity and operation. */
  struct FrameControl {
    Kind kind {};  ///< Frozen operation.
    std::uint16_t slot {};  ///< Exact frame slot, or no_slot where permitted.
    std::uint32_t epoch {1};  ///< Laboratory epoch is exactly one.
    std::uint32_t frame {};  ///< Wire frame identifier.
    std::uint64_t sequence {};  ///< Nonzero, nonwrapping request identity.
    std::uint32_t total {};  ///< Complete frame bytes.
    std::uint32_t content_crc {};  ///< Bound content-specific frame checksum.
    /** @brief Compare every serialized frame-control field. */
    bool operator==(const FrameControl &) const = default;
  };

  /** @brief Validate the pinned parser's field rules, including kind-specific slot rules. */
  inline void validate(const FrameControl &value) {
    const unsigned kind = static_cast<unsigned>(value.kind);
    require(kind >= 1 && kind <= 8 && value.epoch == 1 && value.sequence && value.total > 0 && value.total <= frame_cap && (value.slot < 2 || value.slot == no_slot), "FG19 fields");
    require((value.kind != Kind::busy || value.slot == no_slot) && ((value.kind != Kind::request && value.kind != Kind::grant && value.kind != Kind::release && value.kind != Kind::finished) || value.slot != no_slot), "FG19 slot");
  }

  /** @brief Parse exact FG19 bytes atomically; this checks syntax, not sender ownership. */
  inline FrameControl parse_frame(std::span<const std::uint8_t> bytes) {
    sealed(bytes, 36, "FG19");
    require(bytes[4] == 1, "FG19 version");
    FrameControl value {static_cast<Kind>(bytes[5]), static_cast<std::uint16_t>(read(bytes, 6, 2)), static_cast<std::uint32_t>(read(bytes, 8, 4)), static_cast<std::uint32_t>(read(bytes, 12, 4)), read(bytes, 16, 8), static_cast<std::uint32_t>(read(bytes, 24, 4)), static_cast<std::uint32_t>(read(bytes, 28, 4))};
    validate(value);
    return value;
  }

  /** @brief Serialize FG19 exactly as frame_credit.seal in the pinned reference. */
  inline std::vector<std::uint8_t> serialize(const FrameControl &value) {
    validate(value);
    std::vector<std::uint8_t> out {'F', 'G', '1', '9', 1, static_cast<std::uint8_t>(value.kind)};
    append(out, value.slot, 2);
    append(out, value.epoch, 4);
    append(out, value.frame, 4);
    append(out, value.sequence, 8);
    append(out, value.total, 4);
    append(out, value.content_crc, 4);
    return seal(std::move(out));
  }

  /** @brief A consumed/rejected/unknown packet receipt, independent of frame/reference ACKs. */
  struct PacketCredit {
    std::uint16_t slot {};  ///< Token slot in [0,5].
    bool queried {};  ///< Receipt also answers the active QC18 request.
    std::uint64_t sequence {};  ///< Nonzero per-token generation.
    std::uint8_t status {};  ///< 0 consumed, 1 rejected, 2 unknown; unknown does not free capacity.
    std::uint32_t route_crc {};  ///< CRC of token prefix plus GF03 header.
    /** @brief Compare every packet-credit identity and result field. */
    bool operator==(const PacketCredit &) const = default;
  };

  /** @brief One immutable packet-capacity query; laboratory epoch is implicit one. */
  struct CreditQuery {
    std::uint16_t slot {};  ///< Token slot in [0,5].
    std::uint64_t sequence {};  ///< Nonzero token generation.
    std::uint32_t route_crc {};  ///< Exact queried packet route binding.
    /** @brief Compare the exact queried packet identity. */
    bool operator==(const CreditQuery &) const = default;
  };

  /** @brief Parse the exact PC18 receipt, including its reserved/profile bits. */
  inline PacketCredit parse_credit(std::span<const std::uint8_t> bytes) {
    sealed(bytes, 29, "PC18");
    require(read(bytes, 4, 4) == 1 && read(bytes, 8, 2) < 6 && read(bytes, 10, 2) <= 1 && read(bytes, 12, 8) && bytes[20] <= 2, "PC18 fields");
    return {static_cast<std::uint16_t>(read(bytes, 8, 2)), read(bytes, 10, 2) != 0, read(bytes, 12, 8), bytes[20], static_cast<std::uint32_t>(read(bytes, 21, 4))};
  }

  /** @brief Serialize a valid PC18 receipt, never treating it as a frame ACK. */
  inline std::vector<std::uint8_t> serialize(const PacketCredit &value) {
    require(value.slot < 6 && value.sequence && value.status <= 2, "PC18 fields");
    std::vector<std::uint8_t> out {'P', 'C', '1', '8'};
    append(out, 1, 4);
    append(out, value.slot, 2);
    append(out, value.queried, 2);
    append(out, value.sequence, 8);
    append(out, value.status, 1);
    append(out, value.route_crc, 4);
    return seal(std::move(out));
  }

  /** @brief Parse an exact QC18 query with zero reserved field. */
  inline CreditQuery parse_query(std::span<const std::uint8_t> bytes) {
    sealed(bytes, 28, "QC18");
    require(read(bytes, 4, 4) == 1 && read(bytes, 8, 2) < 6 && read(bytes, 10, 2) == 0 && read(bytes, 12, 8), "QC18 fields");
    return {static_cast<std::uint16_t>(read(bytes, 8, 2)), read(bytes, 12, 8), static_cast<std::uint32_t>(read(bytes, 20, 4))};
  }

  /** @brief Serialize the pinned QC18 packet-capacity query. */
  inline std::vector<std::uint8_t> serialize(const CreditQuery &value) {
    require(value.slot < 6 && value.sequence, "QC18 fields");
    std::vector<std::uint8_t> out {'Q', 'C', '1', '8'};
    append(out, 1, 4);
    append(out, value.slot, 2);
    append(out, 0, 2);
    append(out, value.sequence, 8);
    append(out, value.route_crc, 4);
    return seal(std::move(out));
  }

  /** @brief One non-owning exact GF03 packet view, valid while its input bytes live. */
  struct Chunk {
    std::uint32_t epoch {};  ///< Epoch below reserved all-ones.
    std::uint32_t frame {};  ///< Frame ID below reserved all-ones.
    std::uint32_t total {};  ///< Whole frame bytes, bounded by frame_cap.
    std::uint16_t index {};  ///< Zero-based chunk index.
    std::uint16_t count {};  ///< Exact ceil(total/1008).
    std::uint32_t whole_crc {};  ///< CRC32 of complete frame, including its footer.
    std::uint32_t content_crc {};  ///< CRC32 excluding the frame's final four bytes.
    std::span<const std::uint8_t> payload;  ///< Exact chunk bytes; header has no per-packet CRC.
  };

  /** @brief Parse GF03 structural geometry; complete-frame integrity requires reassembly. */
  inline Chunk parse_chunk(std::span<const std::uint8_t> bytes) {
    require(bytes.size() >= chunk_header && magic(bytes, "GF03") && bytes[4] == 3, "GF03 header");
    Chunk value {static_cast<std::uint32_t>(read(bytes, 5, 4)), static_cast<std::uint32_t>(read(bytes, 9, 4)), static_cast<std::uint32_t>(read(bytes, 13, 4)), static_cast<std::uint16_t>(read(bytes, 17, 2)), static_cast<std::uint16_t>(read(bytes, 19, 2)), static_cast<std::uint32_t>(read(bytes, 23, 4)), static_cast<std::uint32_t>(read(bytes, 27, 4)), bytes.subspan(chunk_header)};
    require(value.epoch != 0xffffffffU && value.frame != 0xffffffffU && value.total > 0 && value.total <= frame_cap && value.count == (value.total + payload_cap - 1) / payload_cap && value.index < value.count, "GF03 identity/geometry");
    require(read(bytes, 21, 2) == value.payload.size() && value.payload.size() == std::min(payload_cap, value.total - value.index * payload_cap), "GF03 payload length");
    return value;
  }

  /** @brief Serialize one exact GF03 view after validating the resulting geometry. */
  inline std::vector<std::uint8_t> serialize(const Chunk &value) {
    require(value.payload.size() <= payload_cap, "GF03 payload bound");
    std::vector<std::uint8_t> bytes {'G', 'F', '0', '3', 3};
    append(bytes, value.epoch, 4);
    append(bytes, value.frame, 4);
    append(bytes, value.total, 4);
    append(bytes, value.index, 2);
    append(bytes, value.count, 2);
    append(bytes, value.payload.size(), 2);
    append(bytes, value.whole_crc, 4);
    append(bytes, value.content_crc, 4);
    bytes.insert(bytes.end(), value.payload.begin(), value.payload.end());
    parse_chunk(bytes);
    return bytes;
  }

  /** @brief Packetize immutable frame bytes exactly; this does not grant transmission permission. */
  inline std::vector<std::vector<std::uint8_t>> datagrams(std::span<const std::uint8_t> frame, std::uint32_t epoch, std::uint32_t id) {
    require(!frame.empty() && frame.size() <= frame_cap && epoch != 0xffffffffU && id != 0xffffffffU, "GF03 frame identity/bound");
    const auto whole = crc32(frame), content = crc32(frame.first(frame.size() > 4 ? frame.size() - 4 : 0));
    const auto count = (frame.size() + payload_cap - 1) / payload_cap;
    std::vector<std::vector<std::uint8_t>> out;
    for (unsigned i = 0; i < count; ++i) {
      const auto payload = frame.subspan(i * payload_cap, std::min<std::size_t>(payload_cap, frame.size() - i * payload_cap));
      std::vector<std::uint8_t> bytes {'G', 'F', '0', '3', 3};
      append(bytes, epoch, 4);
      append(bytes, id, 4);
      append(bytes, frame.size(), 4);
      append(bytes, i, 2);
      append(bytes, count, 2);
      append(bytes, payload.size(), 2);
      append(bytes, whole, 4);
      append(bytes, content, 4);
      bytes.insert(bytes.end(), payload.begin(), payload.end());
      out.push_back(std::move(bytes));
    }
    return out;
  }

  /** @brief Validated token wrapper; route CRC binds the 16-byte token and 31-byte GF03 header. */
  struct Wrapped {
    std::uint16_t slot {};  ///< One of the six laboratory packet-token slots.
    std::uint64_t sequence {};  ///< Nonzero token generation.
    std::uint32_t route_crc {};  ///< Header binding used by PC18/QC18.
    Chunk chunk;  ///< Borrowed structurally valid GF03 packet.
  };

  /** @brief Validate wrapped data, including inner geometry, without granting ownership. */
  inline Wrapped unwrap(std::span<const std::uint8_t> bytes) {
    require(bytes.size() >= 16 + chunk_header && bytes.size() <= 1064, "wrapped bounds");
    require(read(bytes, 0, 4) == 1 && read(bytes, 4, 2) < 6 && read(bytes, 6, 2) == 0 && read(bytes, 8, 8), "wrapped token");
    auto chunk = parse_chunk(bytes.subspan(16));
    require(chunk.epoch == 1, "wrapped epoch");
    return {static_cast<std::uint16_t>(read(bytes, 4, 2)), read(bytes, 8, 8), crc32(bytes.first(16 + chunk_header)), chunk};
  }

  /** @brief Wrap a valid laboratory GF03 packet in its exact packet-token identity. */
  inline std::vector<std::uint8_t> wrap(std::span<const std::uint8_t> packet, unsigned slot, std::uint64_t sequence) {
    const auto chunk = parse_chunk(packet);
    require(chunk.epoch == 1 && slot < 6 && sequence, "wrapped token fields");
    std::vector<std::uint8_t> out;
    append(out, 1, 4);
    append(out, slot, 2);
    append(out, 0, 2);
    append(out, sequence, 8);
    out.insert(out.end(), packet.begin(), packet.end());
    return out;
  }

  /** @brief Compare only the FG19 identity tuple; slot and operation are checked separately. */
  inline bool identity(const FrameControl &a, const FrameControl &b) {
    return a.epoch == b.epoch && a.frame == b.frame && a.sequence == b.sequence && a.total == b.total && a.content_crc == b.content_crc;
  }

  /**
   * @brief Bounded sender frame ledger for the pinned FINISHED-acknowledged laboratory mode.
   * @note Explicit sender intents and received replies only. No physical receiver drain,
   * decoded-reference publication, data-token accounting or timeout-based owner release.
   */
  class SenderFrames {
  public:
    /** @brief Reserve a pending request intent; slots become granted only on its exact reply. */
    std::optional<FrameControl> request(std::uint32_t frame, std::uint32_t total, std::uint32_t crc) {
      if (stopped_ || pending_ || sequence_ == std::numeric_limits<std::uint64_t>::max()) {
        return std::nullopt;
      }
      for (const auto &owner : owners_) {
        if (owner && owner->control.frame == frame) {
          return std::nullopt;
        }
      }
      for (unsigned slot = 0; slot < owners_.size(); ++slot) {
        if (!owners_[slot]) {
          FrameControl value {Kind::request, static_cast<std::uint16_t>(slot), 1, frame, sequence_ + 1, total, crc};
          validate(value);
          ++sequence_;
          pending_ = value;
          return value;
        }
      }
      return std::nullopt;
    }

    /**
     * @brief Issue FINISH or CANCEL for an exact granted frame; no state is released here.
     * @pre CANCEL is allowed only before data has been enqueued or transmitted for this frame.
     * @pre FINISH requires every frame packet to have been sent and all its PC18 permits returned.
     * @note The caller must independently establish both gateway preconditions. This frame-only
     * ledger does not track queued packets, packet permits or physical receiver drain, and
     * is not a complete protocol ownership machine.
     */
    std::optional<FrameControl> control(std::uint32_t frame, Kind kind) {
      require(kind == Kind::finish || kind == Kind::cancel, "sender intent kind");
      if (stopped_ || pending_) {
        return std::nullopt;
      }
      for (auto &owner : owners_) {
        if (owner && owner->control.frame == frame) {
          if (owner->finish_sent) {
            return std::nullopt;
          }
          auto value = owner->control;
          value.kind = kind;
          pending_ = value;
          owner->finish_sent = kind == Kind::finish;
          return value;
        }
      }
      return std::nullopt;
    }

    /** @brief Apply a matching reply; malformed/stale/wrong-kind replies cannot release owners. */
    bool reply(const FrameControl &value) {
      validate(value);
      if (value.kind == Kind::release) {
        auto &owner = owners_[value.slot];
        if (!owner || !owner->finish_confirmed || !identity(owner->control, value)) {
          return false;
        }
        owner.reset();
        return true;
      }
      if (!pending_ || !identity(*pending_, value)) {
        return false;
      }
      const auto kind = pending_->kind;
      if ((kind == Kind::request && value.kind == Kind::busy) || (kind == Kind::cancel && value.kind == Kind::busy)) {
        pending_.reset();
        return true;
      }
      if (value.slot != pending_->slot) {
        return false;
      }
      auto &owner = owners_[value.slot];
      if (kind == Kind::request && value.kind == Kind::grant && !owner) {
        owner = Owner {value};
      } else if (kind == Kind::cancel && value.kind == Kind::canceled && owner && identity(owner->control, value)) {
        owner.reset();
      } else if (kind == Kind::finish && value.kind == Kind::finished && owner && identity(owner->control, value)) {
        owner->finish_confirmed = true;
      } else {
        return false;
      }
      pending_.reset();
      return true;
    }

    /** @brief Stop new intents on unknown outcomes without clearing any pending/granted owner. */
    void stop() {
      stopped_ = true;
    }

    /** @brief Read whether admission is stopped; no production resume/reset is invented. */
    bool stopped() const {
      return stopped_;
    }

    /** @brief Read the outstanding control identity, retained after an ambiguous timeout. */
    const std::optional<FrameControl> &pending() const {
      return pending_;
    }

    /** @brief Count only acknowledged frame-slot grants; independent of packet/reference ownership. */
    unsigned owned() const {
      return static_cast<unsigned>(std::count_if(owners_.begin(), owners_.end(), [](const auto &owner) {
        return owner.has_value();
      }));
    }

  private:
    /** @brief One sender-observed frame-slot grant and its FINISH handshake progress. */
    struct Owner {
      FrameControl control;  ///< Exact granted identity, including slot.
      bool finish_sent {};  ///< Sender issued its single FINISH.
      bool finish_confirmed {};  ///< Exact FINISHED was received; frame storage still remains owned.
    };

    std::array<std::optional<Owner>, 2> owners_;  ///< Two separately owned frame slots.
    std::optional<FrameControl> pending_;  ///< Single in-flight frame-control request.
    std::uint64_t sequence_ {};  ///< Last issued request sequence, never wrapped.
    bool stopped_ {};  ///< Unknown outcome blocks new work while preserving ownership.
  };
}  // namespace gamebub::v20::transport
