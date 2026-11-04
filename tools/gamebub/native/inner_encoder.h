/**
 * @file tools/gamebub/native/inner_encoder.h
 * @brief Offline native GM01 encoder matching the pinned MoonBub integer reference.
 * @note Arithmetic and CP02 decisions are frozen at MoonBub commit
 * 27a4dde6a7e2ea4fab09d892551ef542f05c8965; this is not a negotiated endpoint.
 */
#pragma once

// standard includes
#include <cstdlib>
#include <limits>

// local includes
#include "candidate.h"

namespace gamebub::v20::encoder {
  /** @brief Append a little-endian unsigned word without native-layout casts. */
  inline void append16(std::vector<std::uint8_t> &out, std::uint16_t value) {
    out.push_back(static_cast<std::uint8_t>(value));
    out.push_back(static_cast<std::uint8_t>(value >> 8));
  }

  /** @brief Append a little-endian unsigned double word. */
  inline void append32(std::vector<std::uint8_t> &out, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) {
      out.push_back(static_cast<std::uint8_t>(value >> (8 * i)));
    }
  }

  /** @brief Seal private encoded bytes with their complete IEEE CRC32. */
  inline void seal(std::vector<std::uint8_t> &out) {
    append32(out, crc32(out));
  }

  /**
   * @brief Convert exact RGB8 to clipped integer full-range Y and box-averaged Cb/Cr.
   * @param rgb Exact packed RGB source, never reconstructed from RGB565.
   * @param w Even coded width.
   * @param h Even coded height.
   * @return Signed16 samples with +2 chroma averaging after individual pixel clipping.
   */
  inline body::Planes rgb_to_planes(std::span<const std::uint8_t> rgb, unsigned w, unsigned h) {
    body::geometry(w, h);
    body::require(rgb.size() == std::size_t(w) * h * 3, "original RGB8 geometry");
    body::Planes planes;
    planes[0].resize(w * h);
    planes[1].resize(w * h / 4);
    planes[2].resize(w * h / 4);
    for (unsigned y = 0; y < h; y += 2) {
      for (unsigned x = 0; x < w; x += 2) {
        int cb = 0, cr = 0;
        for (unsigned dy = 0; dy < 2; ++dy) {
          for (unsigned dx = 0; dx < 2; ++dx) {
            const auto pos = std::size_t(y + dy) * w + x + dx;
            const int r = rgb[3 * pos], g = rgb[3 * pos + 1], b = rgb[3 * pos + 2];
            planes[0][pos] = std::clamp(body::floor256(77 * r + 150 * g + 29 * b + 128), 0, 255);
            cb += std::clamp(body::floor256(-43 * r - 85 * g + 128 * b + 128) + 128, 0, 255);
            cr += std::clamp(body::floor256(128 * r - 107 * g - 21 * b + 128) + 128, 0, 255);
          }
        }
        const auto pos = std::size_t(y / 2) * (w / 2) + x / 2;
        planes[1][pos] = (cb + 2) / 4;
        planes[2][pos] = (cr + 2) / 4;
      }
    }
    return planes;
  }

  /**
   * @brief Compute Q14 forward DCT with a separate ties-to-positive-infinity round per pass.
   * @param input One spatial residual block, samples in [-255,255].
   * @return Natural-order signed transform coefficients.
   */
  inline block_t forward(const block_t &input) {
    block_t middle {}, out {};
    for (auto value : input) {
      body::require(value >= -255 && value <= 255, "forward residual domain");
    }
    for (unsigned row = 0; row < 8; ++row) {
      for (unsigned col = 0; col < 8; ++col) {
        std::int64_t sum = 0;
        for (unsigned k = 0; k < 8; ++k) {
          sum += std::int64_t(basis[row][k]) * input[k * 8 + col];
        }
        middle[row * 8 + col] = round_q14(sum);
      }
    }
    for (unsigned row = 0; row < 8; ++row) {
      for (unsigned col = 0; col < 8; ++col) {
        std::int64_t sum = 0;
        for (unsigned k = 0; k < 8; ++k) {
          sum += std::int64_t(middle[row * 8 + k]) * basis[col][k];
        }
        out[row * 8 + col] = round_q14(sum);
      }
    }
    return out;
  }

  /** @brief Map a bounded signed coefficient/delta to its unsigned Rice magnitude. */
  inline unsigned mapped(int value) {
    return value >= 0 ? unsigned(value) * 2 : unsigned(-value) * 2 - 1;
  }

  /** @brief Select the first minimum-cost Rice parameter including bounded escape costs. */
  inline unsigned best_k(std::span<const unsigned> values, unsigned maximum, unsigned escape) {
    unsigned best = 0;
    std::uint64_t best_cost = std::numeric_limits<std::uint64_t>::max();
    for (unsigned k = 0; k <= maximum; ++k) {
      std::uint64_t cost = 0;
      for (auto value : values) {
        cost += (value >> k) < 15 ? (value >> k) + 1 + k : 15 + escape;
      }
      if (cost < best_cost) {
        best_cost = cost;
        best = k;
      }
    }
    return best;
  }

  /** @brief Exact bounded MSB-first bit writer with final zero padding. */
  class Bits {
    std::vector<std::uint8_t> bytes_;  ///< Complete bytes plus at most one zero-padded tail.
    unsigned used_ = 0;  ///< Number of significant bits in the current tail modulo eight.

  public:
    /** @brief Append the low count bits, in most-significant-bit order. */
    void put(unsigned value, unsigned count) {
      body::require(count <= 32, "bit writer width");
      for (unsigned i = count; i > 0; --i) {
        if (!used_) {
          bytes_.push_back(0);
        }
        bytes_.back() |= ((value >> (i - 1)) & 1) << (7 - used_);
        used_ = (used_ + 1) % 8;
      }
    }

    /** @brief Write canonical bounded Rice syntax, with no terminator after an escape. */
    void rice(unsigned value, unsigned k, unsigned escape) {
      body::require(k <= 13 && escape <= 14 && value < (1U << escape), "Rice writer domain");
      const auto quotient = value >> k;
      if (quotient >= 15) {
        put(0, 15);
        put(value, escape);
      } else {
        put(0, quotient);
        put(1, 1);
        put(value, k);
      }
    }

    /** @brief Return the exact zero-padded byte stream. */
    const std::vector<std::uint8_t> &bytes() const {
      return bytes_;
    }
  };

  /** @brief Select the frozen zigzag-position AC entropy band. */
  inline unsigned band(unsigned position) {
    return position <= 5 ? 0 : position <= 20 ? 1 :
                                                2;
  }

  /**
   * @brief Encode actual CP02 bytes with canonical Rice selection and bounded raw fallback.
   * @param coefficients Natural-order int32 blocks constrained to signed wire domain.
   * @param blocks_w Integral row width; the DC predictor resets at every row.
   * @return Complete CP02 header, payload and CRC, byte-identical to the pinned token encoder.
   */
  inline std::vector<std::uint8_t> encode_coefficients(std::span<const block_t> coefficients, unsigned blocks_w) {
    body::require(!coefficients.empty() && coefficients.size() <= 65536 && blocks_w >= 1 && blocks_w <= 256 && coefficients.size() % blocks_w == 0, "coefficient encoder geometry");
    const auto order = body::zigzag();
    std::vector<unsigned> dc;
    std::array<std::vector<unsigned>, 3> ac;
    int previous = 0;
    for (std::size_t i = 0; i < coefficients.size(); ++i) {
      for (auto value : coefficients[i]) {
        body::require(value >= -2048 && value <= 2048, "coefficient encoder domain");
      }
      if (i % blocks_w == 0) {
        previous = 0;
      }
      dc.push_back(mapped(coefficients[i][0] - previous));
      previous = coefficients[i][0];
      for (unsigned pos = 1; pos < 64; ++pos) {
        const int value = coefficients[i][order[pos]];
        if (value) {
          ac[band(pos)].push_back(mapped(value) - 1);
        }
      }
    }
    const auto kd = best_k(dc, 13, 14);
    std::array<unsigned, 3> ks;
    for (unsigned i = 0; i < 3; ++i) {
      ks[i] = best_k(ac[i], 11, 12);
    }
    Bits dcbits, acbits;
    for (auto value : dc) {
      dcbits.rice(value, kd, 14);
    }
    for (const auto &block : coefficients) {
      unsigned position = 1;
      while (position < 64) {
        unsigned target = position;
        while (target < 64 && !block[order[target]]) {
          ++target;
        }
        if (target == 64) {
          acbits.put(0, 2);
          break;
        }
        while (target - position >= 16) {
          acbits.put(1, 2);
          position += 16;
        }
        acbits.put(1, 1);
        acbits.put(target - position, 4);
        acbits.rice(mapped(block[order[target]]) - 1, ks[band(target)], 12);
        position = target + 1;
      }
    }
    std::vector<std::uint8_t> dcdata {static_cast<std::uint8_t>(kd)};
    dcdata.insert(dcdata.end(), dcbits.bytes().begin(), dcbits.bytes().end());
    std::vector<std::uint8_t> acdata(ks.begin(), ks.end());
    acdata.insert(acdata.end(), acbits.bytes().begin(), acbits.bytes().end());
    const bool rice = dcdata.size() + acdata.size() < coefficients.size() * 128;
    if (!rice) {
      dcdata.clear();
      acdata.clear();
      for (const auto &block : coefficients) {
        for (auto value : block) {
          append16(dcdata, static_cast<std::uint16_t>(value));
        }
      }
    }
    std::vector<std::uint8_t> out {'C', 'P', '0', '2', 1, static_cast<std::uint8_t>(rice)};
    append32(out, static_cast<std::uint32_t>(coefficients.size()));
    append16(out, blocks_w);
    append16(out, 0);
    append32(out, static_cast<std::uint32_t>(dcdata.size()));
    append32(out, static_cast<std::uint32_t>(acdata.size()));
    out.insert(out.end(), dcdata.begin(), dcdata.end());
    out.insert(out.end(), acdata.begin(), acdata.end());
    seal(out);
    return out;
  }

  /** @brief Construct the frozen rounded-out macrocell ROI map for one declared candidate. */
  inline std::vector<unsigned> scale_map(candidate::Map map) {
    body::require(std::find(candidate::maps.begin(), candidate::maps.end(), map) != candidate::maps.end(), "undeclared encoder map");
    std::vector<unsigned> scales(45 * 30, map.background);
    for (const auto &rect : candidate::base_regions) {
      for (unsigned y = rect.y / 16; y < (rect.y + rect.height + 15) / 16; ++y) {
        for (unsigned x = rect.x / 16; x < (rect.x + rect.width + 15) / 16; ++x) {
          scales[y * 45 + x] = map.roi;
        }
      }
    }
    return scales;
  }

  /**
   * @brief Encode one complete GM01 candidate from original RGB8 and an exact confirmed bank.
   * @param request Immutable candidate identity, source, reference and declared ROI map.
   * @return Real encoded bytes and canonical reconstructed tag for key/promotion only.
   * @note This offline builder does not open sockets, publish banks or claim a target frame rate.
   */
  inline candidate::BuildResult encode_inner(const candidate::BuildRequest &request) {
    constexpr unsigned w = candidate::width, h = candidate::height;
    constexpr auto no_id = std::numeric_limits<std::uint32_t>::max();
    body::require(request.source && request.source->rgb8().size() == w * h * 3, "encoder requires original RGB8");
    body::require(request.epoch != no_id && request.frame_id != no_id, "encoder session/frame identity");
    body::require(request.key ? (!request.reference && !request.promoted && request.reference_slot == 255 && request.destination_slot == 0) : (request.reference && request.reference_slot < 2 && request.reference->id < request.frame_id && request.destination_slot == (request.promoted ? 1U : 255U)), "encoder reference profile");
    if (request.reference) {
      body::require(body::canonical_tag(request.reference->planes, w, h) == request.reference->tag, "encoder exact reference tag");
    }
    const auto scales = scale_map(request.map);
    const auto source = rgb_to_planes(request.source->rgb8(), w, h);
    body::Planes reconstruction;
    std::array<std::vector<std::uint8_t>, 3> payloads;
    for (unsigned p = 0; p < 3; ++p) {
      const unsigned pw = p ? w / 2 : w, ph = p ? h / 2 : h;
      const unsigned bw = (pw + 7) / 8, bh = (ph + 7) / 8;
      std::vector<block_t> coefficients(bw * bh);
      if (request.key || request.promoted) {
        reconstruction[p].resize(pw * ph);
      }
      for (unsigned by = 0; by < bh; ++by) {
        for (unsigned bx = 0; bx < bw; ++bx) {
          block_t residual;
          for (unsigned y = 0; y < 8; ++y) {
            for (unsigned x = 0; x < 8; ++x) {
              const auto pos = std::size_t(std::min(by * 8 + y, ph - 1)) * pw + std::min(bx * 8 + x, pw - 1);
              residual[y * 8 + x] = source[p][pos] - (request.key ? 128 : request.reference->planes[p][pos]);
            }
          }
          const auto raw = forward(residual);
          auto &quantized = coefficients[by * bw + bx];
          block_t dequantized;
          const auto scale = scales[(p ? by : by / 2) * 45 + (p ? bx : bx / 2)];
          for (unsigned k = 0; k < 64; ++k) {
            const auto q = std::clamp(((p ? body::qc : body::qy)[k] * int(scale) + 8) / 16, 1, 255);
            quantized[k] = (raw[k] >= 0 ? 1 : -1) * ((std::abs(raw[k]) + q / 2) / q);
            body::require(quantized[k] >= -2048 && quantized[k] <= 2048, "quantized encoder coefficient domain");
            dequantized[k] = quantized[k] * q;
          }
          if (request.key || request.promoted) {
            block_t decoded;
            body::require(inverse(dequantized, decoded), "encoder inverse domain");
            for (unsigned y = 0; y < 8 && by * 8 + y < ph; ++y) {
              for (unsigned x = 0; x < 8 && bx * 8 + x < pw; ++x) {
                const auto pos = std::size_t(by * 8 + y) * pw + bx * 8 + x;
                reconstruction[p][pos] = std::clamp(decoded[y * 8 + x] + (request.key ? 128 : request.reference->planes[p][pos]), 0, 255);
              }
            }
          }
        }
      }
      payloads[p] = encode_coefficients(coefficients, bw);
    }
    candidate::BuildResult result;
    auto &out = result.inner;
    out = {'G', 'M', '0', '1', 1, static_cast<std::uint8_t>(request.key)};
    append32(out, request.epoch);
    append32(out, request.frame_id);
    append32(out, request.key ? no_id : request.reference->id);
    append16(out, w);
    append16(out, h);
    append16(out, 0);
    append16(out, 0);
    append16(out, 45);
    append16(out, 30);
    append32(out, (scales.size() + 3) / 4);
    for (const auto &payload : payloads) {
      append32(out, static_cast<std::uint32_t>(payload.size()));
    }
    for (std::size_t i = 0; i < scales.size(); i += 4) {
      unsigned byte = 0;
      for (unsigned j = 0; j < 4 && i + j < scales.size(); ++j) {
        const auto code = scales[i + j] == 8 ? 0 : scales[i + j] == 16 ? 1 :
                                                                         2;
        byte |= code << (6 - 2 * j);
      }
      out.push_back(static_cast<std::uint8_t>(byte));
    }
    for (const auto &payload : payloads) {
      out.insert(out.end(), payload.begin(), payload.end());
    }
    seal(out);
    if (request.key || request.promoted) {
      result.stored_tag = body::canonical_tag(reconstruction, w, h);
    }
    return result;
  }
}  // namespace gamebub::v20::encoder
