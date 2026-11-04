/**
 * @file tools/gamebub/native/composed_wire.h
 * @brief Offline CP23/JA23 framing and nested identity checks from MoonBub4025d355.
 * @note This does not decode entropy or HUD pixels, validate reference banks,
 * publish state, negotiate a profile, or provide a live endpoint.
 */
#pragma once

// standard includes
#include <array>
#include <span>
#include <vector>

// local includes
#include "body_decoder.h"

namespace gamebub::v24::composed {
  using Tag = v20::body::Tag;  ///< Truncated SHA256 identity, not authentication.
  inline constexpr unsigned frame_cap = 49152;  ///< Strict complete CP23 admission limit.
  inline constexpr unsigned pair_header_bytes = 53;  ///< CP23 fields before components.
  inline constexpr unsigned pair_overhead = 57;  ///< CP23 header plus trailing CRC.
  inline constexpr unsigned ack_bytes = 134;  ///< Complete JA23 with AF03 and HA22.

  /** @brief Owned CP23 components; parsed bytes do not imply decoded/public state. */
  struct Pair {
    std::uint32_t epoch {}, frame {};  ///< Common component identity.
    std::vector<std::uint8_t> base, hud;  ///< Complete AR03 and HC22 packets.
    /** @brief Compare all identities and component bytes. */
    bool operator==(const Pair &) const = default;
  };

  /** @brief Syntax-valid JA23; exact outstanding-transaction binding is a later gate. */
  struct Ack {
    std::uint32_t epoch {}, frame {};  ///< Common envelope and component identity.
    Tag pair_digest {};  ///< Hash of the full CP23, not verified without that packet.
    std::array<std::uint8_t, 43> base_ack {};  ///< Nested AF03 including its CRC.
    std::array<std::uint8_t, 54> hud_ack {};  ///< Nested HA22 including its CRC.
    /** @brief Compare every wire identity and nested feedback byte. */
    bool operator==(const Ack &) const = default;
  };

  /** @brief Read-only HC22 framing identity without decoding its four patch payloads. */
  struct HudIdentity {
    std::uint32_t epoch {}, frame {}, generation {};  ///< Monotonic fields, without state comparison.
    std::uint8_t destination {}, reference {};  ///< Two-bank destination and optional reference.
    std::uint32_t reference_frame {}, reference_generation {};  ///< Referenced HUD identity.
    Tag reference_tag {}, new_tag {};  ///< Exact cache tags, without pixel verification.
    std::array<std::uint32_t, 4> sizes {};  ///< Four bounded patch byte counts.
    std::array<std::uint8_t, 4> modes {};  ///< LEGACY0 or DELTA1 dispatch.
  };

  /** @brief Header-only AR03 identity, without decoded coefficient/reference validation. */
  struct BaseIdentity {
    std::uint32_t epoch {}, frame {};  ///< Outer and inner identity.
    bool key {};  ///< Inner key flag matches the outer key flag.
    unsigned width {}, height {};  ///< Bounded even coded geometry.
  };

  /**
   * @brief Compute the first16 SHA256 bytes of the exact bounded source bytes.
   * @param bytes Complete component or pair bytes.
   * @return Truncated digest, never a peer-authentication credential.
   */
  inline Tag digest(std::span<const std::uint8_t> bytes) {
    std::array<unsigned char, SHA256_DIGEST_LENGTH> full;
    v20::body::require(SHA256(bytes.data(), bytes.size(), full.data()) != nullptr, "CP23 SHA256");
    Tag result;
    std::copy_n(full.begin(), result.size(), result.begin());
    return result;
  }

  /** @brief Validate an epoch or frame against HC22's nonwrapping scalar domain. */
  inline void check_id(std::uint32_t value, bool epoch = false) {
    v20::body::require(value != 0xffffffffU && (!epoch || value != 0), "composed bounded identity");
  }

  /**
   * @brief Check complete HC22 framing, slot identities, types and patch lengths.
   * @param packet Complete HC22 including CRC; payload codecs remain undecoded.
   * @return Header identity and bounded patch descriptors.
   */
  inline HudIdentity hud_identity(std::span<const std::uint8_t> packet) {
    using namespace v20::body;
    require(packet.size() >= 83 && packet.size() <= frame_cap, "HC22 bounded length");
    check_crc(packet);
    require(magic(packet, "HC22") && packet[4] == 1, "HC22 version");
    HudIdentity value {};
    value.epoch = u32(packet, 5);
    value.frame = u32(packet, 9);
    value.generation = u32(packet, 13);
    value.destination = packet[17];
    value.reference = packet[18];
    value.reference_frame = u32(packet, 19);
    value.reference_generation = u32(packet, 23);
    value.reference_tag = tag_at(packet, 27);
    value.new_tag = tag_at(packet, 43);
    check_id(value.epoch, true);
    check_id(value.frame);
    check_id(value.generation);
    require(value.destination < 2 && (value.reference < 2 || value.reference == 255) && value.new_tag != Tag {}, "HC22 slots/tag");
    if (value.reference == 255) {
      require(value.reference_frame == 0xffffffffU && value.reference_generation == 0xffffffffU && value.reference_tag == Tag {} && value.destination == 0, "HC22 full identity");
    } else {
      require(value.destination != value.reference && value.reference_frame < value.frame && value.reference_generation < value.generation && value.reference_tag != Tag {}, "HC22 reference identity");
    }
    std::uint64_t total = 83;
    for (unsigned i = 0; i < 4; ++i) {
      value.sizes[i] = u32(packet, 59 + 4 * i);
      value.modes[i] = packet[75 + i];
      require(value.sizes[i] > 0 && value.sizes[i] <= frame_cap && value.modes[i] < 2, "HC22 patch dispatch/length");
      total += value.sizes[i];
    }
    require(total == packet.size(), "HC22 exact body");
    return value;
  }

  /**
   * @brief Check the patch-free AR03 and GM01/SR01 identity grammar used by CP23.
   * @param packet Complete AR03 component, including nested and outer CRCs.
   * @return Framing identity; entropy, reference samples and stored tags remain unverified.
   */
  inline BaseIdentity base_identity(std::span<const std::uint8_t> packet) {
    using namespace v20::body;
    require(packet.size() >= 115 && v20::envelope(packet, false).empty(), "CP23 AR03 envelope");
    const auto flags = packet[5];
    const auto epoch = u32(packet, 6), frame = u32(packet, 10), ref = u32(packet, 16);
    const auto refbank = packet[14], destination = packet[15];
    const auto ref_tag = tag_at(packet, 20), new_tag = tag_at(packet, 36);
    require(epoch != 0xffffffffU && frame != 0xffffffffU && flags <= 2 && packet[56] == 0 && u32(packet, 57) == 0, "CP23 AR03 identity/patches");
    const bool key = flags == 1;
    if (key) {
      require(refbank == 255 && ref == 0xffffffffU && ref_tag == Tag {} && destination == 0 && new_tag != Tag {}, "AR03 key identity");
    } else {
      require(refbank < 2 && ref < frame && ref_tag != Tag {} && (flags == 2 ? destination == 1 && new_tag != Tag {} : destination == 255 && new_tag == Tag {}), "AR03 reference identity");
    }
    const auto inner = packet.subspan(61, u32(packet, 52));
    require(inner.size() >= 50 && (magic(inner, "GM01") || magic(inner, "SR01")) && inner[4] == 1, "AR03 inner dispatch");
    const bool split = magic(inner, "SR01");
    const auto inner_flags = inner[5];
    require((split ? inner_flags == 0 || inner_flags == 1 || inner_flags == 2 || inner_flags == 4 : inner_flags <= 1) && bool(inner_flags & 1) == key && u32(inner, 6) == epoch && u32(inner, 10) == frame && u32(inner, 14) == ref && !u16(inner, 22) && !u16(inner, 24), "AR03 inner identity");
    const unsigned width = u16(inner, 18), height = u16(inner, 20);
    geometry(width, height);
    const unsigned mw = (width + 15) / 16, mh = (height + 15) / 16;
    const auto nmap = u32(inner, 30);
    require(u16(inner, 26) == mw && u16(inner, 28) == mh && nmap == (mw * mh + 3) / 4, "AR03 map geometry");
    const std::array<std::uint32_t, 3> sizes {u32(inner, 34), u32(inner, 38), u32(inner, 42)};
    require(50ULL + nmap + std::uint64_t(sizes[0]) + sizes[1] + sizes[2] == inner.size(), "AR03 inner exact length");
    check_crc(inner);
    for (unsigned i = 0; i < nmap * 4; ++i) {
      const auto code = (inner[46 + i / 4] >> (6 - 2 * (i % 4))) & 3;
      require(code <= 2 && (i < mw * mh || code == 0), "AR03 map code/padding");
    }
    for (unsigned i = 0; i < 3; ++i) {
      const unsigned pw = i ? width / 2 : width, ph = i ? height / 2 : height;
      const std::uint64_t blocks = ((pw + 7) / 8) * ((ph + 7) / 8);
      const std::uint64_t lower = split ? 21 : 26;
      const std::uint64_t upper = split ? 21 + (blocks + 3) / 4 + 2 * blocks + 128 * blocks + 26 : 128 * blocks + 26;
      require(sizes[i] >= lower && sizes[i] <= upper, "AR03 plane bound");
    }
    return {epoch, frame, key, width, height};
  }

  /**
   * @brief Parse strict-cap CP23 framing, hashes and nested identity grammar.
   * @param packet Complete CP23 bytes including CRC.
   * @return Owned component bytes; no entropy decoding or publication occurs.
   */
  inline Pair parse_pair(std::span<const std::uint8_t> packet) {
    using namespace v20::body;
    require(packet.size() >= pair_overhead && packet.size() <= frame_cap, "CP23 complete cap");
    check_crc(packet);
    const auto nb = u32(packet, 13), nh = u32(packet, 17);
    require(magic(packet, "CP23") && packet[4] == 1 && nb > 0 && nb <= frame_cap && nh > 0 && nh <= frame_cap, "CP23 version/component lengths");
    require(pair_overhead + std::uint64_t(nb) + nh == packet.size(), "CP23 exact length");
    const auto base = packet.subspan(pair_header_bytes, nb), hud = packet.subspan(pair_header_bytes + nb, nh);
    require(digest(base) == tag_at(packet, 21) && digest(hud) == tag_at(packet, 37), "CP23 component digest");
    const auto b = base_identity(base);
    const auto h = hud_identity(hud);
    const auto epoch = u32(packet, 5), frame = u32(packet, 9);
    require(epoch == b.epoch && epoch == h.epoch && frame == b.frame && frame == h.frame, "CP23 component identity");
    return {epoch, frame, {base.begin(), base.end()}, {hud.begin(), hud.end()}};
  }

  /**
   * @brief Serialize a strict-cap CP23 pair without native packed-structure layout.
   * @param value Complete components and their common identity.
   * @return Exact CP23 bytes after nested framing validation.
   */
  inline std::vector<std::uint8_t> serialize_pair(const Pair &value) {
    using namespace v20::body;
    require(value.base.size() <= frame_cap && value.hud.size() <= frame_cap && pair_overhead + value.base.size() + value.hud.size() <= frame_cap, "CP23 complete cap");
    std::vector<std::uint8_t> bytes(pair_overhead + value.base.size() + value.hud.size());
    std::copy_n("CP23", 4, bytes.begin());
    bytes[4] = 1;
    put32(bytes, 5, value.epoch);
    put32(bytes, 9, value.frame);
    put32(bytes, 13, static_cast<std::uint32_t>(value.base.size()));
    put32(bytes, 17, static_cast<std::uint32_t>(value.hud.size()));
    const auto base_tag = digest(value.base), hud_tag = digest(value.hud);
    std::copy(base_tag.begin(), base_tag.end(), bytes.begin() + 21);
    std::copy(hud_tag.begin(), hud_tag.end(), bytes.begin() + 37);
    std::copy(value.base.begin(), value.base.end(), bytes.begin() + pair_header_bytes);
    std::copy(value.hud.begin(), value.hud.end(), bytes.begin() + pair_header_bytes + value.base.size());
    put32(bytes, bytes.size() - 4, v20::crc32(std::span(bytes).first(bytes.size() - 4)));
    parse_pair(bytes);
    return bytes;
  }

  /**
   * @brief Parse fixed JA23 plus AF03/HA22 grammar and common epoch/frame identities.
   * @param packet Complete134-byte acknowledgement, not yet bound to an outstanding pair.
   * @return Owned nested acknowledgements and pair digest.
   */
  inline Ack parse_ack(std::span<const std::uint8_t> packet) {
    using namespace v20::body;
    require(packet.size() == ack_bytes, "JA23 fixed length");
    check_crc(packet);
    require(magic(packet, "JA23") && packet[4] == 1 && u16(packet, 29) == 43 && u16(packet, 31) == 54, "JA23 profile");
    const auto epoch = u32(packet, 5), frame = u32(packet, 9);
    check_id(epoch, true);
    check_id(frame);
    const auto base = packet.subspan(33, 43), hud = packet.subspan(76, 54);
    require(v20::envelope(base, true).empty() && u32(base, 6) != 0xffffffffU && u32(base, 10) != 0xffffffffU, "JA23 AF03 profile");
    check_crc(hud);
    require(magic(hud, "HA22") && hud[4] == 1 && hud[17] < 2, "JA23 HA22 profile");
    check_id(u32(hud, 5), true);
    check_id(u32(hud, 9));
    check_id(u32(hud, 13));
    require(u32(base, 6) == epoch && u32(base, 10) == frame && u32(hud, 5) == epoch && u32(hud, 9) == frame, "JA23 component identities");
    Ack result {};
    result.epoch = epoch;
    result.frame = frame;
    result.pair_digest = tag_at(packet, 13);
    std::copy(base.begin(), base.end(), result.base_ack.begin());
    std::copy(hud.begin(), hud.end(), result.hud_ack.begin());
    return result;
  }

  /**
   * @brief Serialize a syntax-valid JA23 without inventing publication semantics.
   * @param value Common identity, opaque pair digest and complete nested feedback.
   * @return Exact134-byte JA23 after component identity validation.
   */
  inline std::array<std::uint8_t, ack_bytes> serialize_ack(const Ack &value) {
    using namespace v20::body;
    std::array<std::uint8_t, ack_bytes> bytes {};
    std::copy_n("JA23", 4, bytes.begin());
    bytes[4] = 1;
    put32(bytes, 5, value.epoch);
    put32(bytes, 9, value.frame);
    std::copy(value.pair_digest.begin(), value.pair_digest.end(), bytes.begin() + 13);
    bytes[29] = 43;
    bytes[31] = 54;
    std::copy(value.base_ack.begin(), value.base_ack.end(), bytes.begin() + 33);
    std::copy(value.hud_ack.begin(), value.hud_ack.end(), bytes.begin() + 76);
    put32(bytes, 130, v20::crc32(std::span(bytes).first(130)));
    parse_ack(bytes);
    return bytes;
  }
}  // namespace gamebub::v24::composed
