/**
 * @file tests/unit/test_gamebub_v20_benchmark.cpp
 * @brief Finite offline profiling, deterministic motion and genuine reference evolution regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <filesystem>
#include <fstream>
#include <limits>
#include <vector>

// local includes
#include "tools/gamebub/native/encoder_benchmark.h"

namespace {
  namespace profile = gamebub::v20::benchmark;
  namespace fixture = gamebub::v20::body_case;

  /** @brief Create a small-edge, otherwise neutral original720x480 RGB8 source. */
  std::vector<std::uint8_t> seed() {
    std::vector<std::uint8_t> rgb(720 * 480 * 3, 128);
    rgb[0] = 255;
    rgb[719 * 3] = 0;
    return rgb;
  }

  /** @brief Own only the exact three temporary fixture files created by this regression. */
  struct SourceCase {
    std::filesystem::path root;  ///< Private existing test directory.
    profile::Json metadata;  ///< Source-only case declaration, not an original packet replay.

    /** @brief Write a hash-bound private RGB seed and source descriptor. */
    SourceCase() {
      root = std::filesystem::temp_directory_path() / ("gamebub-benchmark-" + std::to_string(profile::Clock::now().time_since_epoch().count()));
      std::filesystem::create_directory(root);
      const auto pixels = seed();
      std::ofstream source(root / "source.rgb", std::ios::binary);
      source.write(reinterpret_cast<const char *>(pixels.data()), pixels.size());
      metadata = {{"schema", "gamebub-v20-body-case-v1"}, {"label", "private-static-control"}, {"geometry", {{"width", 720}, {"height", 480}}}, {"source_rgb", {{"path", "source.rgb"}, {"bytes", pixels.size()}, {"sha256", fixture::digest(pixels)}, {"dtype", "|u1"}, {"shape", {480, 720, 3}}}}};
      save();
    }

    /** @brief Rewrite only the private JSON metadata when exercising malformed declarations. */
    void save() const {
      std::ofstream(root / "case.json") << metadata;
    }

    /** @brief Remove only known created files; never recursively erase a computed directory. */
    ~SourceCase() {
      std::filesystem::remove(root / "case.json");
      std::filesystem::remove(root / "source.rgb");
      std::filesystem::remove(root);
    }
  };
}  // namespace

TEST(GamebubV20Benchmark, RejectsUnboundedWorkBeforeInputOrEncoding) {
  profile::Options options;
  for (auto frames : {0U, 1801U}) {
    options.frames = frames;
    EXPECT_THROW(profile::run({}, options), std::invalid_argument);
    EXPECT_THROW(profile::run_case("nonexistent-case.json", options), std::invalid_argument);
  }
  options.frames = 1;
  options.shift_pixels = 720;
  EXPECT_THROW(profile::validate(options), std::invalid_argument);
  options.shift_pixels = 0;
  options.promote_every = 1801;
  EXPECT_THROW(profile::validate(options), std::invalid_argument);
  options.promote_every = 0;
  options.key_every = 1801;
  EXPECT_THROW(profile::validate(options), std::invalid_argument);
  options.key_every = 0;
  EXPECT_NO_THROW(profile::validate(options));
  EXPECT_THROW(profile::run({}, options), std::invalid_argument);
}

TEST(GamebubV20Benchmark, GeneratedMotionIsOwnedDeterministicAndKeepsRows) {
  const auto rgb = seed();
  const auto unchanged = profile::moving_rgb(rgb, 0, 1);
  EXPECT_EQ(unchanged, rgb);
  auto moved = profile::moving_rgb(rgb, 1, 1);
  EXPECT_EQ(moved[0], 0);
  EXPECT_EQ(moved[3], 255);
  EXPECT_EQ(moved[720 * 3], 128);
  EXPECT_EQ(profile::moving_rgb(rgb, 720, 1), rgb);
  EXPECT_EQ(profile::moving_rgb(rgb, 1799, 0), rgb);
  moved[0] = 44;
  EXPECT_EQ(rgb[0], 255);
  EXPECT_THROW(profile::moving_rgb({}, 0, 0), std::invalid_argument);
  EXPECT_THROW(profile::moving_rgb(rgb, 1800, 1), std::invalid_argument);
  EXPECT_THROW(profile::moving_rgb(rgb, 0, 720), std::invalid_argument);
}

TEST(GamebubV20Benchmark, TimingSummariesUseNearestRankAndRejectOverflow) {
  const auto empty = profile::distribution({});
  EXPECT_EQ(empty.at("count"), 0);
  EXPECT_EQ(empty.at("max"), 0);
  EXPECT_EQ(empty.at("p99"), 0);
  const auto values = profile::distribution({8, 1, 5, 2});
  EXPECT_EQ(values.at("total"), 16);
  EXPECT_EQ(values.at("p50"), 2);
  EXPECT_EQ(values.at("p95"), 8);
  EXPECT_EQ(values.at("p99"), 8);
  EXPECT_THROW(profile::distribution(std::vector<std::uint64_t>(1801)), std::invalid_argument);
  EXPECT_THROW(profile::distribution({std::numeric_limits<std::uint64_t>::max(), 1}), std::invalid_argument);
}

TEST(GamebubV20Benchmark, RealSequentialKeyPromotionAndRefreshPublishSoftwareAcks) {
  const auto rgb = seed();
  profile::Options options {3, 1, 1, 2};
  const auto report = profile::run(rgb, options);
  EXPECT_EQ(report.at("scope"), "offline_generated_motion_encode_and_software_decode");
  EXPECT_EQ(report.at("accepted_frames"), 3);
  EXPECT_EQ(report.at("rejected_frames"), 0);
  EXPECT_EQ(report.at("software_decoded_frames"), 3);
  EXPECT_EQ(report.at("key_frames"), 2);
  EXPECT_EQ(report.at("promoted_frames"), 1);
  EXPECT_EQ(report.at("ordinary_frames"), 0);
  EXPECT_EQ(report.at("final_confirmed_frame"), 2);
  EXPECT_FALSE(report.at("network_measured").get<bool>());
  EXPECT_FALSE(report.at("hardware_measured").get<bool>());
  EXPECT_EQ(report.at("timings_ns").at("admission").at("count"), 3);
  EXPECT_EQ(report.at("frames").at(1).at("frame_kind"), 2);
  EXPECT_EQ(fixture::digest(rgb), report.at("source_rgb_sha256").get<std::string>());
}

TEST(GamebubV20Benchmark, CaseSeedStartsFreshInsteadOfReplayingUnrelatedPreBanks) {
  SourceCase source;
  const auto report = profile::run_case(source.root / "case.json", {2, 0, 0, 0});
  EXPECT_EQ(report.at("source_case"), "private-static-control");
  EXPECT_EQ(report.at("key_frames"), 1);
  EXPECT_EQ(report.at("ordinary_frames"), 1);
  EXPECT_EQ(report.at("promoted_frames"), 0);
  EXPECT_EQ(report.at("final_confirmed_frame"), 1);
  EXPECT_EQ(report.at("accepted_frames"), 2);
  source.metadata["schema"] = "other";
  source.save();
  EXPECT_THROW(profile::run_case(source.root / "case.json", {1}), std::invalid_argument);
  source.metadata["schema"] = "gamebub-v20-body-case-v1";
  source.metadata["geometry"]["width"] = 719;
  source.save();
  EXPECT_THROW(profile::run_case(source.root / "case.json", {1}), std::invalid_argument);
  source.metadata["geometry"]["width"] = 720;
  source.metadata["geometry"]["height"] = 479;
  source.save();
  EXPECT_THROW(profile::run_case(source.root / "case.json", {1}), std::invalid_argument);
}

TEST(GamebubV20Benchmark, UnfitGeneratedFramesRemainRejectedWithoutPublishingReferences) {
  std::vector<std::uint8_t> pixels(720 * 480 * 3);
  std::uint32_t state = 1;
  for (auto &value : pixels) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    value = static_cast<std::uint8_t>(state);
  }
  const auto report = profile::run(pixels, {1, 0, 0, 0});
  EXPECT_EQ(report.at("accepted_frames"), 0);
  EXPECT_EQ(report.at("rejected_frames"), 1);
  EXPECT_EQ(report.at("final_confirmed_frame"), -1);
  EXPECT_EQ(report.at("software_decoded_frames"), 0);
  EXPECT_EQ(report.at("frames").at(0).at("reason"), "all_declared_maps_exceed_complete_cap");
  EXPECT_EQ(report.at("attempts"), 4);
  EXPECT_EQ(report.at("losing_attempts"), 4);
  EXPECT_EQ(report.at("complete_bytes"), 0);
  EXPECT_EQ(report.at("timings_ns").at("software_decode").at("count"), 0);
  const auto cached = profile::run(pixels, {1, 0, 0, 0, true});
  EXPECT_EQ(cached.at("accepted_frames"), 0);
  EXPECT_EQ(cached.at("rejected_frames"), 1);
  EXPECT_EQ(cached.at("attempts"), 4);
  EXPECT_EQ(cached.at("analysis_builds"), 1);
  EXPECT_EQ(cached.at("analysis_reuses"), 3);
  EXPECT_EQ(cached.at("final_confirmed_frame"), -1);
}

TEST(GamebubV20Benchmark, FrameLocalAnalysisPreservesSequentialOutputAndReportsPaidWork) {
  const auto rgb = seed();
  profile::Options options {3, 1, 1, 2};
  const auto baseline = profile::run(rgb, options);
  options.reuse_analysis = true;
  const auto cached = profile::run(rgb, options);
  EXPECT_FALSE(baseline.at("analysis_reuse").get<bool>());
  EXPECT_TRUE(cached.at("analysis_reuse").get<bool>());
  EXPECT_FALSE(baseline.at("analysis_paid_in_first_build").get<bool>());
  EXPECT_TRUE(cached.at("analysis_paid_in_first_build").get<bool>());
  EXPECT_EQ(cached.at("accepted_frames"), baseline.at("accepted_frames"));
  EXPECT_EQ(cached.at("complete_bytes"), baseline.at("complete_bytes"));
  EXPECT_EQ(cached.at("final_confirmed_frame"), baseline.at("final_confirmed_frame"));
  EXPECT_EQ(cached.at("analysis_builds"), 3);
  EXPECT_EQ(cached.at("analysis_reuses"), 0);
  EXPECT_EQ(cached.at("maximum_analysis_coefficient_bytes"), 2073600);
  EXPECT_EQ(baseline.at("maximum_analysis_coefficient_bytes"), 0);
  for (unsigned i = 0; i < options.frames; ++i) {
    EXPECT_EQ(cached.at("frames").at(i).at("packet_bytes"), baseline.at("frames").at(i).at("packet_bytes"));
    EXPECT_EQ(cached.at("frames").at(i).at("frame_kind"), baseline.at("frames").at(i).at("frame_kind"));
    EXPECT_EQ(cached.at("frames").at(i).at("analysis_builds"), 1);
  }
}
