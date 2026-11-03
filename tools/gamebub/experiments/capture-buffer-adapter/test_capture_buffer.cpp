/**
 * @file test_capture_buffer.cpp
 * @brief Self-contained tests for capture buffer validation and ownership.
 */
#include "capture_buffer.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

using gamebub::capture_buffer::copy_to_rgb;
using gamebub::capture_buffer::bilinear_letterbox_720x480;
using gamebub::capture_buffer::area_letterbox_720x480;
using gamebub::capture_buffer::optimized_area_letterbox_720x480;
using gamebub::capture_buffer::pixel_layout_e;

namespace {
  void check(bool condition, const char *expression, int line) {
    if (!condition) {
      std::cerr << "check failed at line " << line << ": " << expression << '\n';
      std::exit(1);
    }
  }

  #define CHECK(condition) check((condition), #condition, __LINE__)

  template<class Exception, class Callable>
  void expect_throws(Callable &&callable) {
    bool caught = false;
    try {
      callable();
    } catch (const Exception &) {
      caught = true;
    }
    CHECK(caught);
  }

  void test_channel_order_and_padding() {
    // Two pixels per row, 12-byte pitch, and no final-row padding in the span.
    std::array<std::uint8_t, 20> source {
      3, 2, 1, 255, 6, 5, 4, 128, 90, 91, 92, 93,
      30, 20, 10, 0, 60, 50, 40, 1,
    };
    auto output = copy_to_rgb(source, 2, 2, 12, pixel_layout_e::bgra);
    CHECK(output.width == 2 && output.height == 2);
    CHECK((output.pixels == std::vector<std::uint8_t> {1, 2, 3, 4, 5, 6, 10, 20, 30, 40, 50, 60}));
  }

  void test_bgrx_discards_unused_channel() {
    const std::array<std::uint8_t, 4> source {9, 8, 7, 0};
    auto output = copy_to_rgb(source, 1, 1, 4, pixel_layout_e::bgrx);
    CHECK((output.pixels == std::vector<std::uint8_t> {7, 8, 9}));
  }

  void test_source_mutation_does_not_change_owned_output() {
    std::array<std::uint8_t, 4> source {3, 2, 1, 0};
    auto output = copy_to_rgb(source, 1, 1, 4, pixel_layout_e::bgra);
    source.fill(99);
    CHECK((output.pixels == std::vector<std::uint8_t> {1, 2, 3}));
  }

  void test_invalid_dimensions_pitch_and_layout() {
    const std::array<std::uint8_t, 4> source {};
    expect_throws<std::invalid_argument>([&] { (void) copy_to_rgb(source, 0, 1, 4, pixel_layout_e::bgra); });
    expect_throws<std::invalid_argument>([&] { (void) copy_to_rgb(source, 1, 0, 4, pixel_layout_e::bgra); });
    expect_throws<std::invalid_argument>([&] { (void) copy_to_rgb(source, 1, 1, 3, pixel_layout_e::bgra); });
    expect_throws<std::invalid_argument>([&] { (void) copy_to_rgb(source, 1, 1, 4, static_cast<pixel_layout_e>(99)); });
  }

  void test_short_source_and_output_bound() {
    const std::array<std::uint8_t, 19> short_source {};
    expect_throws<std::length_error>([&] { (void) copy_to_rgb(short_source, 2, 2, 12, pixel_layout_e::bgra); });
    expect_throws<std::length_error>([] {
      (void) copy_to_rgb({}, 5000, 5000, 20000, pixel_layout_e::bgra);
    });
  }

  void test_pitch_arithmetic_overflow() {
    const std::array<std::uint8_t, 4> source {};
    expect_throws<std::length_error>([&] {
      (void) copy_to_rgb(source, 1, 2, std::numeric_limits<std::size_t>::max(), pixel_layout_e::bgra);
    });
    expect_throws<std::length_error>([&] {
      (void) copy_to_rgb(source, 1, 2, std::numeric_limits<std::size_t>::max() - 3, pixel_layout_e::bgra);
    });
  }

  void test_16_by_9_geometry_and_letterbox_edges() {
    gamebub::capture_buffer::rgb_frame_t source {16, 9, std::vector<std::uint8_t>(16 * 9 * 3)};
    for (std::size_t i = 0; i < source.pixels.size(); i += 3) {
      source.pixels[i] = 11;
      source.pixels[i + 1] = 22;
      source.pixels[i + 2] = 33;
    }
    const auto output = bilinear_letterbox_720x480(source);
    CHECK(output.width == 720 && output.height == 480);
    const auto pixel = [&](std::size_t x, std::size_t y) {
      const auto index = (y * 720 + x) * 3;
      return std::array<std::uint8_t, 3> {output.pixels[index], output.pixels[index + 1], output.pixels[index + 2]};
    };
    CHECK((pixel(0, 36) == std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(0, 37) == std::array<std::uint8_t, 3> {11, 22, 33}));
    CHECK((pixel(719, 441) == std::array<std::uint8_t, 3> {11, 22, 33}));
    CHECK((pixel(719, 442) == std::array<std::uint8_t, 3> {0, 0, 0}));
  }

  void test_1_by_1_source_fits_as_centered_square() {
    gamebub::capture_buffer::rgb_frame_t source {1, 1, {17, 18, 19}};
    const auto output = bilinear_letterbox_720x480(source);
    const auto area_output = area_letterbox_720x480(source);
    const auto optimized_output = optimized_area_letterbox_720x480(source);
    const auto pixel = [&](std::size_t x, std::size_t y) {
      const auto index = (y * 720 + x) * 3;
      return std::array<std::uint8_t, 3> {output.pixels[index], output.pixels[index + 1], output.pixels[index + 2]};
    };
    CHECK((pixel(156, 100) == std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(157, 37) == std::array<std::uint8_t, 3> {17, 18, 19}));
    CHECK((pixel(561, 441) == std::array<std::uint8_t, 3> {17, 18, 19}));
    CHECK((pixel(562, 100) == std::array<std::uint8_t, 3> {0, 0, 0}));
    const auto area_index = (static_cast<std::size_t>(37) * 720 + 157) * 3;
    CHECK((std::array<std::uint8_t, 3> {area_output.pixels[area_index], area_output.pixels[area_index + 1], area_output.pixels[area_index + 2]} ==
           std::array<std::uint8_t, 3> {17, 18, 19}));
    CHECK(optimized_output.pixels == area_output.pixels);
  }

  void test_odd_dimensions_are_deterministic_and_bounded() {
    gamebub::capture_buffer::rgb_frame_t source {5, 3, std::vector<std::uint8_t>(5 * 3 * 3)};
    for (std::uint32_t y = 0; y < source.height; ++y) {
      for (std::uint32_t x = 0; x < source.width; ++x) {
        const auto index = (static_cast<std::size_t>(y) * source.width + x) * 3;
        source.pixels[index] = static_cast<std::uint8_t>(x * 40);
        source.pixels[index + 1] = static_cast<std::uint8_t>(y * 80);
        source.pixels[index + 2] = static_cast<std::uint8_t>(x + y);
      }
    }
    const auto first = bilinear_letterbox_720x480(source);
    const auto second = bilinear_letterbox_720x480(source);
    const auto area_first = area_letterbox_720x480(source);
    const auto area_second = area_letterbox_720x480(source);
    const auto optimized = optimized_area_letterbox_720x480(source);
    CHECK(first.pixels == second.pixels);
    CHECK(area_first.pixels == area_second.pixels);
    CHECK(optimized.pixels == area_first.pixels);
    CHECK(first.pixels.size() == 720 * 480 * 3);
    const auto pixel = [&](const auto &image, std::size_t x, std::size_t y) {
      const auto index = (y * 720 + x) * 3;
      return std::array<std::uint8_t, 3> {image.pixels[index], image.pixels[index + 1], image.pixels[index + 2]};
    };
    CHECK((pixel(first, 21, 200) == std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(first, 22, 200) != std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(first, 696, 200) != std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(first, 697, 200) == std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK(area_first.pixels.size() == first.pixels.size());
  }

  void test_scaler_rejects_invalid_source_shape() {
    expect_throws<std::invalid_argument>([] {
      (void) bilinear_letterbox_720x480(gamebub::capture_buffer::rgb_frame_t {0, 1, {}});
    });
    expect_throws<std::invalid_argument>([] {
      (void) bilinear_letterbox_720x480(gamebub::capture_buffer::rgb_frame_t {2, 2, {0, 1, 2}});
    });
  }

  void test_area_filter_is_bounded_and_antialiases_high_frequency_pattern() {
    constexpr std::uint32_t width = 1280;
    constexpr std::uint32_t height = 720;
    gamebub::capture_buffer::rgb_frame_t source {width, height, std::vector<std::uint8_t>(width * height * 3)};
    for (std::uint32_t y = 0; y < height; ++y) {
      for (std::uint32_t x = 0; x < width; ++x) {
        const auto value = static_cast<std::uint8_t>((x + y) % 2 == 0 ? 0 : 255);
        const auto index = (static_cast<std::size_t>(y) * width + x) * 3;
        source.pixels[index] = value;
        source.pixels[index + 1] = value;
        source.pixels[index + 2] = value;
      }
    }
    const auto first = area_letterbox_720x480(source);
    const auto second = area_letterbox_720x480(source);
    CHECK(first.pixels == second.pixels);
    CHECK(first.pixels.size() == 720 * 480 * 3);
    std::uint8_t minimum = 255;
    std::uint8_t maximum = 0;
    for (std::uint32_t y = 37; y <= 441; ++y) {
      for (std::uint32_t x = 0; x < 720; ++x) {
        const auto index = (static_cast<std::size_t>(y) * 720 + x) * 3;
        for (std::size_t channel = 0; channel < 3; ++channel) {
          minimum = std::min(minimum, first.pixels[index + channel]);
          maximum = std::max(maximum, first.pixels[index + channel]);
        }
      }
    }
    CHECK(minimum >= 126 && maximum <= 129);
    CHECK(std::all_of(first.pixels.begin(), first.pixels.begin() + 37 * 720 * 3,
                      [](std::uint8_t value) { return value == 0; }));
    CHECK(std::all_of(first.pixels.begin() + 442 * 720 * 3, first.pixels.end(),
                      [](std::uint8_t value) { return value == 0; }));
  }

  void test_optimized_area_matches_reference_across_patterns() {
    constexpr std::uint32_t width = 1280;
    constexpr std::uint32_t height = 720;
    for (int pattern = 0; pattern < 4; ++pattern) {
      gamebub::capture_buffer::rgb_frame_t source {width, height, std::vector<std::uint8_t>(width * height * 3)};
      for (std::uint32_t y = 0; y < height; ++y) {
        for (std::uint32_t x = 0; x < width; ++x) {
          const auto index = (static_cast<std::size_t>(y) * width + x) * 3;
          if (pattern == 0) {
            source.pixels[index] = static_cast<std::uint8_t>((x * 255 + 639) / 1279);
            source.pixels[index + 1] = static_cast<std::uint8_t>((y * 255 + 359) / 719);
            source.pixels[index + 2] = static_cast<std::uint8_t>(((x + y) * 255 + 999) / 1998);
          } else if (pattern == 1) {
            const bool right = x >= width / 2;
            const bool lower = y >= height / 2;
            source.pixels[index] = lower && right ? 255 : (!lower && !right ? 255 : 0);
            source.pixels[index + 1] = !lower && right ? 255 : (lower && right ? 255 : 0);
            source.pixels[index + 2] = lower ? 255 : 0;
          } else if (pattern == 2) {
            const auto value = static_cast<std::uint8_t>((x + y) % 2 == 0 ? 0 : 255);
            source.pixels[index] = value;
            source.pixels[index + 1] = value;
            source.pixels[index + 2] = value;
          } else {
            const bool bright = (x / 4) % 2 != 0;
            source.pixels[index] = bright ? 255 : 10;
            source.pixels[index + 1] = bright ? 220 : 30;
            source.pixels[index + 2] = bright ? 30 : 180;
          }
        }
      }
      const auto reference = area_letterbox_720x480(source);
      const auto optimized = optimized_area_letterbox_720x480(source);
      CHECK(optimized.width == reference.width && optimized.height == reference.height);
      CHECK(optimized.pixels.size() == reference.pixels.size());
      std::uint8_t maximum_difference = 0;
      for (std::size_t i = 0; i < reference.pixels.size(); ++i) {
        const auto difference = static_cast<std::uint8_t>(std::abs(
          static_cast<int>(optimized.pixels[i]) - static_cast<int>(reference.pixels[i])
        ));
        maximum_difference = std::max(maximum_difference, difference);
      }
      CHECK(maximum_difference <= 1);
    }
  }
}  // namespace

int main() {
  test_channel_order_and_padding();
  test_bgrx_discards_unused_channel();
  test_source_mutation_does_not_change_owned_output();
  test_invalid_dimensions_pitch_and_layout();
  test_short_source_and_output_bound();
  test_pitch_arithmetic_overflow();
  test_16_by_9_geometry_and_letterbox_edges();
  test_1_by_1_source_fits_as_centered_square();
  test_odd_dimensions_are_deterministic_and_bounded();
  test_scaler_rejects_invalid_source_shape();
  test_area_filter_is_bounded_and_antialiases_high_frequency_pattern();
  test_optimized_area_matches_reference_across_patterns();
  return 0;
}
