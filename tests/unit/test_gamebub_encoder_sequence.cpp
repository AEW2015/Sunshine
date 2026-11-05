/**
 * @file tests/unit/test_gamebub_encoder_sequence.cpp
 * @brief Bounded saved-frame profiling, source identity and malformed manifest regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <filesystem>
#include <fstream>
#include <vector>

// local includes
#include "tools/gamebub/native/encoder_sequence.h"

namespace {
  namespace seq = gamebub::v20::sequence;
  namespace bench = gamebub::v20::benchmark;
  namespace body_case = gamebub::v20::body_case;

  /**
   * @brief Own only known temporary inputs; never recursively delete a computed directory.
   */
  struct SequenceCase {
    std::filesystem::path root;  ///< Unique temporary directory, not an external source tree.
    body_case::Json metadata;  ///< Editable source declarations for malformed-input checks.

    /**
     * @brief Create two exact test canvases and self-contained metadata without a video decoder.
     */
    SequenceCase() {
      root = std::filesystem::temp_directory_path() / ("gamebub-sequence-" + std::to_string(bench::Clock::now().time_since_epoch().count()));
      std::filesystem::create_directory(root);
      metadata = {{"schema", seq::schema}, {"label", "private-two-frame-input"}, {"geometry", {{"width", 720}, {"height", 480}, {"channels", 3}}}, {"source", {{"kind", "saved_clip"}, {"file_name", "synthetic-test-only.webm"}, {"bytes", 123}, {"sha256", std::string(64, 'a')}, {"requested_offset_us", 0}, {"selection_mode", "resampled"}, {"native_rate", nullptr}, {"first_decoded_id", nullptr}, {"sample_fps", 30}, {"first_sample_index", 0}, {"pts_origin_us", 0}, {"resampling_policy", seq::resampling_policy}, {"canvas_policy", seq::canvas_policy}, {"loop", false}, {"repeated_source_timestamps", false}}}, {"frames", body_case::Json::array()}};
      for (unsigned index = 0; index < 2; ++index) {
        std::vector<std::uint8_t> pixels(seq::frame_bytes, 128);
        pixels[index * 3] = 255;
        const auto name = "frame" + std::to_string(index) + ".rgb";
        std::ofstream stream(root / name, std::ios::binary);
        stream.write(reinterpret_cast<const char *>(pixels.data()), pixels.size());
        metadata["frames"].push_back({{"id", index}, {"pts_us", index * 33333}, {"sample_time_us", index * 1000000 / 30}, {"rgb", {{"path", name}, {"bytes", seq::frame_bytes}, {"sha256", body_case::digest(pixels)}, {"dtype", "|u1"}, {"shape", {480, 720, 3}}}}});
      }
      save();
    }

    /**
     * @brief Rewrite only the known manifest during malformed descriptor tests.
     */
    void save() const {
      std::ofstream(root / "manifest.json") << metadata;
    }

    /**
     * @brief Declare true native decode order without inventing a sampling-grid timeline.
     */
    void native_source() {
      auto &source = metadata["source"];
      source["selection_mode"] = "native-decoded";
      source["native_rate"] = {{"numerator", 30000}, {"denominator", 1001}};
      source["sample_fps"] = nullptr;
      source["first_sample_index"] = nullptr;
      source["first_decoded_id"] = 0;
      source["pts_origin_us"] = 7000;
      source["resampling_policy"] = seq::native_policy;
      for (auto &frame : metadata["frames"]) {
        const auto original = frame["pts_us"].get<std::uint64_t>();
        frame["pts_us"] = original + 7000;
        frame["relative_pts_us"] = original;
        frame.erase("sample_time_us");
      }
      save();
    }

    /**
     * @brief Remove only the three files this helper creates and its empty directory.
     */
    ~SequenceCase() {
      for (const auto *name : {"manifest.json", "frame0.rgb", "frame1.rgb"}) {
        std::filesystem::remove(root / name);
      }
      std::filesystem::remove(root);
    }
  };
}  // namespace

TEST(GamebubEncoderSequence, RealFiniteInputsKeepPerFrameHashesAndAllSourceCosts) {
  SequenceCase source;
  bench::Options options {2, 0, 0, 0};
  const auto report = seq::run(source.root / "manifest.json", options);
  EXPECT_EQ(report.at("schema"), "gamebub-v20-encoder-sequence-benchmark-v1");
  EXPECT_EQ(report.at("accepted_frames"), 2);
  EXPECT_EQ(report.at("software_decoded_frames"), 2);
  EXPECT_EQ(report.at("source_frames_loaded"), 2);
  EXPECT_EQ(report.at("source_frames_available"), 2);
  EXPECT_EQ(report.at("final_confirmed_frame"), 1);
  EXPECT_FALSE(report.at("capture_measured").get<bool>());
  EXPECT_FALSE(report.at("hardware_measured").get<bool>());
  EXPECT_FALSE(report.at("original_clip_reverified").get<bool>());
  EXPECT_FALSE(report.at("source_reader_retains_pixels").get<bool>());
  EXPECT_EQ(report.at("timings_ns").at("source_file_read").at("count"), 2);
  EXPECT_EQ(report.at("timings_ns").at("source_hash").at("count"), 2);
  for (unsigned index = 0; index < 2; ++index) {
    const auto &row = report.at("frames").at(index);
    EXPECT_EQ(row.at("source_id"), index);
    EXPECT_EQ(row.at("source_rgb_sha256"), source.metadata.at("frames").at(index).at("rgb").at("sha256"));
    EXPECT_EQ(row.at("packet_sha256").get<std::string>().size(), 64);
    EXPECT_GE(row.at("source_prepare_ns").get<std::uint64_t>(), row.at("source_file_read_ns").get<std::uint64_t>() + row.at("source_hash_ns").get<std::uint64_t>());
  }
  options.reuse_analysis = true;
  const auto cached = seq::run(source.root / "manifest.json", options);
  EXPECT_EQ(cached.at("complete_bytes"), report.at("complete_bytes"));
  EXPECT_EQ(cached.at("analysis_builds"), 2);
  EXPECT_EQ(cached.at("final_confirmed_frame"), 1);
  EXPECT_EQ(report.at("timings_ns").at("output_identity").at("count"), 2);
  for (unsigned index = 0; index < 2; ++index) {
    EXPECT_EQ(cached.at("frames").at(index).at("packet_sha256"), report.at("frames").at(index).at("packet_sha256"));
  }
}

TEST(GamebubEncoderSequence, RequestedSubsetLoadsNoUnselectedPixelsAndCannotLoop) {
  SequenceCase source;
  bench::Options options {1, 0, 0, 0};
  const auto report = seq::run(source.root / "manifest.json", options);
  EXPECT_EQ(report.at("source_frames_available"), 2);
  EXPECT_EQ(report.at("source_frames_loaded"), 1);
  options.frames = 3;
  EXPECT_THROW(seq::run(source.root / "manifest.json", options), std::invalid_argument);
  options.frames = 0;
  EXPECT_THROW(seq::run("nonexistent-sequence.json", options), std::invalid_argument);
  options.frames = 1;
  options.shift_pixels = 1;
  EXPECT_THROW(seq::run("nonexistent-sequence.json", options), std::invalid_argument);
}

TEST(GamebubEncoderSequence, NativeDecodeOrderKeepsOriginalPtsAndNominalRateWithoutSampleGrid) {
  SequenceCase source;
  source.native_source();
  const auto report = seq::run(source.root / "manifest.json", {2, 0, 0, 0});
  EXPECT_EQ(report.at("source_provenance").at("selection_mode"), "native-decoded");
  EXPECT_EQ(report.at("source_provenance").at("native_rate").at("numerator"), 30000);
  EXPECT_EQ(report.at("source_provenance").at("native_rate").at("denominator"), 1001);
  EXPECT_TRUE(report.at("source_provenance").at("sample_fps").is_null());
  EXPECT_EQ(report.at("frames").at(0).at("source_pts_us"), 7000);
  EXPECT_EQ(report.at("frames").at(1).at("source_relative_pts_us"), 33333);
  EXPECT_FALSE(report.at("frames").at(0).contains("source_sample_time_us"));
}

TEST(GamebubEncoderSequence, NativeModeRejectsFabricatedGridRateAndOriginalTimestampErrors) {
  SequenceCase source;
  source.native_source();
  const auto valid = source.metadata;
  for (unsigned scenario = 0; scenario < 8; ++scenario) {
    source.metadata = valid;
    switch (scenario) {
      case 0:
        source.metadata["source"]["sample_fps"] = 30;
        break;
      case 1:
        source.metadata["source"]["native_rate"]["numerator"] = 0;
        break;
      case 2:
        source.metadata["source"]["native_rate"]["denominator"] = 0;
        break;
      case 3:
        source.metadata["frames"][1]["pts_us"] = 7000;
        break;
      case 4:
        source.metadata["frames"][1]["relative_pts_us"] = 40000;
        break;
      case 5:
        source.metadata["frames"][0]["sample_time_us"] = 0;
        break;
      case 6:
        source.metadata["source"]["selection_mode"] = "unknown";
        break;
      case 7:
        source.metadata["source"]["requested_offset_us"] = 1;
        break;
    }
    source.save();
    EXPECT_THROW(seq::Reader(source.root / "manifest.json"), std::invalid_argument) << scenario;
  }
}

TEST(GamebubEncoderSequence, ReaderLoadsOneSequentialOwnedFrameAndRejectsMissingAccounting) {
  SequenceCase source;
  seq::Reader reader(source.root / "manifest.json");
  EXPECT_EQ(reader.size(), 2);
  EXPECT_THROW(reader.load(1), std::invalid_argument);
  auto first = reader.load(0);
  EXPECT_EQ(first.size(), seq::frame_bytes);
  first[0] = 17;
  EXPECT_THROW(reader.load(0), std::invalid_argument);
  EXPECT_EQ(reader.load(1).size(), seq::frame_bytes);
  EXPECT_THROW(reader.load(2), std::invalid_argument);
  body_case::Json wrong {{"frames", body_case::Json::array()}};
  EXPECT_THROW(reader.describe(wrong), std::invalid_argument);
}

TEST(GamebubEncoderSequence, SchemaGeometryCountAndProvenanceRejectBeforeEncoding) {
  SequenceCase source;
  const auto valid = source.metadata;
  for (unsigned scenario = 0; scenario < 15; ++scenario) {
    source.metadata = valid;
    switch (scenario) {
      case 0:
        source.metadata["schema"] = "other-v1";
        break;
      case 1:
        source.metadata["geometry"]["width"] = 719;
        break;
      case 2:
        source.metadata["geometry"]["height"] = 479;
        break;
      case 3:
        source.metadata["geometry"]["channels"] = 4;
        break;
      case 4:
        source.metadata["frames"] = body_case::Json::array();
        break;
      case 5:
        source.metadata["frames"] = std::vector<body_case::Json>(1801, valid.at("frames").at(0));
        break;
      case 6:
        source.metadata["source"]["loop"] = true;
        break;
      case 7:
        source.metadata["source"]["repeated_source_timestamps"] = true;
        break;
      case 8:
        source.metadata["source"]["sha256"] = std::string(64, 'A');
        break;
      case 9:
        source.metadata["source"]["bytes"] = 0;
        break;
      case 10:
        source.metadata["source"]["sample_fps"] = 0;
        break;
      case 11:
        source.metadata["source"]["canvas_policy"] = "stretch";
        break;
      case 12:
        source.metadata["source"]["first_sample_index"] = 1;
        break;
      case 13:
        source.metadata["label"] = "";
        break;
      case 14:
        source.metadata["source"]["file_name"] = "";
        break;
    }
    source.save();
    EXPECT_THROW(seq::Reader(source.root / "manifest.json"), std::invalid_argument) << scenario;
  }
}

TEST(GamebubEncoderSequence, DuplicateNonmonotonicAndFutureSampleIdentitiesReject) {
  SequenceCase source;
  const auto valid = source.metadata;
  for (unsigned scenario = 0; scenario < 7; ++scenario) {
    source.metadata = valid;
    auto &second = source.metadata["frames"][1];
    switch (scenario) {
      case 0:
        second["id"] = 0;
        break;
      case 1:
        second["pts_us"] = 0;
        break;
      case 2:
        second["pts_us"] = -1;
        break;
      case 3:
        second["sample_time_us"] = 33334;
        break;
      case 4:
        second["pts_us"] = 40000;
        break;
      case 5:
        second["id"] = 0xffffffffU;
        break;
      case 6:
        source.metadata["source"]["sample_fps"] = true;
        break;
    }
    source.save();
    EXPECT_THROW(seq::Reader(source.root / "manifest.json"), std::invalid_argument) << scenario;
  }
}

TEST(GamebubEncoderSequence, DescriptorBoundsDtypeHashesAndTraversalAreChecked) {
  SequenceCase source;
  const auto valid = source.metadata;
  for (unsigned scenario = 0; scenario < 8; ++scenario) {
    source.metadata = valid;
    auto &descriptor = source.metadata["frames"][0]["rgb"];
    switch (scenario) {
      case 0:
        descriptor["bytes"] = seq::frame_bytes + 1;
        break;
      case 1:
        descriptor["bytes"] = seq::frame_bytes - 1;
        break;
      case 2:
        descriptor["dtype"] = "<u2";
        break;
      case 3:
        descriptor["shape"] = {480, 719, 3};
        break;
      case 4:
        descriptor["sha256"] = "short";
        break;
      case 5:
        descriptor["path"] = "../escape.rgb";
        break;
      case 6:
        descriptor["path"] = source.root.generic_string() + "/frame0.rgb";
        break;
      case 7:
        descriptor["path"] = "frames\\frame0.rgb";
        break;
    }
    source.save();
    EXPECT_THROW(seq::Reader(source.root / "manifest.json"), std::invalid_argument) << scenario;
  }
}

TEST(GamebubEncoderSequence, ExactFrameLengthAndHashFailBeforeCandidatePreparation) {
  SequenceCase source;
  std::filesystem::resize_file(source.root / "frame0.rgb", seq::frame_bytes - 1);
  seq::Reader short_reader(source.root / "manifest.json");
  EXPECT_THROW(short_reader.load(0), std::invalid_argument);
  std::filesystem::resize_file(source.root / "frame0.rgb", seq::frame_bytes + 1);
  seq::Reader long_reader(source.root / "manifest.json");
  EXPECT_THROW(long_reader.load(0), std::invalid_argument);
  std::filesystem::resize_file(source.root / "frame0.rgb", seq::frame_bytes);
  seq::Reader wrong_hash_reader(source.root / "manifest.json");
  EXPECT_THROW(wrong_hash_reader.load(0), std::invalid_argument);
}

TEST(GamebubEncoderSequence, OversizedAndMalformedManifestCannotAllocateUnboundedInput) {
  SequenceCase source;
  std::ofstream(source.root / "manifest.json") << std::string(seq::manifest_limit + 1, ' ');
  EXPECT_THROW(seq::Reader(source.root / "manifest.json"), std::invalid_argument);
  std::ofstream(source.root / "manifest.json") << "{";
  EXPECT_THROW(seq::Reader(source.root / "manifest.json"), std::exception);
}

TEST(GamebubEncoderSequence, GenericFrameLoopRejectsEmptyProvidersAndWrongCanvases) {
  EXPECT_THROW(bench::run_frames({}, {1}), std::invalid_argument);
  unsigned calls = 0;
  EXPECT_THROW(bench::run_frames([&](unsigned) {
                 ++calls;
                 return std::vector<std::uint8_t> {};
               },
                                 {1}),
               std::invalid_argument);
  EXPECT_EQ(calls, 1);
}

TEST(GamebubEncoderSequence, RejectedAdmissionHasNoInventedPacketIdentity) {
  std::vector<std::uint8_t> pixels(seq::frame_bytes);
  std::uint32_t state = 1;
  for (auto &value : pixels) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    value = static_cast<std::uint8_t>(state);
  }
  bench::Options options {1, 0, 0, 0, false, true};
  const auto report = bench::run_frames([&](unsigned) {
    return pixels;
  },
                                        options);
  EXPECT_EQ(report.at("accepted_frames"), 0);
  EXPECT_EQ(report.at("losing_attempts"), 4);
  EXPECT_TRUE(report.at("frames").at(0).at("packet_sha256").is_null());
  EXPECT_EQ(report.at("frames").at(0).at("output_identity_ns"), 0);
  EXPECT_EQ(report.at("timings_ns").at("output_identity").at("total"), 0);
}
