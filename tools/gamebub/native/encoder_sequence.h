/**
 * @file tools/gamebub/native/encoder_sequence.h
 * @brief Finite hash-bound saved-frame input for native offline encoder profiling.
 * @note This loads exported source pixels, not a video capture, network or hardware path.
 */
#pragma once

// standard includes
#include <optional>

// local includes
#include "encoder_benchmark.h"

namespace gamebub::v20::sequence {
  inline constexpr unsigned frame_bytes = 720 * 480 * 3;  ///< One exact RGB8 input canvas.
  inline constexpr unsigned manifest_limit = 1024 * 1024;  ///< Bound before JSON parsing.
  inline constexpr std::string_view schema = "gamebub-v20-rgb8-sequence-v1";  ///< Portable source manifest, not a wire format.
  inline constexpr std::string_view resampling_policy = "existing clip_frames: source at or before sample; ceil offset to sampling grid";  ///< Frozen source selection semantics.
  inline constexpr std::string_view native_policy = "no resampling: unique decoded native frames; skip before requested relative PTS offset";  ///< Native frames retain original timestamps.
  inline constexpr std::string_view canvas_policy = "existing canvas: aspect-preserving fit into centered720x405 within720x480";  ///< Existing fixed canvas placement.

  /**
   * @brief Require canonical lowercase SHA256 text before any source frame is read.
   * @param text Declared digest for an original clip or exported frame.
   */
  inline void check_hash(const std::string &text) {
    body::require(text.size() == 64 && std::all_of(text.begin(), text.end(), [](char ch) {
                    return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
                  }),
                  "sequence SHA256 format");
  }

  /**
   * @brief Validate bounded sequence metadata, then read only one source frame per call.
   * @note The original clip identity is declared provenance; only exported RGB files
   * are rehashed here. No original clip, symlink target or output is ever modified.
   */
  class Reader {
    /**
     * @brief Validated metadata for one source sample; no RGB pixels are retained.
     */
    struct Entry {
      std::uint32_t id;  ///< Contiguous resampler sample identity, not a wire frame ID.
      std::uint64_t pts_us, sample_us;  ///< Actual source PTS and resampling-grid time.
      std::filesystem::path file;  ///< Canonical confined source path.
      std::string sha256;  ///< Expected exact RGB8 file digest.
    };

    std::vector<Entry> entries_;  ///< At most1800 bounded descriptors, without pixel buffers.
    body_case::Json source_;  ///< Original saved-clip provenance, not reverified clip bytes.
    std::string label_, manifest_hash_;  ///< Bounded human label and exact manifest digest.
    bool native_ = false;  ///< Native decode order has no fabricated sample-rate timeline.
    std::vector<std::uint64_t> read_times_, hash_times_;  ///< At most1800 measured source costs.

  public:
    /**
     * @brief Check complete metadata and path confinement before encoding any selected frame.
     * @param path Existing bounded manifest plus canonical descendant RGB8 files.
     */
    explicit Reader(const std::filesystem::path &path) {
      const auto raw = body_case::read_file(path, manifest_limit);
      const auto metadata = body_case::Json::parse(raw);
      body::require(metadata.at("schema") == schema, "sequence manifest schema");
      label_ = metadata.at("label").get<std::string>();
      body::require(!label_.empty() && label_.size() <= 1024, "sequence label bound");
      const auto &geometry = metadata.at("geometry");
      body::require(body_case::number(geometry.at("width"), 720) == 720 && body_case::number(geometry.at("height"), 480) == 480 && body_case::number(geometry.at("channels"), 3) == 3, "sequence RGB8 canvas");
      source_ = metadata.at("source");
      body::require(source_.at("kind") == "saved_clip" && source_.at("loop").is_boolean() && !source_.at("loop").get<bool>() && source_.at("repeated_source_timestamps").is_boolean() && !source_.at("repeated_source_timestamps").get<bool>(), "sequence saved finite source");
      const auto mode = source_.at("selection_mode").get<std::string>();
      body::require(mode == "resampled" || mode == "native-decoded", "sequence selection mode");
      native_ = mode == "native-decoded";
      body::require(source_.at("resampling_policy") == (native_ ? native_policy : resampling_policy) && source_.at("canvas_policy") == canvas_policy, "sequence source policy");
      const auto file_name = source_.at("file_name").get<std::string>();
      body::require(!file_name.empty() && file_name.size() <= 1024 && body_case::number(source_.at("bytes"), 1ULL << 50) > 0, "sequence clip provenance");
      check_hash(source_.at("sha256").get<std::string>());
      const auto offset = body_case::number(source_.at("requested_offset_us"), 86400000000ULL);
      std::uint64_t fps = 1, first = 0;
      if (native_) {
        body::require(source_.at("sample_fps").is_null() && source_.at("first_sample_index").is_null(), "sequence native has no sample grid");
        first = body_case::number(source_.at("first_decoded_id"), 0xfffffffeU);
        const auto &rate = source_.at("native_rate");
        body::require(body_case::number(rate.at("numerator"), 1000000) > 0 && body_case::number(rate.at("denominator"), 1000000) > 0, "sequence native nominal rate");
      } else {
        fps = body_case::number(source_.at("sample_fps"), 30);
        body::require(fps > 0 && source_.at("first_decoded_id").is_null() && source_.at("native_rate").is_null(), "sequence sample rate");
        first = body_case::number(source_.at("first_sample_index"), 0xfffffffeU);
        body::require(first == (offset * fps + 999999) / 1000000, "sequence sample offset");
      }
      const auto origin = body_case::number(source_.at("pts_origin_us"), std::numeric_limits<std::int64_t>::max());
      const auto &frames = metadata.at("frames");
      body::require(frames.is_array() && !frames.empty() && frames.size() <= 1800, "sequence frame count1..1800");
      entries_.reserve(frames.size());
      std::optional<std::uint64_t> previous;
      for (const auto &frame : frames) {
        const auto id = body_case::number(frame.at("id"), 0xfffffffeU);
        const auto pts = body_case::number(frame.at("pts_us"), std::numeric_limits<std::int64_t>::max());
        const auto sample = body_case::number(frame.at(native_ ? "relative_pts_us" : "sample_time_us"), std::numeric_limits<std::int64_t>::max());
        body::require(id == first + entries_.size() && (!previous || pts > *previous) && pts >= origin, "sequence ordered source identities");
        if (native_) {
          body::require(sample == pts - origin && sample >= offset && !frame.contains("sample_time_us"), "sequence native source timestamp");
        } else {
          body::require(sample == id * 1000000 / fps && pts <= origin + sample + 1, "sequence source sample timestamp");
        }
        const auto &descriptor = frame.at("rgb");
        body_case::shape(descriptor, "|u1", {480, 720, 3});
        body::require(body_case::number(descriptor.at("bytes"), frame_bytes) == frame_bytes, "sequence RGB8 byte count");
        const auto hash = descriptor.at("sha256").get<std::string>();
        check_hash(hash);
        const auto base = path.has_parent_path() ? path.parent_path() : std::filesystem::path(".");
        const auto file = body_case::relative_file(base, descriptor.at("path").get<std::string>());
        entries_.push_back({static_cast<std::uint32_t>(id), pts, sample, file, hash});
        previous = pts;
      }
      manifest_hash_ = body_case::digest(raw);
    }

    /**
     * @brief Return the finite count without reading or decoding frame pixels.
     * @return Number of validated metadata entries, at most1800.
     */
    std::size_t size() const {
      return entries_.size();
    }

    /**
     * @brief Load the next exact frame, charging file and hash work before encoding.
     * @param index Next sequential zero-based entry; retries/random access are not implicit.
     * @return One owned RGB8 canvas; the reader retains only bounded metadata/timings.
     */
    std::vector<std::uint8_t> load(unsigned index) {
      body::require(index < entries_.size() && index == read_times_.size(), "sequence ordered frame load");
      const auto &entry = entries_[index];
      const auto began = benchmark::Clock::now();
      auto raw = body_case::read_file(entry.file, frame_bytes);
      const auto read_ns = benchmark::elapsed(began);
      body::require(raw.size() == frame_bytes, "sequence exact RGB8 length");
      const auto hash_began = benchmark::Clock::now();
      body::require(body_case::digest(raw) == entry.sha256, "sequence RGB8 hash");
      const auto hash_ns = benchmark::elapsed(hash_began);
      read_times_.push_back(read_ns);
      hash_times_.push_back(hash_ns);
      return raw;
    }

    /**
     * @brief Bind measured rows to validated source identities and separately paid I/O costs.
     * @param result Completed finite benchmark report, with one row per successful load.
     */
    void describe(body_case::Json &result) const {
      body::require(result.at("frames").size() == read_times_.size(), "sequence complete source accounting");
      for (unsigned index = 0; index < read_times_.size(); ++index) {
        const auto &entry = entries_[index];
        auto &row = result["frames"][index];
        row["source_id"] = entry.id;
        row["source_pts_us"] = entry.pts_us;
        row[native_ ? "source_relative_pts_us" : "source_sample_time_us"] = entry.sample_us;
        row["source_rgb_sha256"] = entry.sha256;
        row["source_file_read_ns"] = read_times_[index];
        row["source_hash_ns"] = hash_times_[index];
      }
      result["schema"] = "gamebub-v20-encoder-sequence-benchmark-v1";
      result["scope"] = "offline_saved_frame_sequence_encode_and_software_decode";
      result["source_sequence_schema"] = schema;
      result["source_label"] = label_;
      result["source_manifest_sha256"] = manifest_hash_;
      result["source_provenance"] = source_;
      result["original_clip_reverified"] = false;
      result["clip_decode_scaling_measured"] = false;
      result["file_replay_not_live_capture"] = true;
      result["source_frames_available"] = entries_.size();
      result["source_frames_loaded"] = read_times_.size();
      result["source_load_allocation_bytes"] = frame_bytes;
      result["source_reader_retains_pixels"] = false;
      result["source_accounting"] = "file read and hash included in source_prepare; immutable snapshot/codec storage additional";
      result["timings_ns"]["source_file_read"] = benchmark::distribution(read_times_);
      result["timings_ns"]["source_hash"] = benchmark::distribution(hash_times_);
    }
  };

  /**
   * @brief Profile a finite saved-frame manifest without generated rotation or looping.
   * @param path Exact manifest; all descriptors are checked, only requested RGBs are loaded.
   * @param options Existing finite codec options; shift must be zero for saved frames.
   * @return Scoped report with separately charged validation, source I/O/hash and codec work.
   */
  inline body_case::Json run(const std::filesystem::path &path, const benchmark::Options &options) {
    benchmark::validate(options);
    body::require(options.shift_pixels == 0, "sequence does not generate motion");
    const auto began = benchmark::Clock::now();
    Reader reader(path);
    const auto metadata_ns = benchmark::elapsed(began);
    body::require(options.frames <= reader.size(), "sequence requested frame count exceeds source");
    auto measured_options = options;
    measured_options.record_output_hashes = true;
    auto result = benchmark::run_frames([&](unsigned index) {
      return reader.load(index);
    },
                                        measured_options);
    reader.describe(result);
    result["manifest_validation_ns"] = metadata_ns;
    result["sequence_total_wall_ns"] = benchmark::elapsed(began);
    return result;
  }
}  // namespace gamebub::v20::sequence
