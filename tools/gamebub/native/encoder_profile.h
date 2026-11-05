/**
 * @file tools/gamebub/native/encoder_profile.h
 * @brief Explicit optional wall-clock observations for offline native inner encoding.
 * @note These clocks add measurable overhead; default encoding supplies no observer.
 */
#pragma once

// standard includes
#include <array>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace gamebub::v20::encoder {
  /** @brief Nonoverlapping paid inner-encoder operations; no algorithm work is skipped. */
  enum class Stage : unsigned {
    validation,  ///< Request and exact analysis/reference binding checks.
    source,  ///< Original RGB8 to source-plane conversion, when required.
    forward,  ///< Residual preparation and forward DCT for one block.
    quantization,  ///< Quantization/bounds; legacy includes dequantization, budgeted keys defer it.
    reconstruction,  ///< Inverse/pixel placement; budgeted keys also recompute dequantization here.
    entropy,  ///< Complete coefficient entropy encoding for one plane.
    framing,  ///< GM01 header/map/payload serialization and inner CRC.
    tag,  ///< Canonical reconstructed-bank tag calculation.
    count  ///< Fixed array bound, never a valid observed operation.
  };

  /** @brief Stable diagnostic names, not protocol identifiers. */
  inline constexpr std::array<std::string_view, static_cast<unsigned>(Stage::count)> stage_names {
    "request_validation",
    "source_conversion",
    "forward_residual",
    "quantization",
    "inverse_reconstruction",
    "entropy",
    "inner_framing",
    "canonical_tag"
  };

  /** @brief Accumulated wall time and completed/aborted operation counts. */
  struct Bucket {
    std::uint64_t nanoseconds {}, calls {}, aborted {};  ///< Aborted calls retain partial paid work.
  };

  /** @brief Caller-owned single-thread observer, with no clocks read at construction. */
  class Profile {
  public:
    using Clock = std::uint64_t (*)() noexcept;  ///< Injectable monotonic nanosecond source.
    std::uint64_t attempts {}, clock_reads {}, clock_regressions {};  ///< Visible observer activity.

    /** @brief Read the platform steady clock only when explicit profiling requests it. */
    static std::uint64_t steady_now() noexcept {
      return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
    }

    /** @brief Bind a nonthrowing clock; null clocks are rejected before observation. */
    explicit Profile(Clock clock = steady_now):
        clock_(clock) {
      if (!clock) {
        throw std::invalid_argument("encoder profile clock");
      }
    }

    /** @brief Return one bounded stage without exposing mutable timing storage. */
    const Bucket &bucket(Stage stage) const {
      const auto index = static_cast<unsigned>(stage);
      if (index >= buckets_.size()) {
        throw std::invalid_argument("encoder profile stage");
      }
      return buckets_[index];
    }

  private:
    friend class StageScope;
    Clock clock_;  ///< Borrowed static/function clock; caller ensures its implementation remains valid.
    std::array<Bucket, static_cast<unsigned>(Stage::count)> buckets_ {};  ///< Bounded, allocation-free counters.

    /** @brief Count every explicit clock read, including aborted operations. */
    std::uint64_t read() noexcept {
      ++clock_reads;
      return clock_();
    }
  };

  /** @brief Noncopyable operation scope; null observers perform no clock reads. */
  class StageScope {
    Profile *profile_;  ///< Borrowed observer, valid through this scope's destruction.
    unsigned index_ {};  ///< Validated bounded stage index.
    std::uint64_t started_ {};  ///< First clock read, when enabled.

    /** @brief Complete once; a backwards injected clock cannot wrap unsigned duration. */
    void stop(bool completed) noexcept {
      if (auto *profile = std::exchange(profile_, nullptr)) {
        const auto ended = profile->read();
        auto &bucket = profile->buckets_[index_];
        ++bucket.calls;
        bucket.aborted += !completed;
        if (ended >= started_) {
          bucket.nanoseconds += ended - started_;
        } else {
          ++profile->clock_regressions;
        }
      }
    }

  public:
    /** @brief Begin one validated stage, or remain inert when profiling is disabled. */
    StageScope(Profile *profile, Stage stage):
        profile_(profile) {
      if (profile_) {
        profile_->bucket(stage);
        index_ = static_cast<unsigned>(stage);
        started_ = profile_->read();
      }
    }

    /** @brief A scope cannot duplicate an outstanding observation. */
    StageScope(const StageScope &) = delete;
    /** @brief A scope cannot transfer an observation through implicit moves. */
    StageScope(StageScope &&) = delete;
    /** @brief An active observation cannot be overwritten by assignment. */
    StageScope &operator=(const StageScope &) = delete;
    /** @brief An active observation cannot be overwritten by move assignment. */
    StageScope &operator=(StageScope &&) = delete;

    /** @brief Preserve partial paid work when an operation exits before explicit completion. */
    ~StageScope() {
      stop(false);
    }

    /** @brief Mark successful completion; repeated completion is harmless and reads no clock. */
    void finish() noexcept {
      stop(true);
    }
  };
}  // namespace gamebub::v20::encoder
