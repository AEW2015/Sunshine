/**
 * @file tools/gamebub/native/composed_encoder.h
 * @brief Offline independent CP23 refresh encoder matching MoonBub4025d355 JointSender.
 * @note No P frames, HD22, reference publication, transport or hardware endpoint.
 */
#pragma once

// standard includes
#include <chrono>

// local includes
#include "composed_refresh.h"
#include "inner_encoder.h"
#include "patch_encoder.h"

namespace gamebub::v24::refresh_encoder {
  /** @brief Paid complete-pair attempt, including unsuccessful quantizer candidates. */
  struct Attempt {
    v20::candidate::Map map;  ///< Ordered frozen quantizer choice.
    std::size_t complete_bytes {};  ///< Full CP23 bytes, never the AR03-only size.
    std::uint64_t build_ns {}, framing_ns {}, discard_ns {};  ///< Measured paid stages.
    bool accepted {};  ///< First complete pair within the requested cap.
  };

  /** @brief Owned private result, with no sender/reference state mutation. */
  struct Result {
    std::vector<std::uint8_t> packet;  ///< Empty when every complete pair exceeds the cap.
    std::array<std::uint8_t, 134> ack {};  ///< Independently reconstructed JA23 when accepted.
    std::vector<Attempt> attempts;  ///< All paid candidates in declared order.
    std::uint64_t hud_prepare_ns {}, validation_ns {}, cleanup_ns {}, total_ns {};  ///< Paid patch/tag/hash/decode/release work.
    std::size_t hud_bytes {};  ///< Complete HC22 including its CRC.

    /** @brief Report admission without implying publication or playback. */
    bool accepted() const {
      return !packet.empty();
    }
  };

  /** @brief Convert one measured steady-clock interval to nanoseconds. */
  inline std::uint64_t elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - start).count();
  }

  /**
   * @brief Prepare a full, nonreferenced HC22 with four exact LEGACY patches.
   * @param source Original fixed-canvas source, with RGB565 derived from original RGB8.
   * @param epoch Nonzero, nonsentinel independent codec epoch.
   * @param frame Nonsentinel frame identity.
   * @return Complete HC22 generation1, destination0, no reference.
   * @note Generation1 is a fresh independent transaction, not a same-epoch stateful HUD sender.
   */
  inline std::vector<std::uint8_t> hud(const v20::candidate::Source &source, std::uint32_t epoch, std::uint32_t frame) {
    composed::check_id(epoch, true);
    composed::check_id(frame);
    v20::body::require(source.rgb8().size() == 720 * 480 * 3, "CP23 original RGB8 required");
    const auto patches = v20::encoder::encode_patches(source);
    std::vector<std::uint8_t> canonical;
    canonical.reserve(42272);
    for (const auto rect : v20::candidate::rectangles) {
      for (auto value : {rect.x, rect.y, rect.width, rect.height}) {
        canonical.push_back(static_cast<std::uint8_t>(value));
        canonical.push_back(static_cast<std::uint8_t>(value >> 8));
      }
      for (unsigned y = rect.y; y < rect.y + rect.height; ++y) {
        for (unsigned x = rect.x; x < rect.x + rect.width; ++x) {
          const auto word = source.words()[y * 720 + x];
          canonical.push_back(static_cast<std::uint8_t>(word));
          canonical.push_back(static_cast<std::uint8_t>(word >> 8));
        }
      }
    }
    const auto tag = composed::digest(canonical);
    std::vector<std::uint8_t> bytes(79);
    std::copy_n("HC22", 4, bytes.begin());
    bytes[4] = 1;
    v20::body::put32(bytes, 5, epoch);
    v20::body::put32(bytes, 9, frame);
    v20::body::put32(bytes, 13, 1);
    bytes[18] = 255;
    v20::body::put32(bytes, 19, 0xffffffffU);
    v20::body::put32(bytes, 23, 0xffffffffU);
    std::copy(tag.begin(), tag.end(), bytes.begin() + 43);
    for (unsigned i = 0; i < patches.size(); ++i) {
      v20::body::put32(bytes, 59 + 4 * i, static_cast<std::uint32_t>(patches[i].size()));
      bytes.insert(bytes.end(), patches[i].begin(), patches[i].end());
    }
    v20::encoder::seal(bytes);
    composed::hud_identity(bytes);
    return bytes;
  }

  /** @brief Frame a patch-free independent AR03 key without fixture/JSON dependencies. */
  inline std::vector<std::uint8_t> base(const v20::candidate::BuildRequest &request, const v20::candidate::BuildResult &built) {
    std::vector<std::uint8_t> bytes(61);
    std::copy_n("AR03", 4, bytes.begin());
    bytes[4] = 3;
    bytes[5] = 1;
    v20::body::put32(bytes, 6, request.epoch);
    v20::body::put32(bytes, 10, request.frame_id);
    bytes[14] = 255;
    v20::body::put32(bytes, 16, 0xffffffffU);
    std::copy(built.stored_tag.begin(), built.stored_tag.end(), bytes.begin() + 36);
    v20::body::put32(bytes, 52, static_cast<std::uint32_t>(built.inner.size()));
    bytes.insert(bytes.end(), built.inner.begin(), built.inner.end());
    v20::encoder::seal(bytes);
    return bytes;
  }

  /**
   * @brief Encode one fresh independent key and LEGACY HUD using first complete CP23 fit.
   * @param source Immutable original RGB8 snapshot, never expanded from RGB565.
   * @param epoch Fresh independent codec epoch, without transport/reset claims.
   * @param frame Frame identity within that independent fixture.
   * @param cap Complete CP23 limit, at most49152; smaller limits support offline cap studies.
   * @return Owned complete pair, exact reconstructed ACK, and all paid attempt metrics.
   * @note CP23 costs124 more framing bytes than AR03 containing the same four patches.
   */
  inline Result encode(std::shared_ptr<const v20::candidate::Source> source, std::uint32_t epoch, std::uint32_t frame, std::size_t cap = composed::frame_cap) {
    const auto start = std::chrono::steady_clock::now();
    v20::body::require(source != nullptr && cap >= 256 && cap <= composed::frame_cap, "CP23 source/cap");
    Result result;
    const auto hud_start = std::chrono::steady_clock::now();
    auto hud_packet = hud(*source, epoch, frame);
    result.hud_prepare_ns = elapsed(hud_start);
    result.hud_bytes = hud_packet.size();
    auto builder = std::make_unique<v20::encoder::FrameBuilder>();
    for (const auto map : v20::candidate::maps) {
      Attempt attempt {map};
      const v20::candidate::BuildRequest request {source, nullptr, epoch, frame, 255, 0, true, false, map};
      auto tick = std::chrono::steady_clock::now();
      auto built = (*builder)(request);
      attempt.build_ns = elapsed(tick);
      tick = std::chrono::steady_clock::now();
      auto base_packet = base(request, built);
      attempt.complete_bytes = composed::pair_overhead + base_packet.size() + hud_packet.size();
      attempt.accepted = attempt.complete_bytes <= cap;
      if (attempt.accepted) {
        result.packet = composed::serialize_pair({epoch, frame, std::move(base_packet), hud_packet});
      }
      attempt.framing_ns = elapsed(tick);
      tick = std::chrono::steady_clock::now();
      std::vector<std::uint8_t>().swap(built.inner);
      std::vector<std::uint8_t>().swap(base_packet);
      attempt.discard_ns = elapsed(tick);
      result.attempts.push_back(attempt);
      if (attempt.accepted) {
        tick = std::chrono::steady_clock::now();
        result.ack = refresh::decode_legacy_refresh(result.packet).ack;
        result.validation_ns = elapsed(tick);
        break;
      }
    }
    const auto cleanup = std::chrono::steady_clock::now();
    builder.reset();
    std::vector<std::uint8_t>().swap(hud_packet);
    result.cleanup_ns = elapsed(cleanup);
    result.total_ns = elapsed(start);
    return result;
  }
}  // namespace gamebub::v24::refresh_encoder
