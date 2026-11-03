/**
 * @file test_capture_buffer.cpp
 * @brief Self-contained tests for capture buffer validation and ownership.
 */
#include "capture_buffer.hpp"

#include <array>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

using gamebub::capture_buffer::copy_to_rgb;
using gamebub::capture_buffer::bilinear_letterbox_720x480;
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
    const auto pixel = [&](std::size_t x, std::size_t y) {
      const auto index = (y * 720 + x) * 3;
      return std::array<std::uint8_t, 3> {output.pixels[index], output.pixels[index + 1], output.pixels[index + 2]};
    };
    CHECK((pixel(156, 100) == std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(157, 37) == std::array<std::uint8_t, 3> {17, 18, 19}));
    CHECK((pixel(561, 441) == std::array<std::uint8_t, 3> {17, 18, 19}));
    CHECK((pixel(562, 100) == std::array<std::uint8_t, 3> {0, 0, 0}));
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
    CHECK(first.pixels == second.pixels);
    CHECK(first.pixels.size() == 720 * 480 * 3);
    const auto pixel = [&](const auto &image, std::size_t x, std::size_t y) {
      const auto index = (y * 720 + x) * 3;
      return std::array<std::uint8_t, 3> {image.pixels[index], image.pixels[index + 1], image.pixels[index + 2]};
    };
    CHECK((pixel(first, 21, 200) == std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(first, 22, 200) != std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(first, 696, 200) != std::array<std::uint8_t, 3> {0, 0, 0}));
    CHECK((pixel(first, 697, 200) == std::array<std::uint8_t, 3> {0, 0, 0}));
  }

  void test_scaler_rejects_invalid_source_shape() {
    expect_throws<std::invalid_argument>([] {
      (void) bilinear_letterbox_720x480(gamebub::capture_buffer::rgb_frame_t {0, 1, {}});
    });
    expect_throws<std::invalid_argument>([] {
      (void) bilinear_letterbox_720x480(gamebub::capture_buffer::rgb_frame_t {2, 2, {0, 1, 2}});
    });
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
  return 0;
}
