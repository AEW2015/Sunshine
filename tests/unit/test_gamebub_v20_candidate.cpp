/**
 * @file tests/unit/test_gamebub_v20_candidate.cpp
 * @brief Native mandatory-HUD coverage, paid retries and exact ownership regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <algorithm>
#include <limits>
#include <memory>
#include <type_traits>
#include <vector>

// local includes
#include "tools/gamebub/native/candidate.h"

namespace {
  namespace c = gamebub::v20::candidate;
  namespace b = gamebub::v20::body;

  /** @brief Write one bounded little-endian test word. */
  void put16(std::vector<std::uint8_t> &data, std::size_t offset, std::uint16_t value) {
    data[offset] = value;
    data[offset + 1] = value >> 8;
  }

  /** @brief Add an actual IEEE trailer to one complete synthetic test body. */
  void add_crc(std::vector<std::uint8_t> &data) {
    const auto crc = gamebub::v20::crc32(data);
    data.resize(data.size() + 4);
    b::put32(data, data.size() - 4, crc);
  }

  /** @brief Reseal feedback after controlled identity/CRC-negative mutations. */
  void reseal(std::array<std::uint8_t, 43> &data) {
    b::put32(data, 39, gamebub::v20::crc32(std::span(data).first(39)));
  }

  /** @brief Encode legal all-zero CP02 coefficients with independent DC/AC bit sections. */
  std::vector<std::uint8_t> zero_plane(unsigned bw, unsigned bh) {
    const unsigned blocks = bw * bh, ndc = 1 + (blocks + 7) / 8, nac = 3 + (2 * blocks + 7) / 8;
    std::vector<std::uint8_t> data(22 + ndc + nac);
    std::copy_n("CP02", 4, data.begin());
    data[4] = 1;
    data[5] = 1;
    b::put32(data, 6, blocks);
    put16(data, 10, bw);
    b::put32(data, 14, ndc);
    b::put32(data, 18, nac);
    for (unsigned i = 0; i < blocks; ++i) {
      data[23 + i / 8] |= 1U << (7 - i % 8);
    }
    add_crc(data);
    return data;
  }

  /** @brief Return a real hash-validated uniform reconstructed reference. */
  b::Bank gray_bank(std::uint32_t id = 0) {
    b::Planes planes;
    planes[0].assign(c::width * c::height, 128);
    planes[1].assign(c::width * c::height / 4, 128);
    planes[2] = planes[1];
    return {id, b::canonical_tag(planes, c::width, c::height), std::move(planes)};
  }

  /** @brief Supply an explicit valid GM01 base encoder stub, not an RGB transform implementation. */
  c::BuildResult zero_builder(const c::BuildRequest &request) {
    constexpr unsigned mw = 45, mh = 30, nmap = (mw * mh + 3) / 4;
    auto y = zero_plane(90, 60), u = zero_plane(45, 30), v = u;
    std::vector<std::uint8_t> data(46 + nmap);
    std::copy_n("GM01", 4, data.begin());
    data[4] = 1;
    data[5] = request.key;
    b::put32(data, 6, request.epoch);
    b::put32(data, 10, request.frame_id);
    b::put32(data, 14, request.key ? 0xffffffffU : request.reference->id);
    put16(data, 18, c::width);
    put16(data, 20, c::height);
    put16(data, 26, mw);
    put16(data, 28, mh);
    b::put32(data, 30, nmap);
    b::put32(data, 34, y.size());
    b::put32(data, 38, u.size());
    b::put32(data, 42, v.size());
    for (unsigned row = 0; row < mh; ++row) {
      for (unsigned col = 0; col < mw; ++col) {
        unsigned scale = request.map.background;
        for (const auto roi : c::base_regions) {
          if (col >= roi.x / 16 && col < (roi.x + roi.width + 15) / 16 && row >= roi.y / 16 && row < (roi.y + roi.height + 15) / 16) {
            scale = request.map.roi;
          }
        }
        const unsigned index = row * mw + col, code = scale == 8 ? 0 : scale == 16 ? 1 :
                                                                                     2;
        data[46 + index / 4] |= code << (6 - 2 * (index % 4));
      }
    }
    data.insert(data.end(), y.begin(), y.end());
    data.insert(data.end(), u.begin(), u.end());
    data.insert(data.end(), v.begin(), v.end());
    add_crc(data);
    return {std::move(data), request.key || request.promoted ? gray_bank().tag : b::Tag {}};
  }

  /** @brief Encode real raw HP01 packets for every requested source rectangle. */
  std::vector<std::vector<std::uint8_t>> raw_patches(const c::Source &source) {
    std::vector<std::vector<std::uint8_t>> result;
    for (const auto r : c::rectangles) {
      std::vector<std::uint8_t> data(24 + 2 * r.width * r.height);
      std::copy_n("HP01", 4, data.begin());
      data[4] = 1;
      put16(data, 6, r.x);
      put16(data, 8, r.y);
      put16(data, 10, r.width);
      put16(data, 12, r.height);
      b::put32(data, 16, r.width * r.height);
      b::put32(data, 20, 2 * r.width * r.height);
      for (unsigned y = 0; y < r.height; ++y) {
        for (unsigned x = 0; x < r.width; ++x) {
          put16(data, 24 + 2 * (y * r.width + x), source.words()[(r.y + y) * c::width + r.x + x]);
        }
      }
      add_crc(data);
      result.push_back(std::move(data));
    }
    return result;
  }

  /** @brief Create an immutable source from mutable caller storage. */
  std::shared_ptr<const c::Source> source(std::uint16_t value = 0x1234) {
    return std::make_shared<const c::Source>(std::vector<std::uint16_t>(c::width * c::height, value));
  }

  /** @brief Independently decode a policy packet to obtain its actual AF03 oracle. */
  b::Frame decode_packet(std::span<const std::uint8_t> packet, bool key = true, unsigned reference_slot = 0) {
    b::State state;
    if (!key) {
      state.banks[reference_slot] = gray_bank();
      state.width = c::width;
      state.height = c::height;
    }
    b::Frame frame;
    std::string error;
    if (!b::decode(packet, state, frame, error)) {
      throw std::runtime_error(error);
    }
    return frame;
  }

  /** @brief Commit/ACK one real valid key to establish the predictor fixture. */
  void establish(c::Policy &policy, const std::shared_ptr<const c::Source> &pixels) {
    auto prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
    auto feedback = decode_packet(policy.packet(prepared)).feedback;
    policy.commit(prepared);
    if (!policy.acknowledge(feedback)) {
      throw std::runtime_error("key was not resolved");
    }
  }
}  // namespace

TEST(GamebubV20Candidate, FullMandatoryCoverageAndExactReferenceAck) {
  c::Policy policy;
  auto pixels = source();
  auto prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  ASSERT_TRUE(prepared.accepted());
  ASSERT_EQ(prepared.metrics().attempts.size(), 1U);
  EXPECT_EQ(prepared.metrics().reason, "mandatory_complete");
  EXPECT_EQ(prepared.metrics().patch_bytes, 42368U);
  EXPECT_EQ(policy.last_issued(), -1);
  EXPECT_EQ(policy.pending(), 0U);
  auto frame = decode_packet(policy.packet(prepared));
  for (const auto rect : c::rectangles) {
    for (unsigned y = 0; y < rect.height; ++y) {
      for (unsigned x = 0; x < rect.width; ++x) {
        ASSERT_EQ(frame.display565[(rect.y + y) * c::width + rect.x + x], 0x1234);
      }
    }
  }
  auto bytes = policy.commit(prepared);
  EXPECT_LE(bytes.size(), 49152U);
  EXPECT_FALSE(policy.active());
  EXPECT_EQ(policy.last_issued(), 0);
  EXPECT_EQ(policy.pending(), 1U);
  EXPECT_THROW(policy.acquire(0), std::invalid_argument);
  ASSERT_TRUE(policy.acknowledge(frame.feedback));
  EXPECT_EQ(policy.pending(), 0U);
  auto reader = policy.acquire(0);
  EXPECT_EQ(reader->bank().id, 0U);
  EXPECT_EQ(reader->bank().tag, gray_bank().tag);
  EXPECT_FALSE(policy.acknowledge(frame.feedback));
  EXPECT_THROW(policy.commit(prepared), std::invalid_argument);
  EXPECT_THROW(policy.discard(prepared), std::invalid_argument);
}

TEST(GamebubV20Candidate, RejectedAttemptsArePaidAndDoNotBurnIdentityOrExternalReaders) {
  c::Policy policy;
  auto pixels = source();
  establish(policy, pixels);
  auto external = policy.acquire(0);
  unsigned calls = 0;
  const auto retry = [&](const c::BuildRequest &request) {
    ++calls;
    EXPECT_EQ(policy.readers(0), 2U);
    return calls < 4 ? c::BuildResult {std::vector<std::uint8_t>(49152), {}} : zero_builder(request);
  };
  auto prepared = policy.prepare(pixels, 1, raw_patches, retry);
  ASSERT_TRUE(prepared.accepted());
  ASSERT_EQ(calls, 4U);
  ASSERT_EQ(prepared.metrics().attempts.size(), 4U);
  for (unsigned i = 0; i < 4; ++i) {
    const auto &attempt = prepared.metrics().attempts[i];
    EXPECT_EQ(attempt.map, c::maps[i]);
    EXPECT_GT(attempt.build_ns, 0U);
    if (i < 3) {
      EXPECT_FALSE(attempt.accepted);
      EXPECT_GT(attempt.discard_ns, 0U);
    } else {
      EXPECT_TRUE(attempt.accepted);
    }
  }
  EXPECT_EQ(policy.last_issued(), 0);
  EXPECT_EQ(policy.readers(0), 2U);
  policy.discard(prepared);
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_EQ(policy.last_issued(), 0);
  calls = 0;
  prepared = policy.prepare(pixels, 1, raw_patches, retry);
  auto feedback = decode_packet(policy.packet(prepared), false).feedback;
  policy.commit(prepared);
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_TRUE(policy.acknowledge(feedback));
  EXPECT_EQ(policy.readers(0), 1U);
  external.reset();
  EXPECT_EQ(policy.readers(0), 0U);
}

TEST(GamebubV20Candidate, AllMapsExhaustedAndImpossibleReservationAreWholeFrameRejections) {
  auto pixels = source();
  c::Policy policy;
  unsigned calls = 0;
  auto failure = policy.prepare(pixels, 0, raw_patches, [&](const auto &) {
    ++calls;
    return c::BuildResult {std::vector<std::uint8_t>(49152), {}};
  });
  EXPECT_FALSE(failure.accepted());
  EXPECT_EQ(calls, 4U);
  EXPECT_EQ(failure.metrics().attempts.size(), 4U);
  EXPECT_EQ(failure.metrics().reason, "all_declared_maps_exceed_complete_cap");
  EXPECT_EQ(policy.last_issued(), -1);
  EXPECT_FALSE(policy.active());
  EXPECT_EQ(policy.pending(), 0U);
  auto retry = policy.prepare(pixels, 0, raw_patches, zero_builder);
  EXPECT_TRUE(retry.accepted());
  policy.discard(retry);
  policy.set_frame_cap(128);
  calls = 0;
  failure = policy.prepare(pixels, 0, raw_patches, [&](const auto &) {
    ++calls;
    return c::BuildResult {};
  });
  EXPECT_FALSE(failure.accepted());
  EXPECT_EQ(calls, 0U);
  EXPECT_EQ(failure.metrics().reason, "mandatory_ui_exceeds_complete_cap");
  EXPECT_THROW(policy.commit(failure), std::invalid_argument);
  EXPECT_THROW(policy.discard(failure), std::invalid_argument);
}

TEST(GamebubV20Candidate, SourceCopyAndExplicitResolutionReleaseCaptureDespiteRetainedHandle) {
  static_assert(!std::is_copy_constructible_v<c::Source>);
  static_assert(!std::is_move_constructible_v<c::Source>);
  static_assert(!std::is_copy_assignable_v<c::Source>);
  static_assert(!std::is_move_assignable_v<c::Source>);
  std::vector<std::uint16_t> mutable_words(c::width * c::height, 0x1234);
  auto pixels = std::make_shared<const c::Source>(mutable_words);
  EXPECT_TRUE(pixels->rgb8().empty());
  std::weak_ptr<const c::Source> weak = pixels;
  mutable_words[0] = 0;
  EXPECT_EQ(pixels->words()[0], 0x1234);
  c::Policy policy;
  auto prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  pixels.reset();
  EXPECT_FALSE(weak.expired());
  EXPECT_THROW(policy.prepare(source(), 1, raw_patches, zero_builder), std::invalid_argument);
  policy.discard(prepared);
  EXPECT_TRUE(weak.expired());
  pixels = source();
  weak = pixels;
  prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  pixels.reset();
  policy.commit(prepared);
  EXPECT_TRUE(weak.expired());
}

TEST(GamebubV20Candidate, StaleCommitRetainsDiscardableLeaseAndForeignHandlesCannotResolveIt) {
  c::Policy policy;
  auto pixels = source();
  establish(policy, pixels);
  auto external = policy.acquire(0);
  auto prepared = policy.prepare(pixels, 1, raw_patches, zero_builder);
  EXPECT_EQ(policy.readers(0), 2U);
  policy.set_frame_cap(49151);
  EXPECT_THROW(policy.commit(prepared), std::invalid_argument);
  EXPECT_TRUE(policy.active());
  EXPECT_EQ(policy.readers(0), 2U);
  c::Policy foreign;
  auto other = foreign.prepare(pixels, 0, raw_patches, zero_builder);
  EXPECT_THROW(policy.commit(other), std::invalid_argument);
  EXPECT_THROW(policy.discard(other), std::invalid_argument);
  policy.discard(prepared);
  EXPECT_EQ(policy.readers(0), 1U);
  foreign.discard(other);
}

TEST(GamebubV20Candidate, MalformedOrChangedSourcePatchesAndBuilderFailuresCannotPublish) {
  c::Policy policy;
  auto pixels = source();
  establish(policy, pixels);
  auto external = policy.acquire(0);
  for (unsigned kind = 0; kind < 4; ++kind) {
    auto broken = [&](const c::Source &s) {
      auto patches = raw_patches(s);
      if (kind == 0) {
        patches.pop_back();
      }
      if (kind == 1) {
        patches[0][24] ^= 1;
        const auto crc = gamebub::v20::crc32(std::span(patches[0]).first(patches[0].size() - 4));
        b::put32(patches[0], patches[0].size() - 4, crc);
      }
      if (kind == 2) {
        std::swap(patches[0], patches[1]);
      }
      if (kind == 3) {
        patches[0].back() ^= 1;
      }
      return patches;
    };
    EXPECT_THROW(policy.prepare(pixels, 1, broken, zero_builder), std::invalid_argument);
    EXPECT_EQ(policy.readers(0), 1U);
    EXPECT_FALSE(policy.active());
    EXPECT_EQ(policy.last_issued(), 0);
  }
  EXPECT_THROW(policy.prepare(pixels, 1, raw_patches, [](const auto &) -> c::BuildResult {
    throw std::runtime_error("injected");
  }),
               std::runtime_error);
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_FALSE(policy.active());
  auto wrong_tag = [](const auto &request) {
    auto result = zero_builder(request);
    result.stored_tag[0] = 1;
    return result;
  };
  EXPECT_THROW(policy.prepare(pixels, 1, raw_patches, wrong_tag), std::invalid_argument);
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_EQ(policy.pending(), 0U);
}

TEST(GamebubV20Candidate, PendingWindowAndExactAf03IdentityDoNotFabricatePublication) {
  c::Policy policy;
  auto pixels = source();
  establish(policy, pixels);
  std::vector<std::array<std::uint8_t, 43>> feedback;
  for (unsigned id = 1; id <= 3; ++id) {
    auto p = policy.prepare(pixels, id, raw_patches, zero_builder);
    feedback.push_back(decode_packet(policy.packet(p), false).feedback);
    policy.commit(p);
  }
  EXPECT_EQ(policy.pending(), 3U);
  EXPECT_THROW(policy.prepare(pixels, 4, raw_patches, zero_builder), std::invalid_argument);
  auto bad = feedback[0];
  b::put32(bad, 14, 0);
  reseal(bad);
  EXPECT_THROW(policy.acknowledge(bad), std::invalid_argument);
  bad = feedback[0];
  b::put32(bad, 6, 2);
  reseal(bad);
  EXPECT_THROW(policy.acknowledge(bad), std::invalid_argument);
  bad = feedback[0];
  bad[23] = 1;
  reseal(bad);
  EXPECT_THROW(policy.acknowledge(bad), std::invalid_argument);
  bad = feedback[0];
  bad.back() ^= 1;
  EXPECT_THROW(policy.acknowledge(bad), std::invalid_argument);
  bad = feedback[0];
  b::put32(bad, 10, 100);
  reseal(bad);
  EXPECT_FALSE(policy.acknowledge(bad));
  EXPECT_EQ(policy.pending(), 3U);
  EXPECT_TRUE(policy.acknowledge(feedback[0]));
  auto prepared = policy.prepare(pixels, 4, raw_patches, zero_builder);
  EXPECT_TRUE(policy.acknowledge(feedback[1]));
  EXPECT_THROW(policy.commit(prepared), std::invalid_argument);
  policy.discard(prepared);
  EXPECT_TRUE(policy.acknowledge(feedback[2]));
  EXPECT_EQ(policy.pending(), 0U);
}

TEST(GamebubV20Candidate, KeyNackAndReaderOwnedDestinationsRemainUnconfirmed) {
  c::Policy policy;
  auto pixels = source();
  auto prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  auto feedback = decode_packet(policy.packet(prepared)).feedback;
  policy.commit(prepared);
  feedback[5] = 2;
  feedback[18] = 255;
  b::put32(feedback, 19, 0xffffffffU);
  std::fill(feedback.begin() + 23, feedback.begin() + 39, 0);
  reseal(feedback);
  EXPECT_TRUE(policy.acknowledge(feedback));
  EXPECT_THROW(policy.acquire(0), std::invalid_argument);
  prepared = policy.prepare(pixels, 1, raw_patches, zero_builder);
  auto accepted = decode_packet(policy.packet(prepared)).feedback;
  policy.commit(prepared);
  EXPECT_THROW(policy.prepare(pixels, 2, raw_patches, zero_builder, true), std::invalid_argument);
  EXPECT_TRUE(policy.acknowledge(accepted));
  auto external = policy.acquire(0);
  EXPECT_THROW(policy.prepare(pixels, 2, raw_patches, zero_builder, true), std::invalid_argument);
}

TEST(GamebubV20Candidate, ConfirmedReferencesAndExternalLeaseSurvivePolicyLifetime) {
  auto bank = gray_bank();
  std::unique_ptr<c::Lease> external;
  {
    c::Policy policy;
    policy.seed_reference(0, bank);
    external = policy.acquire(0);
    EXPECT_EQ(policy.readers(0), 1U);
    EXPECT_EQ(external->bank().planes[0][0], 128);
    EXPECT_THROW(policy.seed_reference(0, bank), std::invalid_argument);
    EXPECT_THROW(policy.acquire(2), std::invalid_argument);
    EXPECT_THROW(policy.readers(2), std::invalid_argument);
  }
  EXPECT_EQ(external->bank().id, 0U);
  EXPECT_EQ(external->bank().planes[0].size(), c::width * c::height);
  external.reset();
  bank.tag[0] ^= 1;
  c::Policy policy;
  EXPECT_THROW(policy.seed_reference(0, bank), std::invalid_argument);
}

TEST(GamebubV20Candidate, RejectInvalidConfigurationCallbacksAndIdentityBeforeMutation) {
  EXPECT_THROW(c::Policy(114), std::invalid_argument);
  EXPECT_THROW(c::Policy(49153), std::invalid_argument);
  EXPECT_THROW(c::Policy(49152, 0xffffffffU), std::invalid_argument);
  EXPECT_THROW(c::Source(std::vector<std::uint16_t>(3)), std::invalid_argument);
  EXPECT_THROW(c::Source(std::vector<std::uint16_t>(2 * c::width * c::height)), std::invalid_argument);
  EXPECT_THROW(c::Source(std::vector<std::uint8_t>(3)), std::invalid_argument);
  EXPECT_THROW(c::Source(std::vector<std::uint8_t>(6 * c::width * c::height)), std::invalid_argument);
  c::Policy policy;
  auto pixels = source();
  EXPECT_THROW(policy.prepare(nullptr, 0, raw_patches, zero_builder), std::invalid_argument);
  EXPECT_THROW(policy.prepare(pixels, 0, {}, zero_builder), std::invalid_argument);
  EXPECT_THROW(policy.prepare(pixels, 0, raw_patches, {}), std::invalid_argument);
  EXPECT_THROW(policy.prepare(pixels, 0xffffffffU, raw_patches, zero_builder), std::invalid_argument);
  EXPECT_THROW(policy.set_frame_cap(0), std::invalid_argument);
  EXPECT_EQ(policy.frame_cap(), 49152U);
  policy.set_frame_cap(49152);
  EXPECT_EQ(policy.frame_cap(), 49152U);
  auto recursive = [&](const auto &) -> c::BuildResult {
    policy.set_frame_cap(49151);
    return {};
  };
  EXPECT_THROW(policy.prepare(pixels, 0, raw_patches, recursive), std::invalid_argument);
  EXPECT_FALSE(policy.active());
  EXPECT_EQ(policy.last_issued(), -1);
}

TEST(GamebubV20Candidate, ExactCompleteCapBoundaryDoesNotOmitAnyPatch) {
  c::Policy policy;
  auto pixels = source();
  auto prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  const auto full = policy.packet(prepared).size();
  policy.discard(prepared);
  policy.set_frame_cap(full);
  prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  ASSERT_TRUE(prepared.accepted());
  EXPECT_EQ(policy.packet(prepared).size(), full);
  policy.discard(prepared);
  policy.set_frame_cap(full - 1);
  prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  EXPECT_FALSE(prepared.accepted());
  ASSERT_EQ(prepared.metrics().attempts.size(), 4U);
  for (const auto &attempt : prepared.metrics().attempts) {
    EXPECT_EQ(attempt.complete_bytes, full);
  }
  EXPECT_EQ(policy.last_issued(), -1);
  EXPECT_EQ(policy.pending(), 0U);
}

TEST(GamebubV20Candidate, PromotedNewestReferenceIsPrivateUntilExactAck) {
  for (bool two_banks : {false, true}) {
    c::Policy policy;
    auto pixels = source();
    if (two_banks) {
      policy.seed_reference(0, gray_bank());
    }
    policy.seed_reference(1, gray_bank(5));
    auto builder = [](const c::BuildRequest &request) {
      EXPECT_EQ(request.reference_slot, 1U);
      EXPECT_EQ(request.reference->id, 5U);
      EXPECT_TRUE(request.promoted);
      return zero_builder(request);
    };
    auto prepared = policy.prepare(pixels, 6, raw_patches, builder, false, true);
    EXPECT_EQ(policy.readers(1), 1U);
    b::State state;
    state.width = c::width;
    state.height = c::height;
    state.banks[1] = gray_bank(5);
    b::Frame frame;
    std::string error;
    ASSERT_TRUE(b::decode(policy.packet(prepared), state, frame, error)) << error;
    policy.commit(prepared);
    EXPECT_EQ(policy.readers(1), 0U);
    EXPECT_THROW(policy.acquire(1), std::invalid_argument);
    EXPECT_TRUE(policy.acknowledge(frame.feedback));
    auto external = policy.acquire(1);
    EXPECT_EQ(external->bank().id, 6U);
    EXPECT_THROW(policy.prepare(pixels, 7, raw_patches, zero_builder, false, true), std::invalid_argument);
  }
}

TEST(GamebubV20Candidate, LateDestinationReaderBlocksCommitWithoutReleasingAnotherOwner) {
  c::Policy policy;
  auto pixels = source();
  policy.seed_reference(0, gray_bank());
  auto prepared = policy.prepare(pixels, 1, raw_patches, zero_builder, true);
  auto external = policy.acquire(0);
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_THROW(policy.commit(prepared), std::invalid_argument);
  EXPECT_TRUE(policy.active());
  external.reset();
  EXPECT_EQ(policy.readers(0), 0U);
  policy.commit(prepared);
  EXPECT_EQ(policy.last_issued(), 1);
  EXPECT_EQ(policy.pending(), 1U);
}

TEST(GamebubV20Candidate, CommittedConsumerAndReentrantCallbacksCannotChangeOwnership) {
  c::Policy policy;
  auto pixels = source();
  establish(policy, pixels);
  auto prepared = policy.prepare(pixels, 1, raw_patches, zero_builder);
  auto ack = decode_packet(policy.packet(prepared), false).feedback;
  policy.commit(prepared);
  EXPECT_THROW(policy.prepare(pixels, 2, raw_patches, zero_builder, true), std::invalid_argument);
  EXPECT_THROW(policy.prepare(pixels, 1, raw_patches, zero_builder), std::invalid_argument);
  EXPECT_THROW(policy.seed_reference(1, gray_bank()), std::invalid_argument);
  for (unsigned kind = 0; kind < 6; ++kind) {
    auto recursive = [&](const c::BuildRequest &) -> c::BuildResult {
      switch (kind) {
        case 0:
          policy.acquire(0);
          break;
        case 1:
          policy.seed_reference(1, gray_bank());
          break;
        case 2:
          policy.prepare(pixels, 3, raw_patches, zero_builder);
          break;
        case 3:
          policy.commit(c::Prepared {});
          break;
        case 4:
          policy.discard(c::Prepared {});
          break;
        case 5:
          policy.acknowledge(ack);
          break;
      }
      return {};
    };
    EXPECT_THROW(policy.prepare(pixels, 2, raw_patches, recursive), std::invalid_argument);
    EXPECT_FALSE(policy.active());
    EXPECT_EQ(policy.readers(0), 0U);
    EXPECT_EQ(policy.pending(), 1U);
  }
  EXPECT_TRUE(policy.acknowledge(ack));
}

TEST(GamebubV20Candidate, InvalidInnerIdentityMapAndEntropyCannotConsumeAnId) {
  auto pixels = source();
  c::Policy policy;
  for (unsigned kind = 0; kind < 15; ++kind) {
    const auto broken = [&](const c::BuildRequest &request) {
      auto result = zero_builder(request);
      switch (kind) {
        case 0:
          result.inner[0] ^= 1;
          break;
        case 1:
          result.inner[4] = 2;
          break;
        case 2:
          result.inner[5] = 0;
          break;
        case 3:
          b::put32(result.inner, 6, 2);
          break;
        case 4:
          b::put32(result.inner, 10, 7);
          break;
        case 5:
          b::put32(result.inner, 14, 0);
          break;
        case 6:
          put16(result.inner, 18, c::width - 2);
          break;
        case 7:
          put16(result.inner, 22, 1);
          break;
        case 8:
          put16(result.inner, 26, 44);
          break;
        case 9:
          b::put32(result.inner, 30, 337);
          break;
        case 10:
          b::put32(result.inner, 34, 0xffffffffU);
          break;
        case 11:
          result.inner.back() ^= 1;
          break;
        case 12:
          result.inner[46] ^= 0xc0;
          break;
        case 13:
          result.inner[46 + 338 + 22] = 14;
          break;
        case 14:
          result.stored_tag[0] ^= 1;
          break;
      }
      if (kind != 11) {
        b::put32(result.inner, result.inner.size() - 4, gamebub::v20::crc32(std::span(result.inner).first(result.inner.size() - 4)));
      }
      return result;
    };
    EXPECT_THROW(policy.prepare(pixels, 0, raw_patches, broken), std::invalid_argument) << kind;
    EXPECT_FALSE(policy.active());
    EXPECT_EQ(policy.last_issued(), -1);
    EXPECT_EQ(policy.pending(), 0U);
  }
  auto prepared = policy.prepare(pixels, 0, raw_patches, zero_builder);
  EXPECT_TRUE(prepared.accepted());
  policy.discard(prepared);
}

TEST(GamebubV20Candidate, TotalExternalAndCandidateReadersRemainBoundedAcrossBothBanks) {
  c::Policy policy;
  auto pixels = source();
  policy.seed_reference(0, gray_bank());
  policy.seed_reference(1, gray_bank(1));
  auto first = policy.acquire(0), second = policy.acquire(0), third = policy.acquire(1);
  EXPECT_EQ(policy.readers(0), 2U);
  EXPECT_EQ(policy.readers(1), 1U);
  EXPECT_THROW(policy.acquire(1), std::invalid_argument);
  unsigned calls = 0;
  auto builder = [&](const c::BuildRequest &r) {
    ++calls;
    return zero_builder(r);
  };
  EXPECT_THROW(policy.prepare(pixels, 2, raw_patches, builder), std::invalid_argument);
  EXPECT_FALSE(policy.active());
  EXPECT_EQ(calls, 0U);
  EXPECT_EQ(policy.readers(0), 2U);
  EXPECT_EQ(policy.readers(1), 1U);
  first.reset();
  auto prepared = policy.prepare(pixels, 2, raw_patches, builder);
  EXPECT_TRUE(prepared.accepted());
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_EQ(policy.readers(1), 2U);
  policy.discard(prepared);
  EXPECT_EQ(policy.readers(0), 1U);
  EXPECT_EQ(policy.readers(1), 1U);
  second.reset();
  third.reset();
  EXPECT_EQ(policy.readers(0), 0U);
  EXPECT_EQ(policy.readers(1), 0U);
}

TEST(GamebubV20Candidate, ConfirmedPreconditionRaisesButNeverLowersCommittedIdentityBound) {
  c::Policy policy;
  auto pixels = source();
  policy.seed_reference(1, gray_bank(5));
  EXPECT_EQ(policy.last_issued(), 5);
  policy.seed_reference(0, gray_bank(2));
  EXPECT_EQ(policy.last_issued(), 5);
  EXPECT_THROW(policy.prepare(pixels, 5, raw_patches, zero_builder, true), std::invalid_argument);
  EXPECT_THROW(policy.prepare(pixels, 0, raw_patches, zero_builder, true), std::invalid_argument);
  auto prepared = policy.prepare(pixels, 6, raw_patches, zero_builder, true);
  EXPECT_TRUE(prepared.accepted());
  policy.discard(prepared);
  EXPECT_EQ(policy.last_issued(), 5);
}

TEST(GamebubV20Candidate, OriginalRgb8AndExact565WordsRemainOwnedAndUnmodified) {
  std::vector<std::uint8_t> bytes(c::width * c::height * 3, 255);
  const std::array<std::array<std::uint8_t, 3>, 8> colors {{{255, 0, 0}, {0, 255, 0}, {0, 0, 255}, {0, 0, 0}, {255, 255, 255}, {173, 102, 57}, {7, 3, 7}, {8, 4, 8}}};
  const std::array<std::uint16_t, 8> expected {0xf800, 0x07e0, 0x001f, 0, 0xffff, 0xab27, 0, 0x0821};
  for (std::size_t i = 0; i < colors.size(); ++i) {
    std::copy(colors[i].begin(), colors[i].end(), bytes.begin() + 3 * i);
  }
  const auto snapshot = bytes;
  auto pixels = std::make_shared<const c::Source>(bytes);
  std::fill(bytes.begin(), bytes.end(), 0);
  EXPECT_EQ(pixels->rgb8().size(), c::width * c::height * 3);
  EXPECT_TRUE(std::equal(pixels->rgb8().begin(), pixels->rgb8().end(), snapshot.begin()));
  EXPECT_TRUE(std::equal(expected.begin(), expected.end(), pixels->words().begin()));
  EXPECT_EQ(pixels->rgb8()[15], 173);
  EXPECT_EQ(pixels->words()[5], 0xab27);
}

TEST(GamebubV20Candidate, Rgb8CaptureLifetimeEndsAtExplicitCommitOrDiscard) {
  for (bool commit : {false, true}) {
    auto pixels = std::make_shared<const c::Source>(std::vector<std::uint8_t>(c::width * c::height * 3, 128));
    std::weak_ptr<const c::Source> weak = pixels;
    c::Policy policy;
    bool saw_rgb8 = false;
    const auto builder = [&](const c::BuildRequest &request) {
      saw_rgb8 = request.source->rgb8().size() == c::width * c::height * 3;
      EXPECT_EQ(request.source->rgb8()[0], 128);
      EXPECT_EQ(request.source->words()[0], 0x8410);
      return zero_builder(request);
    };
    auto prepared = policy.prepare(pixels, 0, raw_patches, builder);
    ASSERT_TRUE(prepared.accepted());
    EXPECT_TRUE(saw_rgb8);
    pixels.reset();
    EXPECT_FALSE(weak.expired());
    if (commit) {
      policy.commit(prepared);
    } else {
      policy.discard(prepared);
    }
    EXPECT_TRUE(weak.expired());
  }
}
