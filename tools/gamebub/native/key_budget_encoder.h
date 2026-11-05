/**
 * @file tools/gamebub/native/key_budget_encoder.h
 * @brief Explicit independent-key preparation that finalizes only a proven size fit.
 * @note The legacy FrameBuilder is unchanged. No P frames, publication or wire mode is added.
 */
#pragma once

// standard includes
#include <array>
#include <chrono>
#include <memory>
#include <optional>
#include <vector>

// local includes
#include "inner_encoder.h"

namespace gamebub::v20::encoder {
  /** @brief Actual entropy/framing result, with a valid encoded key only when it fits. */
  struct KeyAttempt {
    std::size_t inner_bytes {};  ///< Actual complete GM01 size, including CRC, on every attempt.
    std::optional<candidate::BuildResult> encoded;  ///< Present only after full reconstruction/tag finalization.
    std::uint64_t analysis_ns {}, retire_ns {};  ///< Paid frame analysis and temporary/source retirement.
    bool reconstruction_skipped {};  ///< True only when actual encoded size proves nonadmission.
  };

  /**
   * @brief Own one immutable frame analysis across at most four ordered key candidates.
   * @note This separate API never passes a missing/invalid stored tag through legacy policies.
   */
  class KeyBudgetBuilder {
    std::unique_ptr<const Analysis> analysis_;  ///< Exact frame-local raw forward coefficients.
    Profile *profile_ {};  ///< Optional borrowed observer, valid through all calls.
    unsigned attempts_ {};  ///< Actual completed entropy/framing attempts.
    bool analysis_built_ {}, retired_ {}, failed_ {};  ///< Explicit lifetime and terminal state.

    /** @brief Measure only paid local wall time, without source/network clock correlation. */
    static std::uint64_t elapsed(std::chrono::steady_clock::time_point start) {
      return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - start).count();
    }

  public:
    /** @brief Bind an optional observer; construction allocates or reads no clocks. */
    explicit KeyBudgetBuilder(Profile *profile = nullptr) noexcept:
        profile_(profile) {}

    /** @brief Analysis and its input owner cannot be duplicated. */
    KeyBudgetBuilder(const KeyBudgetBuilder &) = delete;
    /** @brief A live frame identity cannot be transferred away from its caller. */
    KeyBudgetBuilder(KeyBudgetBuilder &&) = delete;
    /** @brief Retained analysis cannot be replaced through assignment. */
    KeyBudgetBuilder &operator=(const KeyBudgetBuilder &) = delete;
    /** @brief Retained analysis cannot be replaced through move assignment. */
    KeyBudgetBuilder &operator=(KeyBudgetBuilder &&) = delete;

    /** @brief Idempotently release this private analysis and refuse further candidate calls. */
    void retire() noexcept {
      analysis_.reset();
      retired_ = true;
    }

    /** @brief Return actual completed payload attempts, including oversized candidates. */
    unsigned attempts() const {
      return attempts_;
    }

    /** @brief Return whether one immutable source/forward analysis was actually built. */
    unsigned analysis_builds() const {
      return analysis_built_ ? 1 : 0;
    }

    /** @brief Inspect terminal explicit/automatic retirement. */
    bool retired() const {
      return retired_;
    }

    /** @brief Inspect terminal validation/encoding failure, which always drops retained inputs. */
    bool failed() const {
      return failed_;
    }

    /** @brief Inspect bounded retained coefficient bytes, excluding snapshot/object overhead. */
    std::size_t coefficient_bytes() const {
      return analysis_ ? analysis_->coefficient_bytes() : 0;
    }

    /**
     * @brief Encode actual key entropy, then reconstruct/tag only if its full GM01 fits.
     * @param request Original independent key identity; only the ordered map may change.
     * @param max_inner_bytes Caller-derived inner budget, including GM01 header and CRC.
     * @return Actual size on rejection, or fully valid exact bytes/tag on admission.
     * @note Budget zero still pays quantization, entropy and framing. Rejected private
     * payloads/coefficients are retired before return; no malformed BuildResult escapes.
     */
    KeyAttempt attempt(const candidate::BuildRequest &request, std::size_t max_inner_bytes) {
      try {
        if (profile_) {
          ++profile_->attempts;
        }
        StageScope validation(profile_, Stage::validation);
        body::require(!retired_ && !failed_, "budgeted key builder retired");
        body::require(request.key && !request.promoted && !request.reference && request.reference_slot == 255 && request.destination_slot == 0, "budgeted encoder requires independent key");
        body::require(attempts_ < candidate::maps.size() && request.map == candidate::maps[attempts_], "budgeted key map order");
        validate_request(request);
        if (analysis_) {
          analysis_->require_identity(request);
        }
        validation.finish();
        KeyAttempt outcome;
        if (!analysis_) {
          const auto started = std::chrono::steady_clock::now();
          analysis_ = analyze(request);
          outcome.analysis_ns = elapsed(started);
          analysis_built_ = true;
        }
        constexpr unsigned w = candidate::width, h = candidate::height;
        const auto scales = scale_map(request.map);
        std::array<std::vector<block_t>, 3> coefficients;
        std::array<std::vector<std::uint8_t>, 3> payloads;
        for (unsigned p = 0; p < 3; ++p) {
          const unsigned pw = p ? w / 2 : w, ph = p ? h / 2 : h;
          const unsigned bw = (pw + 7) / 8, bh = (ph + 7) / 8;
          const auto analyzed = analysis_->plane(p);
          coefficients[p].resize(bw * bh);
          for (unsigned by = 0; by < bh; ++by) {
            for (unsigned bx = 0; bx < bw; ++bx) {
              const auto &raw = analyzed[by * bw + bx];
              auto &quantized = coefficients[p][by * bw + bx];
              const auto scale = scales[(p ? by : by / 2) * 45 + (p ? bx : bx / 2)];
              StageScope quantization(profile_, Stage::quantization);
              for (unsigned k = 0; k < 64; ++k) {
                const auto q = std::clamp(((p ? body::qc : body::qy)[k] * int(scale) + 8) / 16, 1, 255);
                quantized[k] = (raw[k] >= 0 ? 1 : -1) * ((std::abs(raw[k]) + q / 2) / q);
                body::require(quantized[k] >= -2048 && quantized[k] <= 2048, "quantized encoder coefficient domain");
              }
              quantization.finish();
            }
          }
          StageScope entropy(profile_, Stage::entropy);
          payloads[p] = encode_coefficients(coefficients[p], bw);
          entropy.finish();
        }
        StageScope framing(profile_, Stage::framing);
        std::vector<std::uint8_t> inner {'G', 'M', '0', '1', 1, 1};
        append32(inner, request.epoch);
        append32(inner, request.frame_id);
        append32(inner, 0xffffffffU);
        append16(inner, w);
        append16(inner, h);
        append16(inner, 0);
        append16(inner, 0);
        append16(inner, 45);
        append16(inner, 30);
        append32(inner, (scales.size() + 3) / 4);
        for (const auto &payload : payloads) {
          append32(inner, static_cast<std::uint32_t>(payload.size()));
        }
        for (std::size_t i = 0; i < scales.size(); i += 4) {
          unsigned byte = 0;
          for (unsigned j = 0; j < 4 && i + j < scales.size(); ++j) {
            const auto code = scales[i + j] == 8 ? 0 : scales[i + j] == 16 ? 1 :
                                                                             2;
            byte |= code << (6 - 2 * j);
          }
          inner.push_back(static_cast<std::uint8_t>(byte));
        }
        for (const auto &payload : payloads) {
          inner.insert(inner.end(), payload.begin(), payload.end());
        }
        seal(inner);
        outcome.inner_bytes = inner.size();
        framing.finish();
        ++attempts_;
        body::Planes reconstruction;
        if (inner.size() <= max_inner_bytes) {
          for (unsigned p = 0; p < 3; ++p) {
            const unsigned pw = p ? w / 2 : w, ph = p ? h / 2 : h;
            const unsigned bw = (pw + 7) / 8, bh = (ph + 7) / 8;
            reconstruction[p].resize(pw * ph);
            for (unsigned by = 0; by < bh; ++by) {
              for (unsigned bx = 0; bx < bw; ++bx) {
                StageScope inverse_stage(profile_, Stage::reconstruction);
                const auto &quantized = coefficients[p][by * bw + bx];
                const auto scale = scales[(p ? by : by / 2) * 45 + (p ? bx : bx / 2)];
                block_t dequantized, decoded;
                for (unsigned k = 0; k < 64; ++k) {
                  const auto q = std::clamp(((p ? body::qc : body::qy)[k] * int(scale) + 8) / 16, 1, 255);
                  dequantized[k] = quantized[k] * q;
                }
                body::require(inverse(dequantized, decoded), "encoder inverse domain");
                for (unsigned y = 0; y < 8 && by * 8 + y < ph; ++y) {
                  for (unsigned x = 0; x < 8 && bx * 8 + x < pw; ++x) {
                    reconstruction[p][std::size_t(by * 8 + y) * pw + bx * 8 + x] = std::clamp(decoded[y * 8 + x] + 128, 0, 255);
                  }
                }
                inverse_stage.finish();
              }
            }
          }
          StageScope tag(profile_, Stage::tag);
          const auto stored_tag = body::canonical_tag(reconstruction, w, h);
          tag.finish();
          body::require(stored_tag != body::Tag {}, "budgeted key stored tag");
          outcome.encoded.emplace(candidate::BuildResult {std::move(inner), stored_tag});
        } else {
          outcome.reconstruction_skipped = true;
        }
        const auto cleanup = std::chrono::steady_clock::now();
        std::array<std::vector<block_t>, 3>().swap(coefficients);
        std::array<std::vector<std::uint8_t>, 3>().swap(payloads);
        body::Planes().swap(reconstruction);
        std::vector<std::uint8_t>().swap(inner);
        if (outcome.encoded || attempts_ == candidate::maps.size()) {
          retire();
        }
        outcome.retire_ns = elapsed(cleanup);
        return outcome;
      } catch (...) {
        retire();
        failed_ = true;
        throw;
      }
    }
  };
}  // namespace gamebub::v20::encoder
