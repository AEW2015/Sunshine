/**
 * @file tools/gamebub/native/body_decoder.h
 * @brief Bounded offline AR03 body decoder; no endpoint, scheduling or throughput claim.
 */
#pragma once

// standard includes
#include <algorithm>
#include <bit>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

// lib includes
#include <openssl/sha.h>

// local includes
#include "v20.h"

namespace gamebub::v20::body {
  /** @brief Canonical truncated SHA256 reference identity. */
  using Tag = std::array<std::uint8_t, 16>;
  /** @brief Canonical row-major Y, Cb and Cr signed16 storage, samples0..255. */
  using Planes = std::array<std::vector<std::int16_t>, 3>;

  /** @brief One complete immutable reconstructed reference bank. */
  struct Bank {
    std::uint32_t id;  ///< Confirmed frame identity.
    Tag tag;  ///< Confirmed canonical reference tag.
    Planes planes;  ///< Reconstructed predictor samples, never display overlays.
    /** @brief Compare complete bank identity and samples for atomicity regressions. */
    bool operator==(const Bank &) const = default;
  };

  /** @brief Serialized offline receiver state and externally held bank readers. */
  struct State {
    std::uint32_t epoch = 1;  ///< Fixed session identity, excluding UINT32_MAX.
    std::int64_t last_frame = -1;  ///< Last committed frame, negative before first frame.
    unsigned width = 0, height = 0;  ///< Fixed geometry after publication.
    std::array<std::optional<Bank>, 2> banks;  ///< Independent key/recent reference banks.
    std::array<std::size_t, 2> readers {};  ///< External readers that prohibit destination writes.
    /** @brief Compare complete publication state, including external readers. */
    bool operator==(const State &) const = default;
  };

  /** @brief Fully validated display-only RGB565 rectangle. */
  struct Patch {
    unsigned x, y, width, height;  ///< Rectangle in coded canvas coordinates.
    std::vector<std::uint16_t> words;  ///< Original RGB565 row-major words.
  };

  /** @brief One atomically decoded frame and exact AF03 publication response. */
  struct Frame {
    unsigned width = 0, height = 0;  ///< Coded output geometry.
    std::uint32_t id = 0;  ///< Accepted outer frame identity.
    Planes planes;  ///< Base reconstruction excluding patches.
    std::vector<std::uint16_t> display565;  ///< RGB565 after exact display-only overlays.
    std::array<std::uint8_t, 43> feedback {};  ///< AF03 ACK, including complete CRC.
    /** @brief Compare every published output word and feedback byte. */
    bool operator==(const Frame &) const = default;
  };

  /** @brief Reject malformed input before private output can be published. */
  inline void require(bool condition, const char *message) {
    if (!condition) {
      throw std::invalid_argument(message);
    }
  }

  /** @brief Read an explicitly bounded little-endian16 word. */
  inline std::uint16_t u16(std::span<const std::uint8_t> bytes, std::size_t offset) {
    require(offset <= bytes.size() && bytes.size() - offset >= 2, "short uint16");
    return static_cast<std::uint16_t>(bytes[offset] | (unsigned(bytes[offset + 1]) << 8));
  }

  /** @brief Read an explicitly bounded little-endian32 word. */
  inline std::uint32_t u32(std::span<const std::uint8_t> bytes, std::size_t offset) {
    require(offset <= bytes.size() && bytes.size() - offset >= 4, "short uint32");
    return le32(bytes, offset);
  }

  /** @brief Store a bounded little-endian word into private feedback storage. */
  inline void put32(std::span<std::uint8_t> bytes, std::size_t offset, std::uint32_t value) {
    require(offset <= bytes.size() && bytes.size() - offset >= 4, "short output uint32");
    for (unsigned i = 0; i < 4; ++i) {
      bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
    }
  }

  /** @brief Match a four-byte magic without unaligned/native-layout casts. */
  inline bool magic(std::span<const std::uint8_t> bytes, std::string_view name) {
    return bytes.size() >= 4 && std::equal(name.begin(), name.end(), bytes.begin());
  }

  /** @brief Validate a complete packet's final IEEE CRC32 before payload parsing. */
  inline void check_crc(std::span<const std::uint8_t> bytes) {
    require(bytes.size() >= 4 && crc32(bytes.first(bytes.size() - 4)) == u32(bytes, bytes.size() - 4), "CRC mismatch");
  }

  /** @brief Check the frozen even geometry and allocation domain. */
  inline void geometry(unsigned w, unsigned h) {
    require(w >= 2 && h >= 2 && w <= 2048 && h <= 2048 && !(w & 1) && !(h & 1) && std::uint64_t(w) * h <= 720 * 480, "geometry domain");
  }

  /** @brief Read a canonical16-byte identity from a checked span. */
  inline Tag tag_at(std::span<const std::uint8_t> bytes, std::size_t offset) {
    require(offset <= bytes.size() && bytes.size() - offset >= 16, "short reference tag");
    Tag result;
    std::copy_n(bytes.begin() + offset, 16, result.begin());
    return result;
  }

  /**
   * @brief Hash canonical little-endian dimensions and Y/Cb/Cr signed16 words.
   * @param planes Exactly shaped predictor samples with values0..255.
   * @param w Coded width.
   * @param h Coded height.
   * @return First16 SHA256 bytes, excluding all RGB565 display overlays.
   */
  inline Tag canonical_tag(const Planes &planes, unsigned w, unsigned h) {
    geometry(w, h);
    std::vector<std::uint8_t> bytes;
    bytes.reserve(4 + 3 * w * h);
    bytes.push_back(static_cast<std::uint8_t>(w));
    bytes.push_back(static_cast<std::uint8_t>(w >> 8));
    bytes.push_back(static_cast<std::uint8_t>(h));
    bytes.push_back(static_cast<std::uint8_t>(h >> 8));
    for (unsigned p = 0; p < 3; ++p) {
      require(planes[p].size() == std::size_t(w) * h / (p ? 4 : 1), "bank plane length");
      for (auto value : planes[p]) {
        require(value >= 0 && value <= 255, "bank sample domain");
        bytes.push_back(static_cast<std::uint8_t>(value));
        bytes.push_back(0);
      }
    }
    std::array<unsigned char, SHA256_DIGEST_LENGTH> digest;
    require(SHA256(bytes.data(), bytes.size(), digest.data()) != nullptr, "SHA256 unavailable");
    Tag result;
    std::copy_n(digest.begin(), 16, result.begin());
    return result;
  }

  /** @brief Bounded MSB-first bit reader with canonical Rice escape/padding checks. */
  class Bits {
    std::span<const std::uint8_t> bytes_;  ///< Immutable compressed bytes.
    std::size_t position_ = 0;  ///< Consumed bits; bounded by actual byte count.

  public:
    /** @brief Bind only the exact DC or AC section, not following stream bytes. */
    explicit Bits(std::span<const std::uint8_t> bytes):
        bytes_(bytes) {}

    /** @brief Read0..32bits without implicit zero extension beyond the packet. */
    std::uint32_t get(unsigned n) {
      require(n <= 32 && position_ + n <= bytes_.size() * 8, "truncated coefficient bits");
      std::uint32_t value = 0;
      for (unsigned i = 0; i < n; ++i, ++position_) {
        value = (value << 1) | ((bytes_[position_ / 8] >> (7 - position_ % 8)) & 1);
      }
      return value;
    }

    /** @brief Decode one bounded unary/Rice value, rejecting noncanonical escapes. */
    std::uint32_t rice(unsigned k, unsigned escape) {
      for (unsigned q = 0; q < 15; ++q) {
        if (get(1)) {
          return (q << k) | get(k);
        }
      }
      const auto value = get(escape);
      require((value >> k) >= 15, "noncanonical Rice escape");
      return value;
    }

    /** @brief Require fewer than8 remaining zero padding bits. */
    void finish() {
      const auto n = bytes_.size() * 8 - position_;
      require(n < 8 && get(static_cast<unsigned>(n)) == 0, "extra coefficient padding");
    }
  };

  /** @brief Decode signed zigzag magnitude without implementation-defined shifts. */
  inline std::int32_t unmap(std::uint32_t value) {
    return value & 1 ? -static_cast<std::int32_t>((value + 1) / 2) : static_cast<std::int32_t>(value / 2);
  }

  /** @brief Frozen block-raster zigzag traversal used by CP02 AC tokens. */
  inline std::array<unsigned, 64> zigzag() {
    std::array<unsigned, 64> result {};
    unsigned n = 0;
    for (int sum = 0; sum <= 14; ++sum) {
      if (sum & 1) {
        for (int row = 0; row < 8; ++row) {
          if (sum - row >= 0 && sum - row < 8) {
            result[n++] = row * 8 + sum - row;
          }
        }
      } else {
        for (int row = 7; row >= 0; --row) {
          if (sum - row >= 0 && sum - row < 8) {
            result[n++] = row * 8 + sum - row;
          }
        }
      }
    }
    return result;
  }

  /** @brief Decode bounded raw or independently padded DC/AC CP02 block coefficients. */
  inline std::vector<block_t> cp02(std::span<const std::uint8_t> bytes, unsigned blocks, unsigned blocks_w) {
    require(blocks && blocks <= 65536 && blocks_w && blocks_w <= 256 && blocks % blocks_w == 0, "CP02 geometry");
    require(bytes.size() >= 26 && bytes.size() <= 128ULL * blocks + 26, "CP02 byte bound");
    require(magic(bytes, "CP02") && bytes[4] == 1 && bytes[5] <= 1 && u32(bytes, 6) == blocks && u16(bytes, 10) == blocks_w && u16(bytes, 12) == 0, "CP02 header");
    const auto ndc = u32(bytes, 14), nac = u32(bytes, 18);
    require(26ULL + ndc + nac == bytes.size(), "CP02 lengths");
    check_crc(bytes);
    std::vector<block_t> result(blocks);
    if (bytes[5] == 0) {
      require(ndc == 128ULL * blocks && nac == 0, "CP02 raw lengths");
      for (unsigned i = 0; i < blocks; ++i) {
        for (unsigned j = 0; j < 64; ++j) {
          const auto value = std::bit_cast<std::int16_t>(u16(bytes, 22 + i * 128 + j * 2));
          require(value >= -2048 && value <= 2048, "CP02 raw coefficient");
          result[i][j] = value;
        }
      }
      return result;
    }
    require(ndc >= 1 && nac >= 3, "CP02 Rice section length");
    const auto dcdata = bytes.subspan(22, ndc), acdata = bytes.subspan(22 + ndc, nac);
    require(dcdata[0] <= 13 && acdata[0] <= 11 && acdata[1] <= 11 && acdata[2] <= 11, "CP02 Rice parameters");
    Bits dc(dcdata.subspan(1)), ac(acdata.subspan(3));
    std::int32_t previous = 0;
    const auto order = zigzag();
    for (unsigned i = 0; i < blocks; ++i) {
      if (i % blocks_w == 0) {
        previous = 0;
      }
      const auto value = previous + unmap(dc.rice(dcdata[0], 14));
      require(value >= -2048 && value <= 2048, "CP02 DC coefficient");
      result[i][0] = previous = value;
      unsigned pos = 1;
      while (pos < 64) {
        const auto token = ac.get(2);
        if (token == 0) {
          break;
        }
        if (token == 1) {
          require(pos + 16 <= 64, "CP02 zero run");
          pos += 16;
          continue;
        }
        const auto target = pos + ((token & 1) << 3) + ac.get(3);
        require(target < 64, "CP02 AC run");
        const auto band = target <= 5 ? 0 : target <= 20 ? 1 :
                                                           2;
        const auto coefficient = unmap(ac.rice(acdata[band], 12) + 1);
        require(coefficient && coefficient >= -2048 && coefficient <= 2048, "CP02 AC coefficient");
        result[i][order[target]] = coefficient;
        pos = target + 1;
      }
    }
    dc.finish();
    ac.finish();
    return result;
  }

  /** @brief Decode SR01 dense or zero/DC/full split plane without implicit block fill. */
  inline std::vector<block_t> sp01(std::span<const std::uint8_t> bytes, unsigned n, unsigned bw) {
    require(n && n <= 65536 && bw && bw <= 256 && n % bw == 0, "SP01 geometry");
    require(bytes.size() >= 21 && magic(bytes, "SP01") && bytes[4] <= 1 && u32(bytes, 5) == n, "SP01 header");
    const auto nmap = u32(bytes, 9), ndc = u32(bytes, 13), nfull = u32(bytes, 17);
    if (bytes[4] == 0) {
      require(!nmap && !ndc && bytes.size() == 21ULL + nfull, "SP01 dense length");
      return cp02(bytes.subspan(21), n, bw);
    }
    require(nmap == (n + 3) / 4 && ndc <= n && bytes.size() == 21ULL + nmap + 2ULL * ndc + nfull, "SP01 split length");
    const auto modes = bytes.subspan(21, nmap);
    const auto mode = [&](unsigned i) {
      return (modes[i / 4] >> (6 - 2 * (i % 4))) & 3;
    };
    unsigned full_count = 0, dc_count = 0;
    for (unsigned i = 0; i < nmap * 4; ++i) {
      const auto value = mode(i);
      require(value <= 2 && (i < n || value == 0), "SP01 modes");
      if (i < n) {
        full_count += value == 2;
        dc_count += value == 1;
      }
    }
    require(dc_count == ndc && bool(nfull) == bool(full_count), "SP01 count agreement");
    std::vector<block_t> full;
    if (nfull) {
      full = cp02(bytes.subspan(21 + nmap + 2 * ndc), full_count, 1);
    }
    std::vector<block_t> result(n);
    unsigned di = 0, fi = 0;
    for (unsigned i = 0; i < n; ++i) {
      if (mode(i) == 1) {
        const auto value = std::bit_cast<std::int16_t>(u16(bytes, 21 + nmap + 2 * di++));
        require(value && value >= -2048 && value <= 2048, "SP01 DC value");
        result[i][0] = value;
      } else if (mode(i) == 2) {
        require(std::any_of(full[fi].begin() + 1, full[fi].end(), [](auto value) {
                  return value != 0;
                }),
                "SP01 full without AC");
        result[i] = full[fi++];
      }
    }
    return result;
  }

  /** @brief Decode one exact HP01/HR01 patch, rejecting unused palette symbols and overlap-independent errors. */
  inline Patch decode_patch(std::span<const std::uint8_t> bytes, unsigned width, unsigned height) {
    geometry(width, height);
    require(bytes.size() >= 28 && (magic(bytes, "HP01") || magic(bytes, "HR01")) && bytes[4] == 1, "patch header");
    const bool row = magic(bytes, "HR01");
    const auto mode = bytes[5];
    Patch patch {u16(bytes, 6), u16(bytes, 8), u16(bytes, 10), u16(bytes, 12), {}};
    const auto colors = u16(bytes, 14);
    const auto pixels = u32(bytes, 16), length = u32(bytes, 20);
    require(patch.width && patch.height && patch.x + patch.width <= width && patch.y + patch.height <= height && pixels == patch.width * patch.height, "patch geometry");
    require(colors <= std::min(256U, pixels) && bytes.size() == 28ULL + 2 * colors + length, "patch exact lengths");
    check_crc(bytes);
    const auto payload = bytes.subspan(24 + 2 * colors, length);
    std::vector<std::uint16_t> palette(colors);
    for (unsigned i = 0; i < colors; ++i) {
      palette[i] = u16(bytes, 24 + 2 * i);
      if (i) {
        require(palette[i] > palette[i - 1], "patch palette order");
      }
    }
    patch.words.reserve(pixels);
    if (!mode) {
      require(!colors && length == pixels * 2, "raw patch length");
      for (unsigned i = 0; i < pixels; ++i) {
        patch.words.push_back(u16(payload, 2 * i));
      }
      return patch;
    }
    std::vector<bool> used(colors);
    const auto append = [&](unsigned value, bool indexed) {
      if (indexed) {
        require(value < colors, "patch index range");
        used[value] = true;
        patch.words.push_back(palette[value]);
      } else {
        patch.words.push_back(static_cast<std::uint16_t>(value));
      }
    };
    if (!row) {
      const unsigned canonical_mode = colors <= 2 ? 1 : colors <= 4 ? 2 :
                                                      colors <= 16  ? 4 :
                                                                      8;
      require(colors && (mode == 1 || mode == 2 || mode == 4 || mode == 8) && mode == canonical_mode && length == (pixels * mode + 7) / 8, "HP01 indexed geometry");
      Bits bits(payload);
      for (unsigned i = 0; i < pixels; ++i) {
        append(bits.get(mode), true);
      }
      bits.finish();
    } else {
      require((mode == 1 && colors == 0) || (mode == 2 && colors), "HR01 mode/palette");
      require(length <= patch.height * (2 + 3 * patch.width), "HR01 payload bound");
      std::size_t cursor = 0;
      for (unsigned y = 0; y < patch.height; ++y) {
        const auto row_bytes = u16(payload, cursor);
        cursor += 2;
        require(row_bytes && row_bytes <= 3 * patch.width && row_bytes <= payload.size() - cursor, "HR01 row length");
        const auto end = cursor + row_bytes;
        unsigned output = 0;
        while (cursor < end) {
          const auto token = payload[cursor++];
          const unsigned count = (token & 127) + 1, unit = mode == 2 ? 1 : 2;
          const auto need = (token & 128 ? 1 : count) * unit;
          require(output + count <= patch.width && need <= end - cursor, "HR01 token bound");
          for (unsigned i = 0; i < count; ++i) {
            const auto at = cursor + (token & 128 ? 0 : i * unit);
            append(unit == 1 ? payload[at] : u16(payload, at), unit == 1);
          }
          cursor += need;
          output += count;
        }
        require(output == patch.width, "HR01 output width");
      }
      require(cursor == payload.size(), "HR01 trailing bytes");
    }
    require(std::all_of(used.begin(), used.end(), [](bool value) {
              return value;
            }),
            "unused patch palette");
    return patch;
  }

  /** @brief Integer floor division by256 for bounded signed color sums. */
  inline int floor256(int value) {
    return value >= 0 ? value / 256 : -((-value + 255) / 256);
  }

  /** @brief Render frozen bilinear co-sited chroma and full-range integer RGB to RGB565. */
  inline std::vector<std::uint16_t> render565(const Planes &planes, unsigned w, unsigned h) {
    const auto chroma = [&](unsigned p, unsigned x, unsigned y) {
      const unsigned cw = w / 2, ch = h / 2, xx = x / 2, yy = y / 2, right = std::min(xx + 1, cw - 1), below = std::min(yy + 1, ch - 1);
      const auto horizontal = [&](unsigned row) {
        const int a = planes[p][row * cw + xx];
        return x & 1 ? (a + planes[p][row * cw + right] + 1) / 2 : a;
      };
      return (y & 1 ? (horizontal(yy) + horizontal(below) + 1) / 2 : horizontal(yy)) - 128;
    };
    std::vector<std::uint16_t> words(std::size_t(w) * h);
    for (unsigned y = 0; y < h; ++y) {
      for (unsigned x = 0; x < w; ++x) {
        const int value = planes[0][y * w + x], cb = chroma(1, x, y), cr = chroma(2, x, y);
        const int r = std::clamp(value + floor256(359 * cr + 128), 0, 255), g = std::clamp(value - floor256(88 * cb + 183 * cr + 128), 0, 255), b = std::clamp(value + floor256(454 * cb + 128), 0, 255);
        words[y * w + x] = static_cast<std::uint16_t>(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
      }
    }
    return words;
  }

  /** @brief Frozen luma quantizer matrix before map-dependent scaling. */
  inline constexpr std::array<int, 64> qy {16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99};
  /** @brief Frozen chroma quantizer matrix before map-dependent scaling. */
  inline constexpr std::array<int, 64> qc {
    17,
    18,
    24,
    47,
    99,
    99,
    99,
    99,
    18,
    21,
    26,
    66,
    99,
    99,
    99,
    99,
    24,
    26,
    56,
    99,
    99,
    99,
    99,
    99,
    47,
    66,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99,
    99
  };

  /**
   * @brief Decode one complete AR03 transaction using exact precondition banks.
   * @param packet Outer frame including all nested CRCs and patch bytes.
   * @param state Serialized receiver state; unchanged on any rejection.
   * @param frame Complete YUV/display/feedback output, unchanged on rejection.
   * @param error Empty on success or diagnostic rejection text.
   * @return True after atomic publication, false without changing state/output.
   */
  inline bool decode(std::span<const std::uint8_t> packet, State &state, Frame &frame, std::string &error) {
    try {
      require(envelope(packet, false).empty(), "AR03 outer envelope");
      const auto flags = packet[5];
      const auto epoch = u32(packet, 6), id = u32(packet, 10), refid = u32(packet, 16);
      const auto refbank = packet[14], dest = packet[15], count = packet[56];
      const auto reftag = tag_at(packet, 20), storedtag = tag_at(packet, 36);
      const bool key = flags == 1, promoted = flags == 2;
      require((flags == 0 || key || promoted) && epoch != 0xffffffffU && epoch == state.epoch && id != 0xffffffffU && std::int64_t(id) > state.last_frame, "AR03 epoch/frame/profile");
      if (key) {
        require(refbank == 255 && refid == 0xffffffffU && reftag == Tag {} && dest == 0 && storedtag != Tag {}, "AR03 key identity");
      } else {
        require(refbank < 2 && refid < id && reftag != Tag {} && (promoted ? dest == 1 && storedtag != Tag {} : dest == 255 && storedtag == Tag {}), "AR03 P identity");
      }
      require(dest == 255 || state.readers[dest] == 0, "AR03 destination read-owned");
      const auto inner = packet.subspan(61, u32(packet, 52));
      require(inner.size() >= 50 && (magic(inner, "GM01") || magic(inner, "SR01")) && inner[4] == 1, "inner profile");
      const bool sr = magic(inner, "SR01");
      require((sr ? inner[5] == 0 || inner[5] == 1 || inner[5] == 2 || inner[5] == 4 : inner[5] <= 1) && bool(inner[5] & 1) == key && u32(inner, 6) == epoch && u32(inner, 10) == id && u32(inner, 14) == refid && !u16(inner, 22) && !u16(inner, 24), "inner identity");
      const auto w = u16(inner, 18), h = u16(inner, 20);
      geometry(w, h);
      require((!state.width && !state.height) || (state.width == w && state.height == h), "fixed geometry");
      for (const auto &bank : state.banks) {
        if (bank) {
          require(bank->id != 0xffffffffU && bank->tag != Tag {} && canonical_tag(bank->planes, w, h) == bank->tag, "invalid existing bank");
        }
      }
      const unsigned mw = (w + 15) / 16, mh = (h + 15) / 16, nmap = u32(inner, 30);
      require(u16(inner, 26) == mw && u16(inner, 28) == mh && nmap == (mw * mh + 3) / 4, "quantizer map geometry");
      const std::array<std::uint32_t, 3> lengths {u32(inner, 34), u32(inner, 38), u32(inner, 42)};
      require(50ULL + nmap + std::uint64_t(lengths[0]) + lengths[1] + lengths[2] == inner.size(), "inner exact lengths");
      check_crc(inner);
      const auto mapped = inner.subspan(46, nmap);
      std::vector<unsigned> scales(mw * mh);
      for (unsigned i = 0; i < nmap * 4; ++i) {
        const auto code = (mapped[i / 4] >> (6 - 2 * (i % 4))) & 3;
        require(code <= 2 && (i < mw * mh || code == 0), "quantizer map code/padding");
        if (i < mw * mh) {
          scales[i] = 8U << code;
        }
      }
      if (!key) {
        require(state.banks[refbank].has_value() && state.banks[refbank]->id == refid && state.banks[refbank]->tag == reftag && canonical_tag(state.banks[refbank]->planes, w, h) == reftag, "missing exact predictor bank");
      }
      Frame output;
      output.width = w;
      output.height = h;
      output.id = id;
      std::size_t position = 46 + nmap;
      for (unsigned p = 0; p < 3; ++p) {
        const unsigned pw = p ? w / 2 : w, ph = p ? h / 2 : h, bw = (pw + 7) / 8, bh = (ph + 7) / 8;
        auto coefficients = sr ? sp01(inner.subspan(position, lengths[p]), bw * bh, bw) : cp02(inner.subspan(position, lengths[p]), bw * bh, bw);
        position += lengths[p];
        output.planes[p].resize(pw * ph);
        for (unsigned by = 0; by < bh; ++by) {
          for (unsigned bx = 0; bx < bw; ++bx) {
            const unsigned scale = scales[(p ? by : by / 2) * mw + (p ? bx : bx / 2)];
            block_t dequantized, residual;
            for (unsigned k = 0; k < 64; ++k) {
              dequantized[k] = coefficients[by * bw + bx][k] * std::clamp(((p ? qc : qy)[k] * int(scale) + 8) / 16, 1, 255);
            }
            require(inverse(dequantized, residual), "inverse operand domain");
            for (unsigned yy = 0; yy < 8 && by * 8 + yy < ph; ++yy) {
              for (unsigned xx = 0; xx < 8 && bx * 8 + xx < pw; ++xx) {
                const auto index = (by * 8 + yy) * pw + bx * 8 + xx;
                const int prediction = key ? 128 : state.banks[refbank]->planes[p][index];
                output.planes[p][index] = static_cast<std::int16_t>(std::clamp(prediction + residual[yy * 8 + xx], 0, 255));
              }
            }
          }
        }
      }
      require(count <= 4, "AR03 patch count");
      auto blob = packet.subspan(61 + inner.size(), u32(packet, 57));
      std::vector<Patch> patches;
      std::size_t cursor = 0;
      for (unsigned i = 0; i < count; ++i) {
        const auto bytes = u32(blob, cursor);
        cursor += 4;
        require(bytes && bytes <= blob.size() - cursor, "patch prefix length");
        auto patch = decode_patch(blob.subspan(cursor, bytes), w, h);
        cursor += bytes;
        for (const auto &prior : patches) {
          require(!(patch.x < prior.x + prior.width && prior.x < patch.x + patch.width && patch.y < prior.y + prior.height && prior.y < patch.y + patch.height), "overlapping patches");
        }
        patches.push_back(std::move(patch));
      }
      require(cursor == blob.size(), "trailing patch bytes");
      if (dest != 255) {
        require(canonical_tag(output.planes, w, h) == storedtag, "reconstructed publication tag");
      }
      output.display565 = render565(output.planes, w, h);
      for (const auto &patch : patches) {
        for (unsigned y = 0; y < patch.height; ++y) {
          std::copy_n(patch.words.begin() + y * patch.width, patch.width, output.display565.begin() + (patch.y + y) * w + patch.x);
        }
      }
      std::copy_n("AF03", 4, output.feedback.begin());
      output.feedback[4] = 3;
      output.feedback[5] = 1;
      put32(output.feedback, 6, epoch);
      put32(output.feedback, 10, id);
      put32(output.feedback, 14, u32(packet, packet.size() - 4));
      output.feedback[18] = dest;
      put32(output.feedback, 19, dest == 255 ? 0xffffffffU : id);
      if (dest != 255) {
        std::copy(storedtag.begin(), storedtag.end(), output.feedback.begin() + 23);
      }
      put32(output.feedback, 39, crc32(std::span(output.feedback).first(39)));
      State next = state;
      if (dest != 255) {
        next.banks[dest] = Bank {id, storedtag, output.planes};
      }
      next.width = w;
      next.height = h;
      next.last_frame = id;
      frame = std::move(output);
      state = std::move(next);
      error.clear();
      return true;
    } catch (const std::exception &failure) {
      error = failure.what();
      return false;
    }
  }
}  // namespace gamebub::v20::body
