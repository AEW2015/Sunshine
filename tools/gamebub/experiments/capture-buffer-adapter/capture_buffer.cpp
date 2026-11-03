/**
 * @file capture_buffer.cpp
 * @brief Portable validation and copy from pitched BGRA/BGRX to owned RGB.
 */
#include "capture_buffer.hpp"

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
}  // namespace gamebub::capture_buffer
