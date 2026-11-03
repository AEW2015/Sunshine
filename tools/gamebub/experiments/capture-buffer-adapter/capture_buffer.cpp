/**
 * @file capture_buffer.cpp
 * @brief Portable validation and copy from pitched BGRA/BGRX to owned RGB.
 */
#include "capture_buffer.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace gamebub::capture_buffer {
  namespace {
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
    if (source.width == 0 || source.height == 0) {
      throw std::invalid_argument {"RGB source dimensions must be nonzero"};
    }
    const auto source_pixels = checked_multiply(static_cast<std::size_t>(source.width), source.height);
    const auto source_bytes = checked_multiply(source_pixels, 3);
    if (source_bytes != source.pixels.size()) {
      throw std::invalid_argument {"packed RGB byte count does not match source dimensions"};
    }

    const double scale = std::min(
      static_cast<double>(canvas_width) / source.width,
      static_cast<double>(content_height) / source.height
    );
    const auto resized_width = std::clamp<std::uint32_t>(
      static_cast<std::uint32_t>(std::floor(source.width * scale + 0.5)), 1, canvas_width
    );
    const auto resized_height = std::clamp<std::uint32_t>(
      static_cast<std::uint32_t>(std::floor(source.height * scale + 0.5)), 1, content_height
    );
    const auto left = (canvas_width - resized_width) / 2;
    const auto top = (canvas_height - resized_height) / 2;
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
        const auto destination = (static_cast<std::size_t>(top + y) * canvas_width + left + x) * 3;
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
}  // namespace gamebub::capture_buffer
