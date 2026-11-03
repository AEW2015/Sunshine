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
  constexpr std::uint32_t canvas_width = 720;  ///< Fixed output canvas width.
  constexpr std::uint32_t canvas_height = 480;  ///< Fixed output canvas height.
  constexpr std::uint32_t content_height = 405;  ///< Centered image area for 16:9 content.

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

  /**
   * @brief Bilinearly fit RGB pixels in a centered 720x405 viewport on black 720x480.
   *
   * Aspect ratio is preserved using nearest-integer destination dimensions;
   * the image is centered within the 720x405 content viewport. Sampling uses
   * pixel-center coordinates, edge clamping, and round-to-nearest channel
   * conversion. For an exact 16:9 input the content is 720x405, with 37 top
   * and 38 bottom black rows. This is a simple scaling candidate rather than
   * a perceptual-quality match to Sunshine's existing scaler.
   *
   * @param source Owned packed RGB source image.
   * @return Owned fixed-size 720x480 RGB canvas.
   * @throws std::invalid_argument If source dimensions or packed pixel count disagree.
   * @throws std::length_error If source dimension arithmetic overflows.
   */
  [[nodiscard]] rgb_frame_t bilinear_letterbox_720x480(const rgb_frame_t &source);

  /**
   * @brief Fit RGB into 720x480 using separable area averaging for reductions.
   *
   * Each reducing axis integrates source-pixel area coverage; an expanding
   * axis uses pixel-center bilinear sampling. The intermediate double plane is
   * bounded by max_rgb_bytes.
   *
   * @param source Owned packed RGB source image.
   * @return Owned fixed-size 720x480 RGB canvas.
   * @throws std::invalid_argument If source dimensions or packed pixel count disagree.
   * @throws std::length_error If arithmetic or bounded scratch allocation fails.
   */
  [[nodiscard]] rgb_frame_t area_letterbox_720x480(const rgb_frame_t &source);

  /**
   * @brief Integer-weighted separable area scaler for downscaling inputs.
   *
   * Uses precomputed integer overlap weights and rounds once after both axes.
   * If fitting would enlarge either source axis, delegates to the area reference
   * path. Axis-plan and intermediate scratch allocations are each capped by
   * max_rgb_bytes.
   *
   * @param source Owned packed RGB source image.
   * @return Owned fixed-size 720x480 RGB canvas.
   * @throws std::invalid_argument If source dimensions or packed pixel count disagree.
   * @throws std::length_error If source, plan or scratch bounds are exceeded.
   */
  [[nodiscard]] rgb_frame_t optimized_area_letterbox_720x480(const rgb_frame_t &source);
}  // namespace gamebub::capture_buffer
