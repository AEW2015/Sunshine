/**
 * @file tests/unit/test_gamebub_composed_encoder.cpp
 * @brief Source-backed independent CP23 encoding, cap and identity regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <span>
#include <stdexcept>
#include <type_traits>
#include <vector>

// local includes
#include "tools/gamebub/native/body_case.h"
#include "tools/gamebub/native/composed_encoder.h"
#include "tools/gamebub/native/composed_encoder_case.h"
#include "tools/gamebub/native/transport_case.h"

namespace {
  namespace e = gamebub::v24::refresh_encoder;
  namespace c = gamebub::v24::composed;
  namespace b = gamebub::v20::body;
  namespace bc = gamebub::v20::body_case;
  namespace candidate = gamebub::v20::candidate;
  namespace inner = gamebub::v20::encoder;

  std::uint64_t fake_ticks {};  ///< Test-only deterministic clock state, never used by encoder defaults.

  /** @brief Advance one deterministic observation clock by ten nanoseconds. */
  std::uint64_t fake_clock() noexcept {
    return fake_ticks += 10;
  }

  /** @brief Inject one backwards clock interval without risking unsigned wrap. */
  std::uint64_t regressing_clock() noexcept {
    return fake_ticks++ ? 90 : 100;
  }

  /** @brief Locate exclusively checked-in independent source/model fixtures. */
  std::filesystem::path oracle_root() {
    return std::filesystem::path(__FILE__).parent_path().parent_path().parent_path() / "tools/gamebub/fixtures/composed-encoder-oracles";
  }

  /** @brief Create exact frozen RGB8 source; no RGB565 expansion is involved. */
  std::shared_ptr<const candidate::Source> uniform() {
    std::vector<std::uint8_t> rgb(720 * 480 * 3);
    for (std::size_t i = 0; i < rgb.size(); i += 3) {
      rgb[i] = 44;
      rgb[i + 1] = 96;
      rgb[i + 2] = 156;
    }
    return std::make_shared<const candidate::Source>(std::span<const std::uint8_t>(rgb));
  }

  /** @brief Generate deterministic asymmetric source with sharp and gradual changes. */
  std::shared_ptr<const candidate::Source> patterned() {
    std::vector<std::uint8_t> rgb(720 * 480 * 3);
    for (unsigned y = 0; y < 480; ++y) {
      for (unsigned x = 0; x < 720; ++x) {
        const auto offset = (y * 720 + x) * 3;
        rgb[offset] = (x / 9 + 3 * (y / 17)) % 256;
        rgb[offset + 1] = ((x / 23) * 31 + (y / 13) * 7) % 256;
        rgb[offset + 2] = (x + y / 3) % 256;
      }
    }
    return std::make_shared<const candidate::Source>(std::span<const std::uint8_t>(rgb));
  }

  /** @brief Create the asymmetric independent reference source without parsing native output. */
  std::shared_ptr<const candidate::Source> boxes() {
    const auto initial = uniform();
    std::vector<std::uint8_t> rgb(initial->rgb8().begin(), initial->rgb8().end());
    const auto fill = [&](unsigned x0, unsigned y0, unsigned x1, unsigned y1, std::array<std::uint8_t, 3> color) {
      for (unsigned y = y0; y < y1; ++y) {
        for (unsigned x = x0; x < x1; ++x) {
          std::copy(color.begin(), color.end(), rgb.begin() + (y * 720 + x) * 3);
        }
      }
    };
    fill(17, 40, 213, 133, {213, 72, 19});
    fill(151, 331, 579, 442, {29, 180, 70});
    fill(22, 82, 182, 96, {230, 210, 11});
    return std::make_shared<const candidate::Source>(std::span<const std::uint8_t>(rgb));
  }
}  // namespace

TEST(GamebubComposedEncoder, ReproducesAllTwelvePublishedStaticInstancesExactly) {
  const auto document = bc::Json::parse(bc::read_file(oracle_root() / "static.json", 256 * 1024));
  ASSERT_EQ(document.at("outputs").size(), 12);
  const auto source = uniform();
  for (const auto &output : document.at("outputs")) {
    const auto encoded = e::encode(source, output.at("epoch"), output.at("frame"));
    ASSERT_TRUE(encoded.accepted());
    const auto packet = gamebub::v20::transport_case::unhex(output.at("packet_hex"));
    EXPECT_EQ(encoded.packet, packet);
    EXPECT_EQ(encoded.packet.size(), 5166);
    const auto ack = gamebub::v20::transport_case::unhex(output.at("ack_hex"));
    EXPECT_EQ(std::vector(encoded.ack.begin(), encoded.ack.end()), ack);
    ASSERT_EQ(encoded.attempts.size(), 1);
    EXPECT_EQ(encoded.attempts[0].map, candidate::maps[0]);
    EXPECT_TRUE(encoded.attempts[0].accepted);
    EXPECT_EQ(encoded.attempts[0].complete_bytes, packet.size());
    EXPECT_GT(encoded.total_ns, 0);
    EXPECT_GT(encoded.hud_prepare_ns, 0);
    EXPECT_GT(encoded.validation_ns, 0);
    EXPECT_GT(encoded.cleanup_ns, 0);
    EXPECT_EQ(encoded.inner_profile, nullptr);
    const auto profiled = e::encode(source, output.at("epoch"), output.at("frame"), 49152, true);
    EXPECT_EQ(profiled.packet, encoded.packet);
    EXPECT_EQ(profiled.ack, encoded.ack);
    ASSERT_NE(profiled.inner_profile, nullptr);
    EXPECT_EQ(profiled.inner_profile->attempts, 1);
    for (const bool instrumented : {false, true}) {
      const auto budgeted = e::encode(source, output.at("epoch"), output.at("frame"), 49152, instrumented, true);
      EXPECT_TRUE(budgeted.budgeted_keys);
      EXPECT_EQ(budgeted.packet, encoded.packet);
      EXPECT_EQ(budgeted.ack, encoded.ack);
      ASSERT_EQ(budgeted.attempts.size(), 1);
      EXPECT_FALSE(budgeted.attempts[0].reconstruction_skipped);
      EXPECT_GT(budgeted.attempts[0].analysis_ns, 0);
    }
  }
}

TEST(GamebubComposedEncoder, WholePairCapBoundaryAndAllFourPaidRejections) {
  const auto source = uniform();
  const auto admitted = e::encode(source, 1, 0, 5166);
  ASSERT_TRUE(admitted.accepted());
  const auto rejected = e::encode(source, 1, 0, 256);
  EXPECT_FALSE(rejected.accepted());
  EXPECT_EQ(rejected.ack, (std::array<std::uint8_t, 134> {}));
  ASSERT_EQ(rejected.attempts.size(), 4);
  EXPECT_EQ(rejected.validation_ns, 0);
  for (unsigned i = 0; i < 4; ++i) {
    EXPECT_EQ(rejected.attempts[i].map, candidate::maps[i]);
    EXPECT_FALSE(rejected.attempts[i].accepted);
    EXPECT_GT(rejected.attempts[i].complete_bytes, 256);
    EXPECT_GT(rejected.attempts[i].build_ns, 0);
  }
  EXPECT_EQ(e::encode(source, 1, 0).packet, admitted.packet);
}

TEST(GamebubComposedEncoder, PatternedIndependentHudRetainsExactWordsAndCanonicalTag) {
  const auto source = patterned();
  const auto hud = e::hud(*source, 7, 19);
  const auto identity = c::hud_identity(hud);
  EXPECT_EQ(identity.generation, 1);
  EXPECT_EQ(identity.destination, 0);
  EXPECT_EQ(identity.reference, 255);
  EXPECT_EQ(identity.modes, (std::array<std::uint8_t, 4> {}));
  std::size_t cursor = 79;
  for (unsigned i = 0; i < 4; ++i) {
    const auto patch = b::decode_patch(std::span(hud).subspan(cursor, identity.sizes[i]), 720, 480);
    const auto rect = candidate::rectangles[i];
    for (unsigned row = 0; row < rect.height; ++row) {
      EXPECT_TRUE(std::equal(patch.words.begin() + row * rect.width, patch.words.begin() + (row + 1) * rect.width, source->words().begin() + (rect.y + row) * 720 + rect.x));
    }
    cursor += identity.sizes[i];
  }
  EXPECT_EQ(cursor + 4, hud.size());
}

TEST(GamebubComposedEncoder, InvalidIdentityCapAndMissingOriginalPixelsFailBeforeEncoding) {
  const auto source = uniform();
  EXPECT_THROW(e::encode(nullptr, 1, 0), std::invalid_argument);
  EXPECT_THROW(e::encode(source, 1, 0, 255), std::invalid_argument);
  EXPECT_THROW(e::encode(source, 1, 0, 49153), std::invalid_argument);
  EXPECT_THROW(e::encode(source, 0, 0), std::invalid_argument);
  EXPECT_THROW(e::encode(source, 0xffffffffU, 0), std::invalid_argument);
  EXPECT_THROW(e::encode(source, 1, 0xffffffffU), std::invalid_argument);
  const auto words = std::make_shared<const candidate::Source>(source->words());
  EXPECT_THROW(e::encode(words, 1, 0), std::invalid_argument);
}

TEST(GamebubComposedEncoder, IndependentNonuniformGoldensMatchBytesAckDisplayRetryAndRejection) {
  const auto document = bc::Json::parse(bc::read_file(oracle_root() / "nonuniform.json", 256 * 1024));
  ASSERT_EQ(document.at("outputs").size(), 4);
  for (const auto &output : document.at("outputs")) {
    const auto source = output.at("name") == "pattern" ? patterned() : boxes();
    EXPECT_EQ(bc::digest(source->rgb8()), output.at("source_rgb_sha256").get<std::string>());
    const auto result = e::encode(source, output.at("epoch"), output.at("frame"), output.at("cap"));
    const auto profiled = e::encode(source, output.at("epoch"), output.at("frame"), output.at("cap"), true);
    EXPECT_EQ(profiled.packet, result.packet);
    EXPECT_EQ(profiled.ack, result.ack);
    ASSERT_EQ(profiled.attempts.size(), result.attempts.size());
    for (std::size_t i = 0; i < result.attempts.size(); ++i) {
      EXPECT_EQ(profiled.attempts[i].map, result.attempts[i].map);
      EXPECT_EQ(profiled.attempts[i].complete_bytes, result.attempts[i].complete_bytes);
      EXPECT_EQ(profiled.attempts[i].accepted, result.attempts[i].accepted);
    }
    ASSERT_EQ(result.accepted(), output.at("accepted").get<bool>());
    for (const bool instrumented : {false, true}) {
      const auto budgeted = e::encode(source, output.at("epoch"), output.at("frame"), output.at("cap"), instrumented, true);
      EXPECT_EQ(budgeted.packet, result.packet);
      EXPECT_EQ(budgeted.ack, result.ack);
      ASSERT_EQ(budgeted.attempts.size(), result.attempts.size());
      for (std::size_t i = 0; i < result.attempts.size(); ++i) {
        EXPECT_EQ(budgeted.attempts[i].map, result.attempts[i].map);
        EXPECT_EQ(budgeted.attempts[i].complete_bytes, result.attempts[i].complete_bytes);
        EXPECT_EQ(budgeted.attempts[i].accepted, result.attempts[i].accepted);
        EXPECT_EQ(budgeted.attempts[i].reconstruction_skipped, !result.attempts[i].accepted);
        EXPECT_EQ(budgeted.attempts[i].analysis_ns > 0, i == 0);
      }
      if (instrumented) {
        ASSERT_NE(budgeted.inner_profile, nullptr);
        EXPECT_EQ(budgeted.inner_profile->bucket(inner::Stage::quantization).calls, 8100 * result.attempts.size());
        EXPECT_EQ(budgeted.inner_profile->bucket(inner::Stage::entropy).calls, 3 * result.attempts.size());
        EXPECT_EQ(budgeted.inner_profile->bucket(inner::Stage::reconstruction).calls, result.accepted() ? 8100 : 0);
        EXPECT_EQ(budgeted.inner_profile->bucket(inner::Stage::tag).calls, result.accepted() ? 1 : 0);
        EXPECT_EQ(budgeted.inner_profile->bucket(inner::Stage::forward).calls, 0);
      }
    }
    const auto &attempts = output.at("attempts");
    ASSERT_EQ(result.attempts.size(), attempts.size());
    for (std::size_t i = 0; i < attempts.size(); ++i) {
      EXPECT_EQ(result.attempts[i].map.roi, attempts[i].at("roi_scale"));
      EXPECT_EQ(result.attempts[i].map.background, attempts[i].at("background_scale"));
      EXPECT_EQ(result.attempts[i].complete_bytes, attempts[i].at("complete_bytes"));
      EXPECT_EQ(result.attempts[i].accepted, attempts[i].at("accepted").get<bool>());
    }
    if (result.accepted()) {
      EXPECT_EQ(result.packet, gamebub::v20::transport_case::unhex(output.at("packet_hex")));
      EXPECT_EQ(std::vector(result.ack.begin(), result.ack.end()), gamebub::v20::transport_case::unhex(output.at("ack_hex")));
      EXPECT_EQ(bc::digest(gamebub::v24::refresh::display_le(gamebub::v24::refresh::decode_legacy_refresh(result.packet))), output.at("display_rgb565_sha256").get<std::string>());
    }
  }
}

TEST(GamebubComposedEncoder, HashBoundCaseReportsAcceptedAndRejectedOfflineWork) {
  const auto directory = std::filesystem::temp_directory_path() / ("gamebub-composed-case-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  std::filesystem::create_directory(directory);
  const auto source = uniform();
  {
    std::ofstream pixels(directory / "source.rgb", std::ios::binary);
    pixels.write(reinterpret_cast<const char *>(source->rgb8().data()), source->rgb8().size());
  }
  bc::Json document {{"schema", "gamebub-cp23-independent-encoder-case-v1"}, {"epoch", 1}, {"frame", 0}, {"cap", 49152}, {"source_rgb", {{"path", "source.rgb"}, {"bytes", 720 * 480 * 3}, {"sha256", bc::digest(source->rgb8())}, {"dtype", "|u1"}, {"shape", {480, 720, 3}}}}};
  const auto run = [&]() {
    std::ofstream(directory / "case.json") << document;
    return gamebub::v24::refresh_encoder_case::run(directory / "case.json");
  };
  const auto accepted = run();
  EXPECT_EQ(accepted.at("packet_bytes"), 5166);
  EXPECT_EQ(accepted.at("packet_sha256"), "a44fcd4a62027dc9c609c4b64a68145ee9f915880a7ec312ade811525eceb24b");
  EXPECT_EQ(accepted.at("ack_sha256"), "d9372f51eb797f5c369d359ca700c6ae36c6a7a499bf600ef78018696f5fa530");
  EXPECT_FALSE(accepted.at("hardware_playback").get<bool>());
  EXPECT_FALSE(accepted.at("inner_profile_enabled").get<bool>());
  EXPECT_TRUE(accepted.at("inner_profile").is_null());
  EXPECT_EQ(accepted.at("inner_strategy"), "legacy_frame_builder");
  document["profile_substages"] = true;
  const auto instrumented = run();
  EXPECT_EQ(instrumented.at("packet_sha256"), accepted.at("packet_sha256"));
  EXPECT_EQ(instrumented.at("ack_sha256"), accepted.at("ack_sha256"));
  EXPECT_TRUE(instrumented.at("inner_profile_enabled").get<bool>());
  EXPECT_EQ(instrumented.at("inner_profile").at("attempts"), 1);
  document["budgeted_keys"] = true;
  const auto budgeted = run();
  EXPECT_TRUE(budgeted.at("budgeted_keys_enabled").get<bool>());
  EXPECT_EQ(budgeted.at("inner_strategy"), "budgeted_keys_prepare_admit_finalize");
  EXPECT_NE(budgeted.at("inner_stage_boundaries").get<std::string>().find("excludes dequantization"), std::string::npos);
  EXPECT_EQ(budgeted.at("packet_sha256"), accepted.at("packet_sha256"));
  EXPECT_EQ(budgeted.at("ack_sha256"), accepted.at("ack_sha256"));
  document["budgeted_keys"] = 1;
  EXPECT_THROW(run(), bc::Json::type_error);
  document["budgeted_keys"] = true;
  document["cap"] = 256;
  const auto rejected = run();
  EXPECT_FALSE(rejected.at("accepted").get<bool>());
  EXPECT_TRUE(rejected.at("packet_sha256").is_null());
  EXPECT_TRUE(rejected.at("ack_sha256").is_null());
  EXPECT_EQ(rejected.at("attempts").size(), 4);
  document["schema"] = "other";
  EXPECT_THROW(run(), std::invalid_argument);
  document["schema"] = "gamebub-cp23-independent-encoder-case-v1";
  document["source_rgb"]["shape"] = {720, 480, 3};
  EXPECT_THROW(run(), std::invalid_argument);
  document["source_rgb"]["shape"] = {480, 720, 3};
  document["source_rgb"]["dtype"] = "<u2";
  EXPECT_THROW(run(), std::invalid_argument);
  std::filesystem::remove(directory / "case.json");
  std::filesystem::remove(directory / "source.rgb");
  std::filesystem::remove(directory);
}

TEST(GamebubEncoderProfile, ScopesCountCompletedAbortedDisabledAndRegressingClocks) {
  static_assert(!std::is_copy_constructible_v<inner::StageScope>);
  static_assert(!std::is_move_constructible_v<inner::StageScope>);
  fake_ticks = 0;
  inner::Profile profile(fake_clock);
  EXPECT_EQ(profile.clock_reads, 0);
  {
    inner::StageScope disabled(nullptr, inner::Stage::count);
    disabled.finish();
  }
  EXPECT_EQ(fake_ticks, 0);
  {
    inner::StageScope completed(&profile, inner::Stage::quantization);
    completed.finish();
    completed.finish();
  }
  EXPECT_EQ(profile.bucket(inner::Stage::quantization).calls, 1);
  EXPECT_EQ(profile.bucket(inner::Stage::quantization).aborted, 0);
  EXPECT_EQ(profile.bucket(inner::Stage::quantization).nanoseconds, 10);
  EXPECT_THROW(([&]() {
                 inner::StageScope aborted(&profile, inner::Stage::entropy);
                 throw std::runtime_error("test operation failed");
               }()),
               std::runtime_error);
  EXPECT_EQ(profile.bucket(inner::Stage::entropy).calls, 1);
  EXPECT_EQ(profile.bucket(inner::Stage::entropy).aborted, 1);
  EXPECT_EQ(profile.clock_reads, 4);
  EXPECT_THROW(profile.bucket(inner::Stage::count), std::invalid_argument);
  EXPECT_THROW((inner::StageScope(&profile, inner::Stage::count)), std::invalid_argument);
  EXPECT_EQ(profile.clock_reads, 4);
  EXPECT_THROW(inner::Profile(nullptr), std::invalid_argument);
  fake_ticks = 0;
  inner::Profile regressing(regressing_clock);
  {
    inner::StageScope scope(&regressing, inner::Stage::tag);
    scope.finish();
  }
  EXPECT_EQ(regressing.clock_regressions, 1);
  EXPECT_EQ(regressing.bucket(inner::Stage::tag).nanoseconds, 0);
}

TEST(GamebubEncoderProfile, KeyOrdinaryAndPromotionRemainByteExactWithBoundedObservations) {
  const auto source = uniform();
  const candidate::BuildRequest key {source, nullptr, 1, 0, 255, 0, true, false, candidate::maps[0]};
  const auto built = inner::encode_inner(key);
  b::State state;
  b::Frame frame;
  std::string error;
  ASSERT_TRUE(b::decode(e::base(key, built), state, frame, error)) << error;
  const auto reference = std::make_shared<const b::Bank>(*state.banks[0]);
  for (unsigned mode = 0; mode < 3; ++mode) {
    const bool is_key = mode == 0, promoted = mode == 2;
    const unsigned destination = is_key ? 0 : promoted ? 1 :
                                                         255;
    const candidate::BuildRequest request {source, is_key ? nullptr : reference, 1, mode + 1, is_key ? 255U : 0U, destination, is_key, promoted, candidate::maps[0]};
    inner::Profile profile;
    const auto plain = inner::encode_inner(request);
    const auto observed = inner::encode_inner_profiled(request, profile);
    EXPECT_EQ(plain.inner, observed.inner);
    EXPECT_EQ(plain.stored_tag, observed.stored_tag);
    EXPECT_EQ(profile.attempts, 1);
    EXPECT_EQ(profile.bucket(inner::Stage::source).calls, 1);
    EXPECT_EQ(profile.bucket(inner::Stage::forward).calls, 8100);
    EXPECT_EQ(profile.bucket(inner::Stage::quantization).calls, 8100);
    EXPECT_EQ(profile.bucket(inner::Stage::reconstruction).calls, is_key || promoted ? 8100 : 0);
    EXPECT_EQ(profile.bucket(inner::Stage::entropy).calls, 3);
    EXPECT_EQ(profile.bucket(inner::Stage::tag).calls, is_key || promoted ? 1 : 0);
    std::uint64_t calls = 0;
    for (unsigned i = 0; i < inner::stage_names.size(); ++i) {
      const auto &bucket = profile.bucket(static_cast<inner::Stage>(i));
      calls += bucket.calls;
      EXPECT_EQ(bucket.aborted, 0);
    }
    EXPECT_EQ(profile.clock_reads, calls * 2);
  }
  inner::Profile failed;
  auto invalid = key;
  invalid.source.reset();
  EXPECT_THROW(inner::encode_inner_profiled(invalid, failed), std::invalid_argument);
  EXPECT_EQ(failed.attempts, 1);
  EXPECT_EQ(failed.bucket(inner::Stage::validation).aborted, 1);
  EXPECT_EQ(failed.bucket(inner::Stage::source).calls, 0);
}

TEST(GamebubCanonicalTag, FrozenLittleEndianWordOrderAndBoundaryGeometriesRemainExact) {
  const b::Planes small {{{0, 1, 127, 255}, {64}, {192}}};
  // Independent hashlib oracle for literal bytes 02000200000001007f00ff004000c000.
  EXPECT_EQ(b::canonical_tag(small, 2, 2), bc::tag("cfbe63a1e59c6b305ce9eadec241ef35"));

  struct Oracle {
    unsigned width, height;  ///< Valid minimum, maximum area and individual dimension bounds.
    const char *tag;  ///< Independent Python struct.pack('<HH') + signed16-LE sample SHA16.
  };

  const std::array<Oracle, 4> oracles {{{2, 2, "02f1811ed32fa28c1f3189a449bb2e1a"}, {720, 480, "f12a31b3d840768688191ef42078a4b3"}, {2048, 168, "d8bbdca2a4000e83d48860dc6cd35492"}, {168, 2048, "ada0de21decddfe3e884ec24a3849ced"}}};
  for (const auto oracle : oracles) {
    b::Planes planes;
    for (unsigned p = 0; p < planes.size(); ++p) {
      planes[p].resize(oracle.width * oracle.height / (p ? 4 : 1));
      for (std::size_t i = 0; i < planes[p].size(); ++i) {
        planes[p][i] = (i * 17 + p * 73) % 256;
      }
    }
    const auto before = planes;
    EXPECT_EQ(b::canonical_tag(planes, oracle.width, oracle.height), bc::tag(oracle.tag));
    EXPECT_EQ(planes, before);
  }
}

TEST(GamebubCanonicalTag, ShapeDomainAndFailureOrderRemainStrictWithoutMutatingInputs) {
  const b::Planes valid {{{0, 1, 127, 255}, {64}, {192}}};
  const auto rejection = [](const b::Planes &planes, unsigned width = 2, unsigned height = 2) {
    const auto before = planes;
    try {
      b::canonical_tag(planes, width, height);
      ADD_FAILURE() << "invalid canonical tag input accepted";
      return std::string {};
    } catch (const std::invalid_argument &error) {
      EXPECT_EQ(planes, before);
      return std::string(error.what());
    }
  };
  for (const auto shape : std::array<std::array<unsigned, 2>, 4> {{{0, 2}, {3, 2}, {2048, 2048}, {2050, 2}}}) {
    EXPECT_EQ(rejection(valid, shape[0], shape[1]), "geometry domain");
  }
  for (unsigned p = 0; p < 3; ++p) {
    auto short_plane = valid;
    short_plane[p].pop_back();
    EXPECT_EQ(rejection(short_plane), "bank plane length");
    auto long_plane = valid;
    long_plane[p].push_back(0);
    EXPECT_EQ(rejection(long_plane), "bank plane length");
    for (const auto invalid : {-1, 256}) {
      auto bad_sample = valid;
      bad_sample[p].back() = invalid;
      EXPECT_EQ(rejection(bad_sample), "bank sample domain");
    }
  }
  auto earlier_sample = valid;
  earlier_sample[0][0] = -1;
  earlier_sample[1].clear();
  EXPECT_EQ(rejection(earlier_sample), "bank sample domain");
  earlier_sample = valid;
  earlier_sample[1][0] = 256;
  earlier_sample[2].clear();
  EXPECT_EQ(rejection(earlier_sample), "bank sample domain");
}

TEST(GamebubKeyBudget, ExactAndOneLessBudgetsReturnOnlyFullyFinalizedKeys) {
  const auto source = uniform();
  const candidate::BuildRequest request {source, nullptr, 1, 0, 255, 0, true, false, candidate::maps[0]};
  const auto expected = inner::encode_inner(request);
  for (const auto budget : {std::size_t(0), expected.inner.size() - 1, expected.inner.size()}) {
    inner::Profile profile;
    inner::KeyBudgetBuilder builder(&profile);
    const auto result = builder.attempt(request, budget);
    EXPECT_EQ(result.inner_bytes, expected.inner.size());
    EXPECT_EQ(result.encoded.has_value(), budget == expected.inner.size());
    EXPECT_EQ(result.reconstruction_skipped, !result.encoded.has_value());
    EXPECT_EQ(builder.attempts(), 1);
    EXPECT_EQ(builder.analysis_builds(), 1);
    EXPECT_GT(result.analysis_ns, 0);
    EXPECT_EQ(profile.bucket(inner::Stage::tag).calls, result.encoded ? 1 : 0);
    EXPECT_EQ(profile.bucket(inner::Stage::reconstruction).calls, result.encoded ? 8100 : 0);
    if (result.encoded) {
      EXPECT_EQ(result.encoded->inner, expected.inner);
      EXPECT_EQ(result.encoded->stored_tag, expected.stored_tag);
      EXPECT_TRUE(builder.retired());
      EXPECT_EQ(builder.coefficient_bytes(), 0);
    } else {
      EXPECT_FALSE(builder.retired());
      EXPECT_GT(builder.coefficient_bytes(), 0);
      builder.retire();
      builder.retire();
      EXPECT_EQ(builder.coefficient_bytes(), 0);
    }
    EXPECT_FALSE(builder.failed());
    EXPECT_THROW(builder.attempt(request, budget), std::invalid_argument);
    EXPECT_TRUE(builder.failed());
    EXPECT_EQ(builder.coefficient_bytes(), 0);
    if (result.encoded) {
      EXPECT_EQ(result.encoded->inner, expected.inner);
      EXPECT_EQ(result.encoded->stored_tag, expected.stored_tag);
    }
  }
}

TEST(GamebubKeyBudget, ZeroBudgetPaysFourOrderedActualSizesAndRetiresBoundSource) {
  auto source = uniform();
  candidate::BuildRequest request {source, nullptr, 1, 0, 255, 0, true, false, candidate::maps[0]};
  const auto count_before = source.use_count();
  inner::KeyBudgetBuilder builder;
  for (unsigned i = 0; i < candidate::maps.size(); ++i) {
    request.map = candidate::maps[i];
    const auto expected = inner::encode_inner(request);
    const auto result = builder.attempt(request, 0);
    EXPECT_EQ(result.inner_bytes, expected.inner.size());
    EXPECT_FALSE(result.encoded.has_value());
    EXPECT_TRUE(result.reconstruction_skipped);
    EXPECT_EQ(result.analysis_ns > 0, i == 0);
    EXPECT_EQ(builder.attempts(), i + 1);
    EXPECT_EQ(source.use_count(), i == 3 ? count_before : count_before + 1);
  }
  EXPECT_TRUE(builder.retired());
  EXPECT_FALSE(builder.failed());
  EXPECT_EQ(builder.analysis_builds(), 1);
  EXPECT_EQ(builder.coefficient_bytes(), 0);
  std::weak_ptr<const candidate::Source> weak;
  {
    auto owned = uniform();
    weak = owned;
    candidate::BuildRequest private_request {owned, nullptr, 2, 0, 255, 0, true, false, candidate::maps[0]};
    inner::KeyBudgetBuilder retained;
    retained.attempt(private_request, 0);
    private_request.source.reset();
    owned.reset();
    EXPECT_FALSE(weak.expired());
  }
  EXPECT_TRUE(weak.expired());
}

TEST(GamebubKeyBudget, RejectsPredictivePromotedReferencedAndMisorderedRequestsBeforeAnalysis) {
  const auto source = uniform();
  const candidate::BuildRequest key {source, nullptr, 1, 0, 255, 0, true, false, candidate::maps[0]};
  for (unsigned invalid = 0; invalid < 7; ++invalid) {
    auto request = key;
    if (invalid == 0) {
      request.key = false;
    }
    if (invalid == 1) {
      request.promoted = true;
    }
    if (invalid == 2) {
      request.reference = std::make_shared<const b::Bank>();
    }
    if (invalid == 3) {
      request.reference_slot = 0;
    }
    if (invalid == 4) {
      request.destination_slot = 1;
    }
    if (invalid == 5) {
      request.map = candidate::maps[1];
    }
    if (invalid == 6) {
      request.source = std::make_shared<const candidate::Source>(source->words());
    }
    inner::KeyBudgetBuilder builder;
    EXPECT_THROW(builder.attempt(request, 49152), std::invalid_argument);
    EXPECT_TRUE(builder.failed());
    EXPECT_TRUE(builder.retired());
    EXPECT_EQ(builder.analysis_builds(), 0);
    EXPECT_EQ(builder.attempts(), 0);
    EXPECT_EQ(builder.coefficient_bytes(), 0);
  }
}

TEST(GamebubKeyBudget, CacheIdentityFailureReleasesOnlyItsPrivateFrame) {
  const auto source = uniform();
  const candidate::BuildRequest key {source, nullptr, 1, 0, 255, 0, true, false, candidate::maps[0]};
  for (unsigned changed = 0; changed < 3; ++changed) {
    inner::KeyBudgetBuilder builder;
    const auto count_before = source.use_count();
    builder.attempt(key, 0);
    EXPECT_GT(builder.coefficient_bytes(), 0);
    auto next = key;
    next.map = candidate::maps[1];
    if (changed == 0) {
      next.source = uniform();
    }
    if (changed == 1) {
      next.frame_id = 1;
    }
    if (changed == 2) {
      next.epoch = 2;
    }
    EXPECT_THROW(builder.attempt(next, 49152), std::invalid_argument);
    EXPECT_TRUE(builder.failed());
    EXPECT_TRUE(builder.retired());
    EXPECT_EQ(builder.coefficient_bytes(), 0);
    EXPECT_EQ(builder.attempts(), 1);
    EXPECT_EQ(builder.analysis_builds(), 1);
    EXPECT_EQ(source.use_count(), count_before + (changed == 0 ? 0 : 1));
  }
}
