/**
 * @file tools/gamebub/native/encoder_benchmark.h
 * @brief Bounded offline continuous generated-motion encoder profiling with real reference evolution.
 */
#pragma once

// standard includes
#include <algorithm>
#include <chrono>
#include <functional>
#include <limits>
#include <memory>

// local includes
#include "body_case.h"
#include "inner_encoder.h"
#include "patch_encoder.h"

namespace gamebub::v20::benchmark {
  /** @brief Explicit finite offline workload parameters; no target rate or network endpoint. */
  struct Options {
    unsigned frames = 60;  ///< Number of generated source frames, from1 through1800.
    unsigned shift_pixels = 1;  ///< Circular horizontal movement per frame, from0 through719.
    unsigned promote_every = 30;  ///< Promotion period, or0 to disable.
    unsigned key_every = 300;  ///< Key refresh period, or0 to disable after initial admission.
    bool reuse_analysis = false;  ///< Reuse only this frame's source conversion/forward work across maps.
    bool record_output_hashes = false;  ///< Optional paid packet SHA256 for saved-frame comparisons.
  };

  /** @brief Monotonic local work clock; never compared with a receiver clock. */
  using Clock = std::chrono::steady_clock;
  /** @brief JSON offline result document, not a wire message. */
  using Json = body_case::Json;
  /**
   * @brief Load or generate exactly one owned RGB8 canvas for the requested source index.
   */
  using FrameProvider = std::function<std::vector<std::uint8_t>(unsigned)>;

  /**
   * @brief Validate every workload limit before source allocation or encoding.
   * @param options Finite options to validate.
   */
  inline void validate(const Options &options) {
    body::require(options.frames >= 1 && options.frames <= 1800, "benchmark frame limit1..1800");
    body::require(options.shift_pixels < candidate::width, "benchmark shift limit0..719");
    body::require(options.promote_every <= 1800 && options.key_every <= 1800, "benchmark reference period0..1800");
  }

  /**
   * @brief Generate an owned deterministic horizontal rotation without vertical movement or scaling.
   * @param original Exact packed720x480 RGB8 source, retained unmodified.
   * @param index Generated frame index below1800.
   * @param shift_pixels Horizontal pixels per frame, zero for a static control.
   * @return One complete generated RGB8 canvas; this is not fresh game footage.
   */
  inline std::vector<std::uint8_t> moving_rgb(std::span<const std::uint8_t> original, unsigned index, unsigned shift_pixels) {
    body::require(original.size() == candidate::width * candidate::height * 3, "benchmark RGB8 geometry");
    body::require(index < 1800 && shift_pixels < candidate::width, "benchmark motion bounds");
    const auto shift = index * shift_pixels % candidate::width;
    std::vector<std::uint8_t> result(original.size());
    for (unsigned y = 0; y < candidate::height; ++y) {
      for (unsigned x = 0; x < candidate::width; ++x) {
        const auto src = (std::size_t(y) * candidate::width + x) * 3;
        const auto dst = (std::size_t(y) * candidate::width + (x + shift) % candidate::width) * 3;
        std::copy_n(original.begin() + src, 3, result.begin() + dst);
      }
    }
    return result;
  }

  /** @brief Return local elapsed nanoseconds for a completed host operation. */
  inline std::uint64_t elapsed(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
  }

  /**
   * @brief Summarize bounded timings with nearest-rank percentiles and explicit empty behavior.
   * @param values At most1800 local timing samples in nanoseconds.
   * @return Sample count, total and p50/p95/p99/maximum; empty samples have zero values.
   */
  inline Json distribution(std::vector<std::uint64_t> values) {
    body::require(values.size() <= 1800, "benchmark timing history bound");
    std::sort(values.begin(), values.end());
    std::uint64_t total = 0;
    for (auto value : values) {
      body::require(value <= std::numeric_limits<std::uint64_t>::max() - total, "benchmark timing sum overflow");
      total += value;
    }
    const auto percentile = [&](unsigned percent) {
      return values.empty() ? std::uint64_t(0) : values[(values.size() * percent + 99) / 100 - 1];
    };
    return {{"count", values.size()}, {"total", total}, {"p50", percentile(50)}, {"p95", percentile(95)}, {"p99", percentile(99)}, {"max", values.empty() ? 0 : values.back()}};
  }

  /**
   * @brief Profile a finite frame provider with all candidate and software reference costs.
   * @param provider Serialized source loader, returning one exact RGB8 canvas per call.
   * @param options Finite workload with explicit refresh/promotion periods.
   * @return Scoped work/cost report; no capture, pacing, RF or hardware playback is measured.
   */
  inline Json run_frames(const FrameProvider &provider, const Options &options = {}) {
    validate(options);
    body::require(bool(provider), "benchmark source provider");
    candidate::Policy policy;
    body::State receiver;
    Json rows = Json::array();
    std::vector<std::uint64_t> source_times, admission_times, decode_times, roundtrip_times, identity_times;
    std::uint64_t accepted = 0, rejected = 0, total_bytes = 0, attempts = 0, losing_attempts = 0;
    std::uint64_t keys = 0, promotions = 0, ordinary = 0;
    std::uint64_t analysis_builds = 0, analysis_reuses = 0;
    std::size_t maximum_analysis_bytes = 0;
    const auto began = Clock::now();
    for (unsigned index = 0; index < options.frames; ++index) {
      const auto frame_start = Clock::now();
      const auto moved = provider(index);
      body::require(moved.size() == candidate::width * candidate::height * 3, "benchmark RGB8 geometry");
      const auto source = std::make_shared<const candidate::Source>(moved);
      const auto source_ns = elapsed(frame_start);
      source_times.push_back(source_ns);
      const bool force_key = options.key_every && index % options.key_every == 0;
      const bool promote = options.promote_every && index % options.promote_every == 0;
      const auto prepare_start = Clock::now();
      candidate::Prepared prepared;
      unsigned frame_analysis_builds = 0, frame_analysis_reuses = 0;
      std::size_t frame_analysis_bytes = 0;
      if (options.reuse_analysis) {
        // Destroy all frame-local analysis before commit or another source frame.
        encoder::FrameBuilder builder;
        prepared = policy.prepare(source, index, encoder::encode_patches, std::ref(builder), force_key, promote);
        frame_analysis_builds = builder.analysis_builds();
        frame_analysis_reuses = builder.attempts() ? builder.attempts() - 1 : 0;
        frame_analysis_bytes = builder.coefficient_bytes();
      } else {
        prepared = policy.prepare(source, index, encoder::encode_patches, encoder::encode_inner, force_key, promote);
      }
      const auto admission_ns = elapsed(prepare_start);
      admission_times.push_back(admission_ns);
      analysis_builds += frame_analysis_builds;
      analysis_reuses += frame_analysis_reuses;
      maximum_analysis_bytes = std::max(maximum_analysis_bytes, frame_analysis_bytes);
      const auto &metrics = prepared.metrics();
      Json paid = Json::array();
      for (const auto &attempt : metrics.attempts) {
        paid.push_back({{"roi", attempt.map.roi}, {"background", attempt.map.background}, {"inner_bytes", attempt.inner_bytes}, {"complete_bytes", attempt.complete_bytes}, {"build_ns", attempt.build_ns}, {"validation_ns", attempt.validate_ns}, {"discard_ns", attempt.discard_ns}, {"accepted", attempt.accepted}});
        ++attempts;
        losing_attempts += !attempt.accepted;
      }
      Json row {{"id", index}, {"accepted", prepared.accepted()}, {"reason", metrics.reason}, {"source_prepare_ns", source_ns}, {"admission_ns", admission_ns}, {"patch_prepare_ns", metrics.patch_prepare_ns}, {"patch_bytes", metrics.patch_bytes}, {"attempts", paid}};
      row["analysis_builds"] = frame_analysis_builds;
      row["analysis_reuses"] = frame_analysis_reuses;
      row["analysis_coefficient_bytes"] = frame_analysis_bytes;
      if (options.record_output_hashes) {
        row["packet_sha256"] = nullptr;
        row["output_identity_ns"] = 0;
      }
      if (prepared.accepted()) {
        const auto packet = policy.commit(prepared);
        const auto decode_start = Clock::now();
        body::Frame decoded;
        std::string error;
        const bool valid = body::decode(packet, receiver, decoded, error);
        body::require(valid, error.c_str());
        const auto decode_ns = elapsed(decode_start);
        decode_times.push_back(decode_ns);
        body::require(decoded.id == index && policy.acknowledge(decoded.feedback), "benchmark AF03/reference evolution");
        body::require(policy.pending() == 0 && !policy.active() && policy.readers(0) == 0 && policy.readers(1) == 0, "benchmark outstanding ownership");
        keys += packet[5] == 1;
        promotions += packet[5] == 2;
        ordinary += packet[5] == 0;
        total_bytes += packet.size();
        ++accepted;
        row["packet_bytes"] = packet.size();
        row["frame_kind"] = packet[5];
        row["software_decode_ns"] = decode_ns;
        row["confirmed_frame"] = receiver.last_frame;
        if (options.record_output_hashes) {
          const auto identity_start = Clock::now();
          row["packet_sha256"] = body_case::digest(packet);
          const auto identity_ns = elapsed(identity_start);
          row["output_identity_ns"] = identity_ns;
          identity_times.push_back(identity_ns);
        }
      } else {
        ++rejected;
        body::require(!policy.active() && policy.pending() == 0, "benchmark rejected ownership");
        if (options.record_output_hashes) {
          identity_times.push_back(0);
        }
      }
      const auto frame_ns = elapsed(frame_start);
      roundtrip_times.push_back(frame_ns);
      row["offline_roundtrip_ns"] = frame_ns;
      rows.push_back(std::move(row));
    }
    const auto wall_ns = elapsed(began);
    Json result {{"schema", "gamebub-v20-encoder-frames-benchmark-v1"}, {"scope", "offline_finite_frames_encode_and_software_decode"}, {"profiling_not_playback", true}, {"capture_measured", false}, {"network_measured", false}, {"hardware_measured", false}, {"cpu_and_peak_memory_measured", false}, {"width", candidate::width}, {"height", candidate::height}, {"shift_pixels", options.shift_pixels}, {"promote_every", options.promote_every}, {"key_every", options.key_every}, {"analysis_reuse", options.reuse_analysis}, {"analysis_builds", analysis_builds}, {"analysis_reuses", analysis_reuses}, {"maximum_analysis_coefficient_bytes", maximum_analysis_bytes}, {"analysis_paid_in_first_build", options.reuse_analysis}, {"analysis_accounting", options.reuse_analysis ? "first build includes frame analysis; later maps reuse coefficients" : "every build pays conversion and forward analysis"}, {"requested_frames", options.frames}, {"accepted_frames", accepted}, {"rejected_frames", rejected}, {"software_decoded_frames", accepted}, {"key_frames", keys}, {"promoted_frames", promotions}, {"ordinary_frames", ordinary}, {"attempts", attempts}, {"losing_attempts", losing_attempts}, {"complete_bytes", total_bytes}, {"complete_frame_cap", 49152}, {"final_confirmed_frame", receiver.last_frame}, {"wall_ns", wall_ns}, {"timings_ns", {{"source_prepare", distribution(source_times)}, {"admission", distribution(admission_times)}, {"software_decode", distribution(decode_times)}, {"offline_roundtrip", distribution(roundtrip_times)}}}, {"frames", rows}};
    if (options.record_output_hashes) {
      result["output_identity_recorded"] = true;
      result["timings_ns"]["output_identity"] = distribution(identity_times);
    }
    return result;
  }

  /**
   * @brief Preserve the generated-motion workload and report schema around the finite loop.
   * @param original Exact original RGB8 seed; never modified or replaced by RGB565 expansion.
   * @param options Finite generated workload with explicit refresh/promotion periods.
   * @return Existing generated-motion report, with no saved-footage or capture claim.
   */
  inline Json run(std::span<const std::uint8_t> original, const Options &options = {}) {
    validate(options);
    body::require(original.size() == candidate::width * candidate::height * 3, "benchmark RGB8 geometry");
    const auto source_hash = body_case::digest(original);
    auto result = run_frames([&](unsigned index) {
      return moving_rgb(original, index, options.shift_pixels);
    },
                             options);
    body::require(body_case::digest(original) == source_hash, "benchmark seed mutation");
    result["schema"] = "gamebub-v20-encoder-benchmark-v1";
    result["scope"] = "offline_generated_motion_encode_and_software_decode";
    result["source_rgb_sha256"] = source_hash;
    return result;
  }

  /**
   * @brief Load only a hash-bound frozen RGB8 seed, then create a clean continuous workload.
   * @param path Existing body/encoder case JSON with a confined source descriptor.
   * @param options Finite benchmark options; checked before reading input files.
   * @return Scoped benchmark report; original packet/pre-banks are not replayed or concatenated.
   */
  inline Json run_case(const std::filesystem::path &path, const Options &options = {}) {
    validate(options);
    const auto metadata = Json::parse(body_case::read_file(path, 1024 * 1024));
    body::require(metadata.at("schema") == "gamebub-v20-body-case-v1", "benchmark source case schema");
    body::require(body_case::number(metadata.at("geometry").at("width"), 720) == 720 && body_case::number(metadata.at("geometry").at("height"), 480) == 480, "benchmark source canvas");
    body_case::shape(metadata.at("source_rgb"), "|u1", {480, 720, 3});
    const auto original = body_case::blob(path.parent_path(), metadata.at("source_rgb"), 720 * 480 * 3);
    auto result = run(original, options);
    result["source_case"] = metadata.at("label");
    result["source_validation"] = "hash-bound RGB8 seed only; original packet/pre-banks not replayed";
    return result;
  }
}  // namespace gamebub::v20::benchmark
