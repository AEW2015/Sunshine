/**
 * @file tools/gamebub/native/composed_transaction.h
 * @brief Offline exact CP23/JA23 outstanding binding from MoonBub4025d355.
 * @note This does not decode pixels, manage reference/HUD banks, publish state,
 * release transport owners or implement a live endpoint or reset service.
 */
#pragma once

// standard includes
#include <optional>

// local includes
#include "composed_wire.h"

namespace gamebub::v24::transaction {
  /**
   * @brief Construct the exact expected joint reply from one syntax-valid CP23 pair.
   * @param packet Complete bounded CP23 with fixed720x480 component identities.
   * @return Complete expected JA23, including exact AF03/HA22 payloads and CRCs.
   * @note Header-declared tags are expectations, not proof that a decoder reconstructed them.
   */
  inline std::array<std::uint8_t, composed::ack_bytes> expected_ack(std::span<const std::uint8_t> packet) {
    using namespace v20::body;
    const auto pair = composed::parse_pair(packet);
    const auto base = composed::base_identity(pair.base);
    require(base.width == 720 && base.height == 480, "CP23 transaction fixed canvas");
    composed::Ack reply {};
    reply.epoch = pair.epoch;
    reply.frame = pair.frame;
    reply.pair_digest = composed::digest(packet);
    auto &base_ack = reply.base_ack;
    std::copy_n("AF03", 4, base_ack.begin());
    base_ack[4] = 3;
    base_ack[5] = 1;
    put32(base_ack, 6, pair.epoch);
    put32(base_ack, 10, pair.frame);
    put32(base_ack, 14, u32(pair.base, pair.base.size() - 4));
    const auto destination = pair.base[15];
    base_ack[18] = destination;
    put32(base_ack, 19, destination == 255 ? 0xffffffffU : pair.frame);
    if (destination != 255) {
      std::copy_n(pair.base.begin() + 36, 16, base_ack.begin() + 23);
    }
    put32(base_ack, 39, v20::crc32(std::span(base_ack).first(39)));
    auto &hud_ack = reply.hud_ack;
    std::copy_n("HA22", 4, hud_ack.begin());
    hud_ack[4] = 1;
    put32(hud_ack, 5, pair.epoch);
    put32(hud_ack, 9, pair.frame);
    put32(hud_ack, 13, u32(pair.hud, 13));
    hud_ack[17] = pair.hud[17];
    const auto hud_digest = composed::digest(pair.hud);
    std::copy(hud_digest.begin(), hud_digest.end(), hud_ack.begin() + 18);
    std::copy_n(pair.hud.begin() + 43, 16, hud_ack.begin() + 34);
    put32(hud_ack, 50, v20::crc32(std::span(hud_ack).first(50)));
    return composed::serialize_ack(reply);
  }

  /**
   * @brief Retain one immutable outstanding pair until its exact successful joint ACK.
   * @note This bounded software binding is only one prerequisite for the full host.
   * It neither owns nor releases physical packet/frame buffers, and exposes no
   * cancellation/reset shortcut for unknown outcomes. A fresh instance is not
   * permission to reset hardware or republish previously used references.
   */
  class PendingPair {
    /**
     * @brief Private exact bytes retained independently of caller-owned storage.
     */
    struct Pending {
      std::vector<std::uint8_t> packet;  ///< Complete CP23 retained for byte-identical retry.
      std::array<std::uint8_t, composed::ack_bytes> ack;  ///< Exact expected whole-pair response.
      std::uint32_t frame;  ///< Identity committed only after a matching response.
    };

    std::uint32_t epoch_;  ///< Fixed nonzero epoch, with no wrap or live reset facility.
    std::optional<std::uint32_t> acknowledged_;  ///< Last accepted frame, not reference publication.
    std::optional<Pending> pending_;  ///< At most one bounded unresolved pair.

  public:
    /**
     * @brief Create an empty offline binding for one already-agreed epoch.
     * @param epoch Nonzero CP23 epoch, excluding the invalid sentinel.
     */
    explicit PendingPair(std::uint32_t epoch):
        epoch_(epoch) {
      composed::check_id(epoch, true);
    }

    /**
     * @brief Report whether exact bytes remain retained awaiting an ACK.
     */
    bool has_pending() const {
      return pending_.has_value();
    }

    /**
     * @brief Return the last matched frame; no hardware publication is implied.
     */
    std::optional<std::uint32_t> acknowledged_frame() const {
      return acknowledged_;
    }

    /**
     * @brief Admit an exact bounded pair only while no other outcome is unresolved.
     * @param packet Caller-owned bytes copied before returning; later mutations are isolated.
     * @note Rejections preserve pending bytes and the last acknowledged identity.
     */
    void begin(std::span<const std::uint8_t> packet) {
      v20::body::require(!pending_, "CP23 unresolved transaction");
      const auto pair = composed::parse_pair(packet);
      v20::body::require(pair.epoch == epoch_ && (!acknowledged_ || pair.frame > *acknowledged_), "CP23 transaction epoch/frame");
      const auto expected = expected_ack(packet);
      pending_ = Pending {{packet.begin(), packet.end()}, expected, pair.frame};
    }

    /**
     * @brief Return byte-identical retained media after an unknown outcome or lost ACK.
     * @return Read-only view, valid only until ACK acceptance or object destruction.
     */
    std::span<const std::uint8_t> retry() const {
      v20::body::require(pending_.has_value(), "CP23 no pending transaction");
      return pending_->packet;
    }

    /**
     * @brief Match the entire CRC-valid JA23 without publishing banks or releasing owners.
     * @param bytes Complete peer reply; mismatches preserve the pending transaction.
     * @note Successful return retires only these private retry bytes. Publication,
     * reference transitions and real owner release require their separate gates.
     */
    void acknowledge(std::span<const std::uint8_t> bytes) {
      v20::body::require(pending_.has_value(), "CP23 no pending ACK");
      composed::parse_ack(bytes);
      v20::body::require(std::equal(bytes.begin(), bytes.end(), pending_->ack.begin(), pending_->ack.end()), "JA23 exact outstanding whole-pair ACK");
      acknowledged_ = pending_->frame;
      pending_.reset();
    }
  };
}  // namespace gamebub::v24::transaction
