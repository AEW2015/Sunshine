/**
 * @file tools/gamebub/native/composed_sequence.h
 * @brief Bounded same-process independent CP23 source replay with explicit repetition.
 */
#pragma once

// standard includes
#include <algorithm>
#include <charconv>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

// local includes
#include "composed_encoder.h"
#include "encoder_profile_json.h"
#include "encoder_sequence.h"

namespace gamebub::v24::composed_sequence {
  using Json = v20::body_case::Json;  ///< Bounded diagnostic metadata, never protocol bytes.

  /** @brief Explicit finite independent-key workload; all optional modes default off. */
  struct Options {
    unsigned iterations = 1;  ///< At most1800 completed source attempts.
    bool repeat = false, budgeted_keys = false, profile_substages = false;  ///< Explicit independent flags.
  };

  /**
   * @brief Parse a strict finite count and unique explicit mode flags.
   * @param tokens Count followed by at most three recognized flags.
   * @return Valid bounded options; malformed, duplicate or unknown options throw.
   */
  inline Options parse(std::span<const std::string_view> tokens) {
    v20::body::require(!tokens.empty() && tokens.size() <= 4, "composed sequence option count");
    v20::body::require(!tokens[0].empty(), "composed sequence count1..1800");
    Options options;
    const auto parsed = std::from_chars(tokens[0].data(), tokens[0].data() + tokens[0].size(), options.iterations);
    v20::body::require(parsed.ec == std::errc() && parsed.ptr == tokens[0].data() + tokens[0].size() && options.iterations >= 1 && options.iterations <= 1800, "composed sequence count1..1800");
    for (const auto token : tokens.subspan(1)) {
      bool *flag = token == "--repeat" ? &options.repeat : token == "--budgeted-keys"   ? &options.budgeted_keys :
                                                         token == "--profile-substages" ? &options.profile_substages :
                                                                                          nullptr;
      v20::body::require(flag && !*flag, "composed sequence unknown/duplicate flag");
      *flag = true;
    }
    return options;
  }

  /**
   * @brief Replay original RGB8 sources in one process without retaining pixel snapshots.
   * @param path Existing hash-bound saved-source manifest; original clip is not reread.
   * @param options At most1800 independent fixtures, with repetition explicitly enabled.
   * @return Per-source identities, exact output hashes, paid work and bounded aggregate timings.
   * @note Codec epoch is iteration+1/frame0/generation1, not a live transport reset.
   */
  inline Json run(const std::filesystem::path &path, const Options &options) {
    using namespace v20;
    body::require(options.iterations >= 1 && options.iterations <= 1800, "composed sequence count1..1800");
    const auto began = benchmark::Clock::now();
    Json result {{"schema", "gamebub-cp23-independent-sequence-benchmark-v1"}, {"scope", "offline_same_process_independent_cp23_saved_sources"}, {"frames", Json::array()}};
    std::vector<std::uint64_t> encode_times, source_times, hash_times, iteration_times;
    std::string manifest_hash;
    unsigned completed = 0, cycles = 0, available = 0, accepted = 0, attempts = 0, skipped = 0;
    std::uint64_t metadata_ns = 0;
    while (completed < options.iterations) {
      const auto metadata_start = benchmark::Clock::now();
      sequence::Reader reader(path);
      Json cycle {{"frames", Json::array()}};
      reader.describe(cycle);
      if (cycles == 0) {
        available = static_cast<unsigned>(reader.size());
        body::require(options.repeat || options.iterations <= available, "composed sequence repeat not enabled");
        manifest_hash = cycle.at("source_manifest_sha256").get<std::string>();
        result["source_provenance"] = cycle.at("source_provenance");
        result["source_label"] = cycle.at("source_label");
        result["source_sequence_schema"] = cycle.at("source_sequence_schema");
      } else {
        body::require(reader.size() == available && cycle.at("source_manifest_sha256").get<std::string>() == manifest_hash, "composed sequence manifest changed during repeat");
      }
      metadata_ns += benchmark::elapsed(metadata_start);
      const auto count = std::min(options.iterations - completed, static_cast<unsigned>(reader.size()));
      for (unsigned index = 0; index < count; ++index) {
        const auto iteration_start = benchmark::Clock::now();
        Json row;
        std::weak_ptr<const candidate::Source> retired_source;
        {
          const auto source_start = benchmark::Clock::now();
          const auto pixels = reader.load(index);
          const auto source = std::make_shared<const candidate::Source>(std::span<const std::uint8_t>(pixels));
          retired_source = source;
          const auto source_ns = benchmark::elapsed(source_start);
          const auto encoded = refresh_encoder::encode(source, completed + 1, 0, composed::frame_cap, options.profile_substages, options.budgeted_keys);
          Json candidates = Json::array();
          for (const auto &attempt : encoded.attempts) {
            candidates.push_back({{"roi_scale", attempt.map.roi}, {"background_scale", attempt.map.background}, {"complete_bytes", attempt.complete_bytes}, {"accepted", attempt.accepted}, {"build_ns", attempt.build_ns}, {"framing_ns", attempt.framing_ns}, {"discard_ns", attempt.discard_ns}, {"analysis_ns", attempt.analysis_ns}, {"retire_ns", attempt.retire_ns}, {"reconstruction_skipped", attempt.reconstruction_skipped}});
            skipped += attempt.reconstruction_skipped;
          }
          const auto hash_start = benchmark::Clock::now();
          const auto packet_hash = encoded.accepted() ? Json(body_case::digest(encoded.packet)) : Json(nullptr);
          const auto ack_hash = encoded.accepted() ? Json(body_case::digest(encoded.ack)) : Json(nullptr);
          const auto output_hash_ns = benchmark::elapsed(hash_start);
          row = {{"iteration", completed}, {"cycle", cycles}, {"codec_epoch", completed + 1}, {"codec_frame", 0}, {"hud_generation", 1}, {"accepted", encoded.accepted()}, {"packet_bytes", encoded.packet.size()}, {"packet_sha256", packet_hash}, {"ack_sha256", ack_hash}, {"attempts", candidates}, {"hud_prepare_ns", encoded.hud_prepare_ns}, {"validation_ns", encoded.validation_ns}, {"cleanup_ns", encoded.cleanup_ns}, {"encode_total_ns", encoded.total_ns}, {"source_prepare_ns", source_ns}, {"output_hash_ns", output_hash_ns}, {"inner_profile", encoded.inner_profile ? encoder::profile_json(*encoded.inner_profile) : Json(nullptr)}};
          accepted += encoded.accepted();
          attempts += static_cast<unsigned>(encoded.attempts.size());
          encode_times.push_back(encoded.total_ns);
          source_times.push_back(source_ns);
          hash_times.push_back(output_hash_ns);
        }
        body::require(retired_source.expired(), "composed sequence retained source snapshot");
        row["source_snapshot_retired"] = true;
        const auto iteration_ns = benchmark::elapsed(iteration_start);
        row["iteration_wall_ns"] = iteration_ns;
        iteration_times.push_back(iteration_ns);
        cycle["frames"].push_back(std::move(row));
        ++completed;
      }
      reader.describe(cycle);
      for (auto &row : cycle["frames"]) {
        result["frames"].push_back(std::move(row));
      }
      ++cycles;
    }
    result["requested_iterations"] = options.iterations;
    result["completed_iterations"] = completed;
    result["accepted_frames"] = accepted;
    result["software_acks_constructed"] = accepted;
    result["rejected_frames"] = completed - accepted;
    result["candidate_attempts"] = attempts;
    result["skipped_reconstructions"] = skipped;
    result["source_frames_available"] = available;
    result["unique_sources_loaded"] = std::min(options.iterations, available);
    result["cycles"] = cycles;
    result["repeat_requested"] = options.repeat;
    result["repeat_occurred"] = cycles > 1;
    result["budgeted_keys_enabled"] = options.budgeted_keys;
    result["profile_substages_enabled"] = options.profile_substages;
    result["source_manifest_sha256"] = manifest_hash;
    result["metadata_validation_ns"] = metadata_ns;
    result["timings_ns"] = {{"encode", benchmark::distribution(encode_times)}, {"source_prepare", benchmark::distribution(source_times)}, {"output_hash", benchmark::distribution(hash_times)}, {"iteration_wall", benchmark::distribution(iteration_times)}};
    result["source_snapshots_retired"] = completed;
    result["maximum_active_source_snapshots"] = 1;
    result["metadata_row_bound"] = 1800;
    result["retained_metadata_rows"] = completed;
    result["source_pixels_retained_after_iteration"] = false;
    result["original_clip_reverified"] = false;
    result["hardware_measured"] = false;
    result["network_measured"] = false;
    result["capture_or_clip_decode_measured"] = false;
    result["process_cpu_measured"] = false;
    result["peak_memory_measured"] = false;
    result["stateful_stream"] = false;
    result["reference_publication"] = false;
    result["transport_epochs_exercised"] = false;
    result["timing_boundaries"] = "same process wall includes input/hash/snapshot/encoding/validation/retirement/metadata; output serialization/stdout and external resource sampling are separate; no clock overhead subtracted";
    result["inner_stage_boundaries"] = options.budgeted_keys ? "coarse analysis_ns includes conversion/forward; quantization excludes dequantization; selected inverse includes recomputed dequantization; retire_ns is inside build_ns" : "fine source/forward stages; quantization includes dequantization; inverse excludes it; frame-local cleanup remains paid";
    result["benchmark_wall_ns"] = benchmark::elapsed(began);
    return result;
  }
}  // namespace gamebub::v24::composed_sequence
