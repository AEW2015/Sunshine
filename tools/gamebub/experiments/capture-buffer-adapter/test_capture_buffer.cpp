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
}  // namespace

int main() {
  test_channel_order_and_padding();
  test_bgrx_discards_unused_channel();
  test_source_mutation_does_not_change_owned_output();
  test_invalid_dimensions_pitch_and_layout();
  test_short_source_and_output_bound();
  test_pitch_arithmetic_overflow();
  return 0;
}
