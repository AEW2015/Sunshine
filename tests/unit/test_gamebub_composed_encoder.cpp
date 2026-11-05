/**
 * @file tests/unit/test_gamebub_composed_encoder.cpp
 * @brief Source-backed independent CP23 encoding, cap and identity regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <filesystem>
#include <fstream>
#include <span>
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
    ASSERT_EQ(result.accepted(), output.at("accepted").get<bool>());
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
