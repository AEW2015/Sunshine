/**
 * @file tests/unit/test_gamebub_v20_encoder.cpp
 * @brief Native original-RGB GM01 arithmetic, entropy and reference regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <memory>
#include <vector>

// local includes
#include "tools/gamebub/native/inner_encoder.h"

namespace {
  namespace e = gamebub::v20::encoder;
  namespace c = gamebub::v20::candidate;
  namespace b = gamebub::v20::body;
  using gamebub::v20::block_t;

  /** @brief Construct a valid owned RGB8 key request with neutral source samples. */
  c::BuildRequest key_request() {
    std::vector<std::uint8_t> rgb(c::width * c::height * 3, 128);
    return {std::make_shared<const c::Source>(std::span<const std::uint8_t>(rgb)), nullptr, 1, 7, 255, 0, true, false, c::maps[0]};
  }

  /** @brief Hash complete native packet bytes against the independently frozen Python oracle. */
  std::string packet_hash(std::span<const std::uint8_t> packet) {
    std::array<unsigned char, SHA256_DIGEST_LENGTH> digest;
    SHA256(packet.data(), packet.size(), digest.data());
    constexpr std::string_view hex = "0123456789abcdef";
    std::string result;
    for (auto byte : digest) {
      result.push_back(hex[byte >> 4]);
      result.push_back(hex[byte & 15]);
    }
    return result;
  }

  /** @brief Wrap real GM01 bytes in an independently constructed patch-free AR03 envelope. */
  std::vector<std::uint8_t> envelope(const c::BuildRequest &request, const c::BuildResult &encoded) {
    std::vector<std::uint8_t> out {'A', 'R', '0', '3', 3, std::uint8_t(request.key ? 1 : request.promoted ? 2 :
                                                                                                            0)};
    e::append32(out, request.epoch);
    e::append32(out, request.frame_id);
    out.push_back(request.reference_slot);
    out.push_back(request.destination_slot);
    e::append32(out, request.key ? UINT32_MAX : request.reference->id);
    b::Tag reference_tag {};
    if (request.reference) {
      reference_tag = request.reference->tag;
    }
    out.insert(out.end(), reference_tag.begin(), reference_tag.end());
    out.insert(out.end(), encoded.stored_tag.begin(), encoded.stored_tag.end());
    e::append32(out, encoded.inner.size());
    out.push_back(0);
    e::append32(out, 0);
    out.insert(out.end(), encoded.inner.begin(), encoded.inner.end());
    e::seal(out);
    return out;
  }
}  // namespace

TEST(GamebubV20Encoder, ColorConversionUsesClippedIntegerPixelsBeforeChromaBoxAverage) {
  const std::array<std::uint8_t, 12> rgb {255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255};
  const auto planes = e::rgb_to_planes(rgb, 2, 2);
  EXPECT_EQ(planes[0], (std::vector<std::int16_t> {77, 149, 29, 255}));
  EXPECT_EQ(planes[1], (std::vector<std::int16_t> {128}));
  EXPECT_EQ(planes[2], (std::vector<std::int16_t> {128}));
  EXPECT_THROW(e::rgb_to_planes(std::span(rgb).first(11), 2, 2), std::invalid_argument);
  const std::array<std::uint8_t, 18> odd_geometry {};
  EXPECT_THROW(e::rgb_to_planes(odd_geometry, 3, 2), std::invalid_argument);
}

TEST(GamebubV20Encoder, ForwardSeparatesBothQ14RoundingPassesAndRejectsInvalidResiduals) {
  block_t input {};
  EXPECT_EQ(e::forward(input), input);
  input.fill(-128);
  const auto negative = e::forward(input);
  EXPECT_EQ(negative[0], -1024);
  EXPECT_TRUE(std::all_of(negative.begin() + 1, negative.end(), [](auto value) {
    return value == 0;
  }));
  input.fill(255);
  const auto positive = e::forward(input);
  EXPECT_EQ(positive[0], 2039);
  EXPECT_TRUE(std::all_of(positive.begin() + 1, positive.end(), [](auto value) {
    return value == 0;
  }));
  // Frozen MoonBub27a4dde Python forward oracle; the asymmetric input detects transposition.
  for (unsigned i = 0; i < input.size(); ++i) {
    input[i] = int((i * 37) % 511) - 255;
  }
  const block_t asymmetric {-126, -115, 0, -37, 0, -44, 0, -116, -133, 128, -231, 1, 0, -1, 96, -25, -195, -302, -128, 106, 0, -71, 53, 60, 11, -1, 196, 128, 0, -85, -81, 0, -256, -96, 0, -197, 0, 131, 0, 19, 36, 0, 131, -192, 0, 128, -54, 0, -472, -126, 308, 44, 0, -29, -128, 25, 114, -642, -46, 0, 0, 0, 19, 128};
  EXPECT_EQ(e::forward(input), asymmetric);
  input[13] = 256;
  EXPECT_THROW(e::forward(input), std::invalid_argument);
  input[13] = -256;
  EXPECT_THROW(e::forward(input), std::invalid_argument);
}

TEST(GamebubV20Encoder, RiceParametersHaveFirstMinimumTiesAndCanonicalEscapePadding) {
  EXPECT_EQ(e::best_k({}, 13, 14), 0);
  const std::array<unsigned, 1> zero {0};
  EXPECT_EQ(e::best_k(zero, 13, 14), 0);
  e::Bits bits;
  bits.rice(0, 0, 12);
  bits.rice(14, 0, 12);
  bits.rice(15, 0, 12);
  bits.rice(4095, 11, 12);
  b::Bits reader(bits.bytes());
  EXPECT_EQ(reader.rice(0, 12), 0);
  EXPECT_EQ(reader.rice(0, 12), 14);
  EXPECT_EQ(reader.rice(0, 12), 15);
  EXPECT_EQ(reader.rice(11, 12), 4095);
  EXPECT_NO_THROW(reader.finish());
  EXPECT_THROW(bits.put(0, 33), std::invalid_argument);
  EXPECT_THROW(bits.rice(4096, 0, 12), std::invalid_argument);
  EXPECT_THROW(bits.rice(0, 14, 12), std::invalid_argument);
  EXPECT_THROW(bits.rice(0, 0, 15), std::invalid_argument);
}

TEST(GamebubV20Encoder, CoefficientEntropyPreservesRowsBandsRunsEscapesAndRawFallback) {
  const auto order = b::zigzag();
  std::vector<block_t> blocks(4);
  blocks[0][0] = -2048;
  blocks[1][0] = 2048;
  blocks[2][0] = -2048;
  blocks[3][0] = -2048;
  blocks[0][order[5]] = 1;
  blocks[0][order[6]] = -1;
  blocks[0][order[20]] = 2048;
  blocks[0][order[21]] = -2048;
  blocks[0][order[63]] = 1;
  blocks[2][order[50]] = -1;
  auto encoded = e::encode_coefficients(blocks, 2);
  EXPECT_EQ(encoded[5], 1);
  EXPECT_EQ(packet_hash(encoded), "eb354d4ec2a7e46a5d79bfea5d155c118c790a0b0e20075233837b8cfac8459c");
  EXPECT_EQ(b::cp02(encoded, 4, 2), blocks);
  std::vector<block_t> dense(4);
  for (unsigned i = 0; i < 4; ++i) {
    for (unsigned j = 0; j < 64; ++j) {
      dense[i][j] = int(((i * 64 + j) * 977 + 19) % 4097) - 2048;
    }
  }
  encoded = e::encode_coefficients(dense, 2);
  EXPECT_EQ(encoded[5], 0);
  EXPECT_EQ(encoded.size(), 26 + 4 * 128);
  EXPECT_EQ(packet_hash(encoded), "487e3d0087f168a1b2d4cdd44702bbe0d2bd6b6b8de2cd8dc09cea4cd676a177");
  EXPECT_EQ(b::cp02(encoded, 4, 2), dense);
  EXPECT_THROW(e::encode_coefficients({}, 1), std::invalid_argument);
  EXPECT_THROW(e::encode_coefficients(blocks, 0), std::invalid_argument);
  EXPECT_THROW(e::encode_coefficients(blocks, 257), std::invalid_argument);
  EXPECT_THROW(e::encode_coefficients(blocks, 3), std::invalid_argument);
  blocks[2][18] = 2049;
  EXPECT_THROW(e::encode_coefficients(blocks, 2), std::invalid_argument);
  blocks[2][18] = -2049;
  EXPECT_THROW(e::encode_coefficients(blocks, 2), std::invalid_argument);
}

TEST(GamebubV20Encoder, DeclaredMapsUseOutwardRoundedFixedRois) {
  for (auto map : c::maps) {
    const auto scales = e::scale_map(map);
    ASSERT_EQ(scales.size(), 1350);
    EXPECT_EQ(scales[0], map.background);
    EXPECT_EQ(scales[3 * 45 + 1], map.roi);
    EXPECT_EQ(scales[7 * 45 + 12], map.roi);
    EXPECT_EQ(scales[8 * 45 + 12], map.background);
    EXPECT_EQ(scales[22 * 45 + 10], map.roi);
    EXPECT_EQ(scales[26 * 45 + 34], map.roi);
    EXPECT_EQ(scales[26 * 45 + 35], map.background);
  }
  EXPECT_THROW(e::scale_map({16, 16}), std::invalid_argument);
}

TEST(GamebubV20Encoder, OriginalRgbKeyAndPredictivePromotionDecodeWithExactPublicationTags) {
  auto request = key_request();
  const auto key = e::encode_inner(request);
  ASSERT_TRUE(b::magic(key.inner, "GM01"));
  b::State state;
  b::Frame frame;
  std::string error;
  ASSERT_TRUE(b::decode(envelope(request, key), state, frame, error)) << error;
  ASSERT_TRUE(state.banks[0]);
  EXPECT_EQ(key.stored_tag, state.banks[0]->tag);
  EXPECT_TRUE(std::all_of(frame.planes[0].begin(), frame.planes[0].end(), [](auto value) {
    return value == 128;
  }));
  request.reference = std::make_shared<const b::Bank>(*state.banks[0]);
  request.reference_slot = 0;
  request.destination_slot = 255;
  request.frame_id = 8;
  request.key = false;
  const auto ordinary = e::encode_inner(request);
  EXPECT_EQ(ordinary.stored_tag, b::Tag {});
  ASSERT_TRUE(b::decode(envelope(request, ordinary), state, frame, error)) << error;
  request.frame_id = 9;
  request.destination_slot = 1;
  request.promoted = true;
  request.map = c::maps[3];
  const auto promoted = e::encode_inner(request);
  ASSERT_TRUE(b::decode(envelope(request, promoted), state, frame, error)) << error;
  EXPECT_EQ(promoted.stored_tag, state.banks[1]->tag);
  EXPECT_EQ(state.banks[0]->planes, state.banks[1]->planes);
}

TEST(GamebubV20Encoder, RejectsAbsentOriginalRgbAndInvalidReferenceIdentitiesBeforeEncoding) {
  auto request = key_request();
  request.source.reset();
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  std::vector<std::uint16_t> words(c::width * c::height, 0);
  request.source = std::make_shared<const c::Source>(std::span<const std::uint16_t>(words));
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  request = key_request();
  request.epoch = UINT32_MAX;
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  request = key_request();
  request.frame_id = UINT32_MAX;
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  request = key_request();
  request.reference_slot = 0;
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  request = key_request();
  request.key = false;
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  b::Planes planes;
  planes[0].assign(c::width * c::height, 128);
  planes[1].assign(c::width * c::height / 4, 128);
  planes[2] = planes[1];
  request.reference = std::make_shared<const b::Bank>(b::Bank {0, {}, planes});
  request.reference_slot = 0;
  request.destination_slot = 255;
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  request.reference = std::make_shared<const b::Bank>(b::Bank {request.frame_id, b::canonical_tag(planes, c::width, c::height), planes});
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  request.reference = std::make_shared<const b::Bank>(b::Bank {0, {}, {}});
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
}

TEST(GamebubV20Encoder, FrameAnalysisMatchesUncachedBytesAndTagsForEveryMapAndPublicationKind) {
  auto request = key_request();
  std::vector<std::uint8_t> rgb(c::width * c::height * 3);
  for (std::size_t i = 0; i < rgb.size(); ++i) {
    rgb[i] = static_cast<std::uint8_t>((i * 37 + i / 29) % 256);
  }
  request.source = std::make_shared<const c::Source>(rgb);
  b::Planes planes;
  planes[0].assign(c::width * c::height, 128);
  planes[1].assign(c::width * c::height / 4, 128);
  planes[2] = planes[1];
  for (unsigned kind = 0; kind < 3; ++kind) {
    request.key = kind == 0;
    request.promoted = kind == 2;
    request.reference = request.key ? nullptr : std::make_shared<const b::Bank>(b::Bank {0, b::canonical_tag(planes, c::width, c::height), planes});
    request.reference_slot = request.key ? 255 : 0;
    request.destination_slot = request.key ? 0 : request.promoted ? 1 :
                                                                    255;
    const auto analysis = e::analyze(request);
    EXPECT_EQ(analysis->coefficient_bytes(), 2073600U);
    EXPECT_EQ(analysis->plane(0).size(), 5400U);
    EXPECT_EQ(analysis->plane(1).size(), 1350U);
    EXPECT_EQ(analysis->plane(2).size(), 1350U);
    EXPECT_THROW(analysis->plane(3), std::invalid_argument);
    for (auto map : c::maps) {
      request.map = map;
      const auto uncached = e::encode_inner(request);
      const auto cached = e::encode_analyzed(request, *analysis);
      EXPECT_EQ(cached.inner, uncached.inner);
      EXPECT_EQ(cached.stored_tag, uncached.stored_tag);
    }
  }
}

TEST(GamebubV20Encoder, FrameAnalysisRejectsIdentityChangesAndMutatedReferenceAliases) {
  auto request = key_request();
  const auto key_analysis = e::analyze(request);
  auto changed = request;
  changed.source = key_request().source;
  EXPECT_THROW(e::encode_analyzed(changed, *key_analysis), std::invalid_argument);
  changed = request;
  ++changed.epoch;
  EXPECT_THROW(e::encode_analyzed(changed, *key_analysis), std::invalid_argument);
  changed = request;
  ++changed.frame_id;
  EXPECT_THROW(e::encode_analyzed(changed, *key_analysis), std::invalid_argument);
  changed = request;
  changed.reference_slot = 0;
  EXPECT_THROW(key_analysis->require_identity(changed), std::invalid_argument);
  changed = request;
  changed.destination_slot = 1;
  EXPECT_THROW(key_analysis->require_identity(changed), std::invalid_argument);
  changed = request;
  changed.key = false;
  EXPECT_THROW(key_analysis->require_identity(changed), std::invalid_argument);
  changed = request;
  changed.promoted = true;
  EXPECT_THROW(key_analysis->require_identity(changed), std::invalid_argument);
  b::Planes planes;
  planes[0].assign(c::width * c::height, 128);
  planes[1].assign(c::width * c::height / 4, 128);
  planes[2] = planes[1];
  auto aliased = std::make_shared<b::Bank>(b::Bank {0, b::canonical_tag(planes, c::width, c::height), planes});
  request.reference = aliased;
  request.reference_slot = 0;
  request.destination_slot = 255;
  request.key = false;
  const auto prediction = e::analyze(request);
  changed = request;
  changed.reference = std::make_shared<const b::Bank>(*aliased);
  EXPECT_THROW(e::encode_analyzed(changed, *prediction), std::invalid_argument);
  aliased->planes[0][0] = 129;
  EXPECT_THROW(e::encode_analyzed(request, *prediction), std::invalid_argument);
  EXPECT_THROW(e::encode_inner(request), std::invalid_argument);
  aliased->tag = b::canonical_tag(aliased->planes, c::width, c::height);
  EXPECT_THROW(e::encode_analyzed(request, *prediction), std::invalid_argument);
  aliased->planes = planes;
  aliased->tag = b::canonical_tag(planes, c::width, c::height);
  ++aliased->id;
  EXPECT_THROW(e::encode_analyzed(request, *prediction), std::invalid_argument);
}

TEST(GamebubV20Encoder, FrameBuilderBoundsAttemptsAndReleasesOwnedSourceWithItsAnalysis) {
  auto request = key_request();
  std::weak_ptr<const c::Source> retained = request.source;
  {
    e::FrameBuilder builder;
    EXPECT_EQ(builder.analysis_builds(), 0U);
    EXPECT_EQ(builder.attempts(), 0U);
    EXPECT_EQ(builder.coefficient_bytes(), 0U);
    auto invalid = request;
    invalid.source.reset();
    EXPECT_THROW(builder(invalid), std::invalid_argument);
    EXPECT_EQ(builder.analysis_builds(), 0U);
    for (auto map : c::maps) {
      request.map = map;
      const auto actual = builder(request);
      EXPECT_EQ(actual.inner, e::encode_inner(request).inner);
    }
    EXPECT_EQ(builder.analysis_builds(), 1U);
    EXPECT_EQ(builder.attempts(), 4U);
    EXPECT_EQ(builder.coefficient_bytes(), 2073600U);
    EXPECT_THROW(builder(request), std::invalid_argument);
    request.source.reset();
    EXPECT_FALSE(retained.expired());
  }
  EXPECT_TRUE(retained.expired());
  request = key_request();
  e::FrameBuilder one_frame;
  one_frame(request);
  // A second prepare starts again at map0, even when frame/source identity is unchanged.
  EXPECT_THROW(one_frame(request), std::invalid_argument);
  ++request.frame_id;
  request.map = c::maps[1];
  EXPECT_THROW(one_frame(request), std::invalid_argument);
  EXPECT_EQ(one_frame.attempts(), 1U);
  request = key_request();
  request.map = {16, 16};
  EXPECT_THROW(e::analyze(request), std::invalid_argument);
}
