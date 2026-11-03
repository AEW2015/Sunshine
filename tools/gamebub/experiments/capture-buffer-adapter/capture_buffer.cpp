/**
 * @file capture_buffer.cpp
 * @brief Portable validation and copy from pitched BGRA/BGRX to owned RGB.
 */
#include "capture_buffer.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace gamebub::capture_buffer {
  namespace {
    struct tap_t {
      std::uint32_t source_index;
      std::uint16_t overlap;
    };

    struct axis_plan_t {
      std::vector<std::size_t> offsets;
      std::vector<tap_t> taps;
    };

    struct fit_t {
      std::uint32_t width;
      std::uint32_t height;
      std::uint32_t left;
      std::uint32_t top;
    };

    /**
     * @brief Multiply sizes without wrapping.
     * @param left First size factor.
     * @param right Second size factor.
     * @return Product.
     * @throws std::length_error If the product does not fit in size_t.
     */
    std::size_t checked_multiply(std::size_t left, std::size_t right) {
      if (right != 0 && left > std::numeric_limits<std::size_t>::max() / right) {
        throw std::length_error {"capture buffer size overflow"};
      }
      return left * right;
    }

    /**
     * @brief Add sizes without wrapping.
     * @param left First size.
     * @param right Second size.
     * @return Sum.
     * @throws std::length_error If the sum does not fit in size_t.
     */
    std::size_t checked_add(std::size_t left, std::size_t right) {
      if (left > std::numeric_limits<std::size_t>::max() - right) {
        throw std::length_error {"capture buffer size overflow"};
      }
      return left + right;
    }

    fit_t fit_dimensions(std::uint32_t width, std::uint32_t height) {
      const double scale = std::min(static_cast<double>(canvas_width) / width,
                                     static_cast<double>(content_height) / height);
      const auto fitted_width = std::clamp<std::uint32_t>(
        static_cast<std::uint32_t>(std::floor(width * scale + 0.5)), 1, canvas_width
      );
      const auto fitted_height = std::clamp<std::uint32_t>(
        static_cast<std::uint32_t>(std::floor(height * scale + 0.5)), 1, content_height
      );
      return {fitted_width, fitted_height, (canvas_width - fitted_width) / 2,
              (canvas_height - fitted_height) / 2};
    }

    void validate_rgb_source(const rgb_frame_t &source) {
      if (source.width == 0 || source.height == 0) {
        throw std::invalid_argument {"RGB source dimensions must be nonzero"};
      }
      const auto source_pixels = checked_multiply(static_cast<std::size_t>(source.width), source.height);
      const auto source_bytes = checked_multiply(source_pixels, 3);
      if (source_bytes != source.pixels.size()) {
        throw std::invalid_argument {"packed RGB byte count does not match source dimensions"};
      }
    }

    axis_plan_t make_area_plan(std::uint32_t input_size, std::uint32_t output_size) {
      const auto maximum_taps = max_rgb_bytes / sizeof(tap_t);
      const auto upper_bound = checked_add(input_size, output_size);
      if (output_size > input_size || upper_bound > maximum_taps) {
        throw std::length_error {"area scaler axis plan exceeds configured bound"};
      }
      axis_plan_t plan;
      plan.offsets.reserve(static_cast<std::size_t>(output_size) + 1);
      plan.taps.reserve(upper_bound);
      for (std::uint32_t output = 0; output < output_size; ++output) {
        plan.offsets.push_back(plan.taps.size());
        const auto start = static_cast<std::uint64_t>(output) * input_size;
        const auto end = static_cast<std::uint64_t>(output + 1) * input_size;
        const auto first = static_cast<std::uint32_t>(start / output_size);
        const auto past = static_cast<std::uint32_t>((end + output_size - 1) / output_size);
        for (auto source = first; source < past; ++source) {
          const auto source_start = static_cast<std::uint64_t>(source) * output_size;
          const auto source_end = static_cast<std::uint64_t>(source + 1) * output_size;
          const auto overlap = std::min(end, source_end) - std::max(start, source_start);
          if (overlap == 0 || overlap > std::numeric_limits<std::uint16_t>::max()) {
            throw std::length_error {"area scaler weight is outside configured integer range"};
          }
          plan.taps.push_back({source, static_cast<std::uint16_t>(overlap)});
        }
      }
      plan.offsets.push_back(plan.taps.size());
      if (checked_multiply(plan.taps.size(), sizeof(tap_t)) > max_rgb_bytes ||
          checked_multiply(plan.offsets.size(), sizeof(std::size_t)) > max_rgb_bytes) {
        throw std::length_error {"area scaler axis plan exceeds configured allocation bound"};
      }
      return plan;
    }

    template<class Read>
    double sample_axis(std::uint32_t output_index, std::uint32_t input_size,
                       std::uint32_t output_size, Read &&read) {
      if (output_size < input_size) {
        const double start = static_cast<double>(output_index) * input_size / output_size;
        const double end = static_cast<double>(output_index + 1) * input_size / output_size;
        const auto first = static_cast<std::uint32_t>(std::floor(start));
        const auto past = static_cast<std::uint32_t>(std::ceil(end));
        double sum = 0.0;
        for (auto index = first; index < past; ++index) {
          const double overlap = std::max(0.0, std::min(end, static_cast<double>(index + 1)) -
                                                  std::max(start, static_cast<double>(index)));
          sum += read(index) * overlap;
        }
        return sum / (end - start);
      }

      const double position = std::clamp(
        (static_cast<double>(output_index) + 0.5) * input_size / output_size - 0.5,
        0.0, static_cast<double>(input_size - 1)
      );
      const auto low = static_cast<std::uint32_t>(std::floor(position));
      const auto high = std::min(low + 1, input_size - 1);
      const double fraction = position - low;
      return read(low) * (1.0 - fraction) + read(high) * fraction;
    }
  }  // namespace

  rgb_frame_t copy_to_rgb(
    std::span<const std::uint8_t> source,
    std::uint32_t width,
    std::uint32_t height,
    std::size_t row_pitch,
    pixel_layout_e layout
  ) {
    if (width == 0 || height == 0) {
      throw std::invalid_argument {"capture dimensions must be nonzero"};
    }
    if (layout != pixel_layout_e::bgra && layout != pixel_layout_e::bgrx) {
      throw std::invalid_argument {"unsupported four-byte source pixel layout"};
    }

    const auto source_row_bytes = checked_multiply(static_cast<std::size_t>(width), 4);
    if (row_pitch < source_row_bytes) {
      throw std::invalid_argument {"source row pitch is smaller than one pixel row"};
    }
    const auto output_row_bytes = checked_multiply(static_cast<std::size_t>(width), 3);
    const auto output_bytes = checked_multiply(output_row_bytes, static_cast<std::size_t>(height));
    if (output_bytes > max_rgb_bytes) {
      throw std::length_error {"owned RGB output exceeds configured bound"};
    }

    // Only bytes through the final pixel are required; trailing last-row padding
    // is not read and need not be present in the caller's span.
    const auto prior_rows_bytes = checked_multiply(row_pitch, static_cast<std::size_t>(height - 1));
    const auto required_source_bytes = checked_add(prior_rows_bytes, source_row_bytes);
    if (source.size() < required_source_bytes) {
      throw std::length_error {"source buffer is shorter than its dimensions and row pitch"};
    }

    rgb_frame_t output {width, height, std::vector<std::uint8_t>(output_bytes)};
    for (std::size_t y = 0; y < height; ++y) {
      const auto source_row = source.data() + y * row_pitch;
      auto output_pixel = output.pixels.data() + y * output_row_bytes;
      for (std::size_t x = 0; x < width; ++x) {
        const auto source_pixel = source_row + x * 4;
        *output_pixel++ = source_pixel[2];  // R
        *output_pixel++ = source_pixel[1];  // G
        *output_pixel++ = source_pixel[0];  // B
      }
    }
    return output;
  }

  rgb_frame_t bilinear_letterbox_720x480(const rgb_frame_t &source) {
    validate_rgb_source(source);
    const auto fit = fit_dimensions(source.width, source.height);
    const auto resized_width = fit.width;
    const auto resized_height = fit.height;
    const auto output_row_bytes = static_cast<std::size_t>(canvas_width) * 3;
    rgb_frame_t output {
      canvas_width,
      canvas_height,
      std::vector<std::uint8_t>(output_row_bytes * canvas_height, 0),
    };

    for (std::uint32_t y = 0; y < resized_height; ++y) {
      const double source_y = std::clamp(
        (static_cast<double>(y) + 0.5) * source.height / resized_height - 0.5,
        0.0, static_cast<double>(source.height - 1)
      );
      const auto y0 = static_cast<std::uint32_t>(std::floor(source_y));
      const auto y1 = std::min(y0 + 1, source.height - 1);
      const double fy = source_y - y0;
      for (std::uint32_t x = 0; x < resized_width; ++x) {
        const double source_x = std::clamp(
          (static_cast<double>(x) + 0.5) * source.width / resized_width - 0.5,
          0.0, static_cast<double>(source.width - 1)
        );
        const auto x0 = static_cast<std::uint32_t>(std::floor(source_x));
        const auto x1 = std::min(x0 + 1, source.width - 1);
        const double fx = source_x - x0;
        const auto destination = (static_cast<std::size_t>(fit.top + y) * canvas_width + fit.left + x) * 3;
        const auto p00 = (static_cast<std::size_t>(y0) * source.width + x0) * 3;
        const auto p10 = (static_cast<std::size_t>(y0) * source.width + x1) * 3;
        const auto p01 = (static_cast<std::size_t>(y1) * source.width + x0) * 3;
        const auto p11 = (static_cast<std::size_t>(y1) * source.width + x1) * 3;
        for (std::size_t channel = 0; channel < 3; ++channel) {
          const double upper = source.pixels[p00 + channel] * (1.0 - fx) + source.pixels[p10 + channel] * fx;
          const double lower = source.pixels[p01 + channel] * (1.0 - fx) + source.pixels[p11 + channel] * fx;
          output.pixels[destination + channel] = static_cast<std::uint8_t>(std::floor(upper * (1.0 - fy) + lower * fy + 0.5));
        }
      }
    }
    return output;
  }

  rgb_frame_t area_letterbox_720x480(const rgb_frame_t &source) {
    validate_rgb_source(source);
    const auto fit = fit_dimensions(source.width, source.height);
    const auto output_row_bytes = static_cast<std::size_t>(canvas_width) * 3;
    rgb_frame_t output {
      canvas_width,
      canvas_height,
      std::vector<std::uint8_t>(output_row_bytes * canvas_height, 0),
    };

    // Horizontal pass reduces into a bounded double-precision intermediate.
    const auto intermediate_values = checked_multiply(
      checked_multiply(static_cast<std::size_t>(fit.width), source.height), 3
    );
    const auto intermediate_bytes = checked_multiply(intermediate_values, sizeof(double));
    if (intermediate_bytes > max_rgb_bytes) {
      throw std::length_error {"area scaler intermediate exceeds configured bound"};
    }
    std::vector<double> horizontal(intermediate_values);
    for (std::uint32_t y = 0; y < source.height; ++y) {
      for (std::uint32_t x = 0; x < fit.width; ++x) {
        const auto destination = (static_cast<std::size_t>(y) * fit.width + x) * 3;
        for (std::uint32_t channel = 0; channel < 3; ++channel) {
          horizontal[destination + channel] = sample_axis(x, source.width, fit.width, [&](std::uint32_t sx) {
            const auto source_index = (static_cast<std::size_t>(y) * source.width + sx) * 3 + channel;
            return static_cast<double>(source.pixels[source_index]);
          });
        }
      }
    }

    // Vertical pass integrates source-row coverage, then rounds to byte values.
    for (std::uint32_t y = 0; y < fit.height; ++y) {
      for (std::uint32_t x = 0; x < fit.width; ++x) {
        const auto destination = (static_cast<std::size_t>(fit.top + y) * canvas_width + fit.left + x) * 3;
        for (std::uint32_t channel = 0; channel < 3; ++channel) {
          const double value = sample_axis(y, source.height, fit.height, [&](std::uint32_t sy) {
            const auto index = (static_cast<std::size_t>(sy) * fit.width + x) * 3 + channel;
            return horizontal[index];
          });
          output.pixels[destination + channel] = static_cast<std::uint8_t>(std::floor(value + 0.5));
        }
      }
    }
    return output;
  }

  rgb_frame_t optimized_area_letterbox_720x480(const rgb_frame_t &source) {
    validate_rgb_source(source);
    const auto source_bytes = checked_multiply(
      checked_multiply(static_cast<std::size_t>(source.width), source.height), 3
    );
    if (source_bytes > max_rgb_bytes) {
      throw std::length_error {"optimized area source exceeds configured bound"};
    }
    const auto fit = fit_dimensions(source.width, source.height);
    if (fit.width > source.width || fit.height > source.height) {
      return area_letterbox_720x480(source);
    }

    const auto horizontal_plan = make_area_plan(source.width, fit.width);
    const auto vertical_plan = make_area_plan(source.height, fit.height);
    const auto intermediate_values = checked_multiply(
      checked_multiply(static_cast<std::size_t>(fit.width), source.height), 3
    );
    const auto intermediate_bytes = checked_multiply(intermediate_values, sizeof(std::uint64_t));
    if (intermediate_bytes > max_rgb_bytes) {
      throw std::length_error {"optimized area intermediate exceeds configured bound"};
    }
    std::vector<std::uint64_t> horizontal(intermediate_values);
    for (std::uint32_t y = 0; y < source.height; ++y) {
      for (std::uint32_t x = 0; x < fit.width; ++x) {
        const auto destination = (static_cast<std::size_t>(y) * fit.width + x) * 3;
        for (std::size_t tap_index = horizontal_plan.offsets[x];
             tap_index < horizontal_plan.offsets[x + 1]; ++tap_index) {
          const auto tap = horizontal_plan.taps[tap_index];
          const auto from = (static_cast<std::size_t>(y) * source.width + tap.source_index) * 3;
          for (std::size_t channel = 0; channel < 3; ++channel) {
            horizontal[destination + channel] += static_cast<std::uint64_t>(source.pixels[from + channel]) * tap.overlap;
          }
        }
      }
    }

    const auto denominator = checked_multiply(static_cast<std::size_t>(source.width), source.height);
    const auto output_row_bytes = static_cast<std::size_t>(canvas_width) * 3;
    rgb_frame_t output {
      canvas_width,
      canvas_height,
      std::vector<std::uint8_t>(output_row_bytes * canvas_height, 0),
    };
    for (std::uint32_t y = 0; y < fit.height; ++y) {
      for (std::uint32_t x = 0; x < fit.width; ++x) {
        const auto destination = (static_cast<std::size_t>(fit.top + y) * canvas_width + fit.left + x) * 3;
        std::array<std::uint64_t, 3> accumulators {};
        for (std::size_t tap_index = vertical_plan.offsets[y];
             tap_index < vertical_plan.offsets[y + 1]; ++tap_index) {
          const auto tap = vertical_plan.taps[tap_index];
          const auto from = (static_cast<std::size_t>(tap.source_index) * fit.width + x) * 3;
          for (std::size_t channel = 0; channel < 3; ++channel) {
            accumulators[channel] += horizontal[from + channel] * tap.overlap;
          }
        }
        for (std::size_t channel = 0; channel < 3; ++channel) {
          const auto rounded = (accumulators[channel] + denominator / 2) / denominator;
          output.pixels[destination + channel] = static_cast<std::uint8_t>(std::min<std::uint64_t>(rounded, 255));
        }
      }
    }
    return output;
  }
}  // namespace gamebub::capture_buffer
