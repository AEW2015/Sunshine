/**
 * @file capture_buffer.hpp
 * @brief Portable owned RGB copy adapter for BGRA/BGRX capture buffers.
 */
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace gamebub::capture_buffer {
  constexpr std::size_t max_rgb_bytes = 64 * 1024 * 1024;  ///< Maximum owned output allocation.

  /**
   * @brief Supported four-byte source pixel layouts.
   */
  enum class pixel_layout_e {
    bgra,
    bgrx,
  };

  /**
   * @brief Owned packed RGB image copied from a pitched source buffer.
   */
  struct rgb_frame_t {
    std::uint32_t width;  ///< Image width in pixels.
    std::uint32_t height;  ///< Image height in pixels.
    std::vector<std::uint8_t> pixels;  ///< Packed RGB pixels in top-to-bottom row order.
  };

  /**
   * @brief Validate a BGRA/BGRX source and copy its color channels to owned RGB.
   *
   * The source may include padding between rows and need not include padding
   * after its last row. Alpha/X is intentionally discarded. This function has
   * no Windows, DXGI, or Sunshine dependency.
   *
   * @param source Borrowed source bytes; they are not retained.
   * @param width Nonzero source width in pixels.
   * @param height Nonzero source height in pixels.
   * @param row_pitch Bytes between starts of consecutive source rows.
   * @param layout BGRA (discard alpha) or BGRX (discard unused X byte).
   * @return An owned tightly packed RGB frame.
   * @throws std::invalid_argument For zero dimensions, too-small pitch, or unknown layout.
   * @throws std::length_error For arithmetic overflow, insufficient source bytes,
   *         or output allocation above max_rgb_bytes.
   */
  [[nodiscard]] rgb_frame_t copy_to_rgb(
    std::span<const std::uint8_t> source,
    std::uint32_t width,
    std::uint32_t height,
    std::size_t row_pitch,
    pixel_layout_e layout
  );
}  // namespace gamebub::capture_buffer
