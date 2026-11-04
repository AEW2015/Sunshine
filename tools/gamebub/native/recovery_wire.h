/**
 * @file tools/gamebub/native/recovery_wire.h
 * @brief Offline RS24 syntax from MoonBub4025d355, without negotiation or reset ownership.
 * @note Successful parsing does not establish a supported profile, authenticated peer,
 * transport drain, epoch persistence or permission to send CP23 media.
 */
#pragma once

// standard includes
#include <algorithm>
#include <array>
#include <cstdint>
#include <span>
#include <stdexcept>

// local includes
#include "v20.h"

namespace gamebub::v24::recovery {
  inline constexpr unsigned control_bytes = 46;  ///< Exact RS24 packet size including CRC.
  inline constexpr std::uint32_t maximum_epoch = 0xfffffffeU;  ///< Last legal epoch; wrapping is forbidden.

  /** @brief Pinned RS24 message kinds, independent of any active state machine. */
  enum class Kind : std::uint8_t {
    hello = 1,  ///< Discover the peer boot identity and epoch ledger.
    hello_reply,  ///< Return the peer boot identity and current ledger.
    offer,  ///< Propose a bound profile and epoch.
    ready,  ///< Report readiness for the proposed agreement.
    commit,  ///< Request commitment of the proposed agreement.
    committed,  ///< Report commitment of the proposed agreement.
    go,  ///< Request activation after commitment.
    go_ack,  ///< Acknowledge activation.
    busy  ///< Decline immediate readiness without granting ownership.
  };

  /** @brief One syntactically valid RS24 operation and its bound wire identity. */
  struct Control {
    Kind kind {};  ///< HELLO through BUSY, inclusive.
    std::uint32_t epoch {};  ///< Zero only for HELLO or HELLO_REPLY.
    std::uint64_t host_nonce {};  ///< Nonzero boot nonce; not an authentication credential.
    std::uint64_t target_nonce {};  ///< Zero for HELLO, nonzero for all other kinds.
    std::array<std::uint8_t, 16> profile {};  ///< Opaque SHA256 prefix, checked by a future agreement layer.
    /** @brief Compare every serialized identity and message field. */
    bool operator==(const Control &) const = default;
  };

  /**
   * @brief Reject fields outside the pinned RS24 grammar.
   * @param value Local or parsed control; profile support is deliberately not inferred.
   */
  inline void validate(const Control &value) {
    const auto kind = static_cast<unsigned>(value.kind);
    if (kind < 1 || kind > 9 || value.epoch > maximum_epoch || value.host_nonce == 0) {
      throw std::invalid_argument("RS24 fields");
    }
    if (value.kind == Kind::hello) {
      if (value.epoch != 0 || value.target_nonce != 0) {
        throw std::invalid_argument("RS24 HELLO fields");
      }
    } else if (value.target_nonce == 0 || (value.kind != Kind::hello_reply && value.epoch == 0)) {
      throw std::invalid_argument("RS24 bound fields");
    }
  }

  /**
   * @brief Serialize one exact-size RS24 packet without native struct layout assumptions.
   * @param value Grammar-valid control with an opaque profile tag.
   * @return Forty-six bytes; trailing little-endian IEEE CRC32 covers the first42 bytes.
   */
  inline std::array<std::uint8_t, control_bytes> serialize(const Control &value) {
    validate(value);
    std::array<std::uint8_t, control_bytes> bytes {'R', 'S', '2', '4', 1, static_cast<std::uint8_t>(value.kind)};
    for (unsigned i = 0; i < 4; ++i) {
      bytes[6 + i] = static_cast<std::uint8_t>(value.epoch >> (8 * i));
    }
    for (unsigned i = 0; i < 8; ++i) {
      bytes[10 + i] = static_cast<std::uint8_t>(value.host_nonce >> (8 * i));
      bytes[18 + i] = static_cast<std::uint8_t>(value.target_nonce >> (8 * i));
    }
    std::copy(value.profile.begin(), value.profile.end(), bytes.begin() + 26);
    const auto checksum = gamebub::v20::crc32(std::span(bytes).first(42));
    for (unsigned i = 0; i < 4; ++i) {
      bytes[42 + i] = static_cast<std::uint8_t>(checksum >> (8 * i));
    }
    return bytes;
  }

  /**
   * @brief Parse an entire RS24 packet atomically, checking framing, CRC and grammar.
   * @param bytes Exact packet bytes, without transport prefixes or suffixes.
   * @return Parsed fields; throws before returning on any malformed packet.
   */
  inline Control parse(std::span<const std::uint8_t> bytes) {
    if (bytes.size() != control_bytes) {
      throw std::invalid_argument("RS24 exact length");
    }
    if (gamebub::v20::crc32(bytes.first(42)) != gamebub::v20::le32(bytes, 42)) {
      throw std::invalid_argument("RS24 CRC");
    }
    if (bytes[0] != 'R' || bytes[1] != 'S' || bytes[2] != '2' || bytes[3] != '4' || bytes[4] != 1) {
      throw std::invalid_argument("RS24 magic/version");
    }
    Control value {};
    value.kind = static_cast<Kind>(bytes[5]);
    value.epoch = gamebub::v20::le32(bytes, 6);
    for (unsigned i = 0; i < 8; ++i) {
      value.host_nonce |= static_cast<std::uint64_t>(bytes[10 + i]) << (8 * i);
      value.target_nonce |= static_cast<std::uint64_t>(bytes[18 + i]) << (8 * i);
    }
    std::copy(bytes.begin() + 26, bytes.begin() + 42, value.profile.begin());
    validate(value);
    return value;
  }
}  // namespace gamebub::v24::recovery
