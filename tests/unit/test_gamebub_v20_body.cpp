/**
 * @file tests/unit/test_gamebub_v20_body.cpp
 * @brief Full-body arithmetic, nested parsing and atomic publication regressions.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <array>
#include <bit>
#include <string>
#include <utility>
#include <vector>

// local includes
#include "tools/gamebub/native/body_decoder.h"

namespace {
  namespace body = gamebub::v20::body;

  /** @brief Store a bounded16-bit synthetic fixture value. */
  void word16(std::vector<std::uint8_t> &bytes, std::size_t at, unsigned value) {
    bytes[at] = static_cast<std::uint8_t>(value);
    bytes[at + 1] = static_cast<std::uint8_t>(value >> 8);
  }

  /** @brief Append an IEEE trailer to a private synthetic message. */
  std::vector<std::uint8_t> sealed(std::vector<std::uint8_t> bytes) {
    const auto n = bytes.size();
    bytes.resize(n + 4);
    body::put32(bytes, n, gamebub::v20::crc32(std::span(bytes).first(n)));
    return bytes;
  }

  /** @brief Recalculate a mutated message's CRC to exercise deeper validation. */
  void reseal(std::vector<std::uint8_t> &bytes) {
    body::put32(bytes, bytes.size() - 4, gamebub::v20::crc32(std::span(bytes).first(bytes.size() - 4)));
  }

  /** @brief Build one legal raw CP02 block in natural coefficient order. */
  std::vector<std::uint8_t> raw_coeff(unsigned dc = 0, bool ac = false) {
    std::vector<std::uint8_t> bytes(22 + 128);
    std::copy_n("CP02", 4, bytes.begin());
    bytes[4] = 1;
    body::put32(bytes, 6, 1);
    word16(bytes, 10, 1);
    body::put32(bytes, 14, 128);
    word16(bytes, 22, dc);
    if (ac) {
      word16(bytes, 24, 1);
    }
    return sealed(std::move(bytes));
  }

  /** @brief Build one compressed all-zero block with independent DC/AC padding. */
  std::vector<std::uint8_t> rice_coeff() {
    std::vector<std::uint8_t> bytes(22);
    std::copy_n("CP02", 4, bytes.begin());
    bytes[4] = 1;
    bytes[5] = 1;
    body::put32(bytes, 6, 1);
    word16(bytes, 10, 1);
    body::put32(bytes, 14, 2);
    body::put32(bytes, 18, 4);
    bytes.insert(bytes.end(), {0, 0x80, 0, 0, 0, 0});
    return sealed(std::move(bytes));
  }

  /** @brief Build exact MSB-first AC token cases independent of the decoder. */
  std::vector<std::uint8_t> ac_tokens(const std::string &bits) {
    std::vector<std::uint8_t> bytes(22);
    std::copy_n("CP02", 4, bytes.begin());
    bytes[4] = 1;
    bytes[5] = 1;
    body::put32(bytes, 6, 1);
    word16(bytes, 10, 1);
    body::put32(bytes, 14, 2);
    body::put32(bytes, 18, 3 + (bits.size() + 7) / 8);
    bytes.insert(bytes.end(), {0, 0x80, 0, 0, 0});
    for (std::size_t at = 0; at < bits.size(); at += 8) {
      unsigned value = 0;
      for (unsigned bit = 0; bit < 8; ++bit) {
        value = (value << 1) | (at + bit < bits.size() && bits[at + bit] == '1');
      }
      bytes.push_back(static_cast<std::uint8_t>(value));
    }
    return sealed(std::move(bytes));
  }

  /** @brief Build a single2x2 key or ordinary P frame with no display patches. */
  std::vector<std::uint8_t> tiny_frame(unsigned id = 0, bool key = true) {
    std::vector<std::uint8_t> inner(46);
    std::copy_n("GM01", 4, inner.begin());
    inner[4] = 1;
    inner[5] = key;
    body::put32(inner, 6, 1);
    body::put32(inner, 10, id);
    body::put32(inner, 14, key ? 0xffffffffU : 0);
    word16(inner, 18, 2);
    word16(inner, 20, 2);
    word16(inner, 26, 1);
    word16(inner, 28, 1);
    body::put32(inner, 30, 1);
    inner.push_back(0);
    const auto cp = raw_coeff();
    for (unsigned p = 0; p < 3; ++p) {
      body::put32(inner, 34 + 4 * p, cp.size());
      inner.insert(inner.end(), cp.begin(), cp.end());
    }
    inner = sealed(std::move(inner));
    body::Planes planes;
    planes[0].assign(4, 128);
    planes[1].assign(1, 128);
    planes[2].assign(1, 128);
    const auto tag = body::canonical_tag(planes, 2, 2);
    std::vector<std::uint8_t> bytes(61);
    std::copy_n("AR03", 4, bytes.begin());
    bytes[4] = 3;
    bytes[5] = key;
    body::put32(bytes, 6, 1);
    body::put32(bytes, 10, id);
    bytes[14] = key ? 255 : 0;
    bytes[15] = key ? 0 : 255;
    body::put32(bytes, 16, key ? 0xffffffffU : 0);
    std::copy(tag.begin(), tag.end(), bytes.begin() + (key ? 36 : 20));
    body::put32(bytes, 52, inner.size());
    bytes.insert(bytes.end(), inner.begin(), inner.end());
    return sealed(std::move(bytes));
  }

  /** @brief Build exact raw or palette HP01 fixtures for a2x2 display region. */
  std::vector<std::uint8_t> patch_packet(bool row = false, unsigned mode = 0) {
    std::vector<std::uint8_t> bytes(24);
    std::copy_n(row ? "HR01" : "HP01", 4, bytes.begin());
    bytes[4] = 1;
    bytes[5] = mode;
    word16(bytes, 10, 2);
    word16(bytes, 12, 2);
    body::put32(bytes, 16, 4);
    std::vector<std::uint8_t> payload;
    if (mode == 0) {
      payload = {0, 0, 255, 255, 0, 0, 255, 255};
    } else if (!row) {
      word16(bytes, 14, 2);
      bytes.insert(bytes.end(), {0, 0, 255, 255});
      payload = {0x50};
    } else if (mode == 1) {
      payload = {5, 0, 1, 0, 0, 255, 255, 5, 0, 1, 0, 0, 255, 255};
    } else {
      word16(bytes, 14, 2);
      bytes.insert(bytes.end(), {0, 0, 255, 255});
      payload = {3, 0, 1, 0, 1, 3, 0, 1, 0, 1};
    }
    body::put32(bytes, 20, payload.size());
    bytes.insert(bytes.end(), payload.begin(), payload.end());
    return sealed(std::move(bytes));
  }

  /** @brief Independently pack every palette symbol into MSB-first HP01 indices. */
  std::vector<std::uint8_t> palette_patch(unsigned mode, unsigned colors, unsigned width, unsigned height) {
    const unsigned pixels = width * height, length = (pixels * mode + 7) / 8;
    std::vector<std::uint8_t> bytes(24 + 2 * colors + length);
    std::copy_n("HP01", 4, bytes.begin());
    bytes[4] = 1;
    bytes[5] = mode;
    word16(bytes, 10, width);
    word16(bytes, 12, height);
    word16(bytes, 14, colors);
    body::put32(bytes, 16, pixels);
    body::put32(bytes, 20, length);
    for (unsigned i = 0; i < colors; ++i) {
      word16(bytes, 24 + 2 * i, 0x1000 + 61 * i);
    }
    for (unsigned i = 0; i < pixels; ++i) {
      const auto bit = i * mode;
      bytes[24 + 2 * colors + bit / 8] |= static_cast<std::uint8_t>((i % colors) << (8 - mode - bit % 8));
    }
    return sealed(std::move(bytes));
  }
}  // namespace

TEST(GamebubV20Body, PrimitiveBitsAndEntropyValidateCanonicalBoundaries) {
  namespace b = gamebub::v20::body;
  EXPECT_EQ(b::zigzag()[1], 1U);
  EXPECT_EQ(b::zigzag()[2], 8U);
  EXPECT_EQ(b::zigzag()[63], 63U);
  EXPECT_EQ(b::unmap(1), -1);
  EXPECT_EQ(b::unmap(2), 1);
  EXPECT_THROW(b::u16({}, 0), std::invalid_argument);
  EXPECT_THROW(b::u32({}, 0), std::invalid_argument);
  EXPECT_THROW(b::tag_at({}, 0), std::invalid_argument);
  EXPECT_THROW(b::geometry(3, 2), std::invalid_argument);
  EXPECT_THROW(b::geometry(2048, 2048), std::invalid_argument);
  EXPECT_NO_THROW(b::geometry(2, 2));
  std::array<std::uint8_t, 1> bits {0x80};
  b::Bits reader(bits);
  EXPECT_EQ(reader.get(1), 1U);
  reader.finish();
  EXPECT_THROW(reader.get(1), std::invalid_argument);
  b::Bits extra(bits);
  EXPECT_THROW(extra.finish(), std::invalid_argument);
  std::array<std::uint8_t, 4> noncanonical {};
  b::Bits escape(noncanonical);
  EXPECT_THROW(escape.rice(0, 12), std::invalid_argument);
  const auto zero = b::cp02(rice_coeff(), 1, 1);
  EXPECT_EQ(zero[0], gamebub::v20::block_t {});
  auto bad = rice_coeff();
  bad[22] = 14;
  reseal(bad);
  EXPECT_THROW(b::cp02(bad, 1, 1), std::invalid_argument);
  EXPECT_THROW(b::cp02(raw_coeff(), 0, 1), std::invalid_argument);
  EXPECT_THROW(b::cp02(raw_coeff(), 1, 2), std::invalid_argument);
  EXPECT_THROW(b::cp02(raw_coeff(2049), 1, 1), std::invalid_argument);
  bad = raw_coeff();
  bad.back() ^= 1;
  EXPECT_THROW(b::cp02(bad, 1, 1), std::invalid_argument);
  for (const auto &[bits, target] : std::array<std::pair<std::string, unsigned>, 4> {{{"100000100", 1}, {"01100000100", 17}, {"0101100000100", 33}, {"0101011111001", 63}}}) {
    const auto blocks = b::cp02(ac_tokens(bits), 1, 1);
    EXPECT_EQ(blocks[0][b::zigzag()[target]], 1) << target;
  }
  EXPECT_THROW(b::cp02(ac_tokens("01010101"), 1, 1), std::invalid_argument);
  EXPECT_THROW(b::cp02(ac_tokens("01010111111"), 1, 1), std::invalid_argument);
}

TEST(GamebubV20Body, SplitPlanesPreserveZeroDcAndFullClassifications) {
  namespace b = gamebub::v20::body;
  auto dense = raw_coeff(2, true);
  std::vector<std::uint8_t> bytes(21);
  std::copy_n("SP01", 4, bytes.begin());
  b::put32(bytes, 5, 1);
  b::put32(bytes, 17, dense.size());
  bytes.insert(bytes.end(), dense.begin(), dense.end());
  EXPECT_EQ(b::sp01(bytes, 1, 1)[0][0], 2);
  std::vector<std::uint8_t> split(21);
  std::copy_n("SP01", 4, split.begin());
  split[4] = 1;
  b::put32(split, 5, 3);
  b::put32(split, 9, 1);
  b::put32(split, 13, 1);
  b::put32(split, 17, dense.size());
  split.insert(split.end(), {0x18, 0xff, 0xff});
  split.insert(split.end(), dense.begin(), dense.end());
  auto output = b::sp01(split, 3, 1);
  EXPECT_EQ(output[0], gamebub::v20::block_t {});
  EXPECT_EQ(output[1][0], -1);
  EXPECT_EQ(output[2][1], 1);
  split[21] = 0xff;
  EXPECT_THROW(b::sp01(split, 3, 1), std::invalid_argument);
  EXPECT_THROW(b::sp01({}, 1, 1), std::invalid_argument);
  EXPECT_THROW(b::sp01(bytes, 0, 0), std::invalid_argument);
}

TEST(GamebubV20Body, LosslessPatchModesAndCanonicalPaletteFailures) {
  namespace b = gamebub::v20::body;
  const std::vector<std::uint16_t> expected {0, 65535, 0, 65535};
  for (auto mode : {0U, 1U}) {
    EXPECT_EQ(b::decode_patch(patch_packet(false, mode), 2, 2).words, expected);
  }
  for (auto mode : {0U, 1U, 2U}) {
    EXPECT_EQ(b::decode_patch(patch_packet(true, mode), 2, 2).words, expected);
  }
  auto bad = patch_packet();
  bad.back() ^= 1;
  EXPECT_THROW(b::decode_patch(bad, 2, 2), std::invalid_argument);
  bad = patch_packet(false, 1);
  bad[28] = 0x00;
  reseal(bad);
  EXPECT_THROW(b::decode_patch(bad, 2, 2), std::invalid_argument);
  bad = patch_packet(true, 1);
  bad[24] = 255;
  reseal(bad);
  EXPECT_THROW(b::decode_patch(bad, 2, 2), std::invalid_argument);
  bad = patch_packet(true, 2);
  bad[31] = 2;
  reseal(bad);
  EXPECT_THROW(b::decode_patch(bad, 2, 2), std::invalid_argument);
  EXPECT_THROW(b::decode_patch({}, 2, 2), std::invalid_argument);
  EXPECT_THROW(b::decode_patch(patch_packet(), 2, 0), std::invalid_argument);
}

TEST(GamebubV20Body, AllHpPaletteWidthsUseEverySymbolAndRejectNoncanonicalPadding) {
  namespace b = gamebub::v20::body;

  struct PaletteCase {
    unsigned mode, colors, width, height;
  };

  const std::array<PaletteCase, 6> cases {{{2, 3, 3, 3}, {2, 4, 3, 3}, {4, 5, 3, 3}, {4, 16, 5, 5}, {8, 17, 5, 5}, {8, 256, 16, 16}}};
  for (const auto &sample : cases) {
    const auto bytes = palette_patch(sample.mode, sample.colors, sample.width, sample.height);
    const unsigned canvas_width = (sample.width + 1) & ~1U, canvas_height = (sample.height + 1) & ~1U;
    const auto decoded = b::decode_patch(bytes, canvas_width, canvas_height);
    ASSERT_EQ(decoded.words.size(), sample.width * sample.height);
    for (unsigned i = 0; i < decoded.words.size(); ++i) {
      EXPECT_EQ(decoded.words[i], 0x1000 + 61 * (i % sample.colors)) << sample.mode << ':' << i;
    }
    // A complete extra payload byte is invalid even when its value is zero.
    auto trailing = bytes;
    trailing.insert(trailing.end() - 4, 0);
    b::put32(trailing, 20, b::u32(bytes, 20) + 1);
    reseal(trailing);
    EXPECT_THROW(b::decode_patch(trailing, canvas_width, canvas_height), std::invalid_argument);
    // Every palette entry is required to be used by at least one pixel.
    auto unused = bytes;
    std::fill(unused.begin() + 24 + 2 * sample.colors, unused.end() - 4, 0);
    reseal(unused);
    EXPECT_THROW(b::decode_patch(unused, canvas_width, canvas_height), std::invalid_argument);
    const auto padding = (8 - (sample.width * sample.height * sample.mode) % 8) % 8;
    if (padding) {
      auto bad = bytes;
      bad[bad.size() - 5] |= 1;
      reseal(bad);
      EXPECT_THROW(b::decode_patch(bad, canvas_width, canvas_height), std::invalid_argument);
    }
  }
}

TEST(GamebubV20Body, KeyPredictorReplayAndFailedPublicationAreAtomic) {
  namespace b = gamebub::v20::body;
  b::State state;
  b::Frame output;
  std::string error;
  auto key = tiny_frame();
  ASSERT_TRUE(b::decode(key, state, output, error)) << error;
  EXPECT_EQ(state.last_frame, 0);
  ASSERT_TRUE(state.banks[0]);
  EXPECT_EQ(output.display565, std::vector<std::uint16_t>(4, 0x8410));
  EXPECT_EQ(output.feedback[18], 0);
  EXPECT_EQ(output.feedback[4], 3);
  const auto snapshot = state;
  const auto old_output = output;
  EXPECT_FALSE(b::decode(key, state, output, error));
  EXPECT_EQ(state, snapshot);
  EXPECT_EQ(output, old_output);
  auto next = tiny_frame(1, false);
  ASSERT_TRUE(b::decode(next, state, output, error)) << error;
  EXPECT_EQ(output.planes, snapshot.banks[0]->planes);
  EXPECT_EQ(output.feedback[18], 255);
  auto bad = tiny_frame(2, false);
  bad[20] ^= 1;
  reseal(bad);
  const auto before = state;
  const auto before_output = output;
  EXPECT_FALSE(b::decode(bad, state, output, error));
  EXPECT_EQ(state, before);
  EXPECT_EQ(output, before_output);
  bad = tiny_frame(3, true);
  bad[36] ^= 1;
  reseal(bad);
  EXPECT_FALSE(b::decode(bad, state, output, error));
  EXPECT_EQ(state, before);
  EXPECT_EQ(output, before_output);
  state.readers[0] = 1;
  EXPECT_FALSE(b::decode(tiny_frame(4, true), state, output, error));
  state = before;
  state.epoch = 2;
  EXPECT_FALSE(b::decode(tiny_frame(5, true), state, output, error));
  state = before;
  state.width = 4;
  EXPECT_FALSE(b::decode(tiny_frame(6, true), state, output, error));
}

TEST(GamebubV20Body, PrivatePatchPublicationAndEveryTruncationPreserveBaseState) {
  namespace b = gamebub::v20::body;
  auto key = tiny_frame();
  key.resize(key.size() - 4);
  const auto patch = patch_packet();
  key[56] = 1;
  b::put32(key, 57, 4 + patch.size());
  const auto start = key.size();
  key.resize(start + 4);
  b::put32(key, start, patch.size());
  key.insert(key.end(), patch.begin(), patch.end());
  key = sealed(std::move(key));
  b::State state;
  b::Frame output;
  std::string error;
  ASSERT_TRUE(b::decode(key, state, output, error)) << error;
  EXPECT_EQ(output.display565, (std::vector<std::uint16_t> {0, 65535, 0, 65535}));
  ASSERT_TRUE(state.banks[0]);
  EXPECT_EQ(state.banks[0]->planes, output.planes);
  EXPECT_EQ(state.banks[0]->tag, b::canonical_tag(output.planes, 2, 2));
  for (std::size_t length = 0; length < key.size(); ++length) {
    b::State fresh;
    b::Frame sentinel;
    sentinel.id = 123;
    const auto before = sentinel;
    EXPECT_FALSE(b::decode(std::span(key).first(length), fresh, sentinel, error));
    EXPECT_EQ(fresh, b::State {});
    EXPECT_EQ(sentinel, before);
  }
  auto overlap = key;
  overlap.resize(overlap.size() - 4);
  overlap[56] = 2;
  b::put32(overlap, 57, 2 * (4 + patch.size()));
  const auto next = overlap.size();
  overlap.resize(next + 4);
  b::put32(overlap, next, patch.size());
  overlap.insert(overlap.end(), patch.begin(), patch.end());
  overlap = sealed(std::move(overlap));
  b::State fresh;
  const auto before = output;
  EXPECT_FALSE(b::decode(overlap, fresh, output, error));
  EXPECT_EQ(fresh, b::State {});
  EXPECT_EQ(output, before);
}

TEST(GamebubV20Body, RepairedOuterCrcCannotPublishCorruptInnerOrPredictor) {
  namespace b = gamebub::v20::body;
  const auto key = tiny_frame();
  for (auto at : {61U, 65U, 66U, 67U, 71U, 75U, 79U, 81U, 83U, 85U, 87U, 89U, 91U, 95U, 99U, 103U, 107U, 108U, 112U, 122U}) {
    auto bad = key;
    bad[at] ^= at == 107 ? 0xc0 : 0x80;
    const auto inner_bytes = b::u32(bad, 52);
    b::put32(bad, 61 + inner_bytes - 4, gamebub::v20::crc32(std::span(bad).subspan(61, inner_bytes - 4)));
    reseal(bad);
    b::State state;
    b::Frame output;
    output.id = 17;
    const auto before = output;
    std::string error;
    EXPECT_FALSE(b::decode(bad, state, output, error)) << at;
    EXPECT_EQ(state, b::State {});
    EXPECT_EQ(output, before);
  }
  b::State state;
  b::Frame output;
  std::string error;
  ASSERT_TRUE(b::decode(key, state, output, error));
  state.banks[0]->planes[0][0] = 256;
  const auto before = state;
  const auto before_output = output;
  EXPECT_FALSE(b::decode(tiny_frame(1, false), state, output, error));
  EXPECT_EQ(state, before);
  EXPECT_EQ(output, before_output);
  state.banks[0]->planes[0][0] = 128;
  state.banks[0]->planes[1].clear();
  EXPECT_FALSE(b::decode(tiny_frame(2, true), state, output, error));
}
