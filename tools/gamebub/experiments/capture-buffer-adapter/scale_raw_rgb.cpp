/**
 * @file scale_raw_rgb.cpp
 * @brief Apply the isolated optimized scaler to one packed RGB frame.
 *
 * Raw input/output keep this helper independent from media libraries. Timing
 * reported on stderr covers only the scaler call, not process or file I/O.
 */
#include "capture_buffer.hpp"

#include <charconv>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifdef _WIN32
  #include <fcntl.h>
  #include <io.h>
#endif

namespace {
  std::uint32_t parse_dimension(const char *value) {
    std::uint32_t parsed = 0;
    const std::string input {value};
    const auto result = std::from_chars(input.data(), input.data() + input.size(), parsed);
    if (result.ec != std::errc {} || result.ptr != input.data() + input.size() || parsed == 0) {
      throw std::invalid_argument {"dimensions must be positive decimal integers"};
    }
    return parsed;
  }
}  // namespace

int main(int argc, char **argv) {
  if (argc != 5) {
    std::cerr << "usage: scale_raw_rgb WIDTH HEIGHT INPUT.rgb|'-' OUTPUT.rgb|'-'\n";
    return 2;
  }
  try {
#ifdef _WIN32
    if (std::string {argv[3]} == "-") {
      _setmode(_fileno(stdin), _O_BINARY);
    }
    if (std::string {argv[4]} == "-") {
      _setmode(_fileno(stdout), _O_BINARY);
    }
#endif
    const auto width = parse_dimension(argv[1]);
    const auto height = parse_dimension(argv[2]);
    if (static_cast<std::size_t>(width) > std::numeric_limits<std::size_t>::max() / height / 3) {
      throw std::length_error {"source dimensions overflow"};
    }
    const auto byte_count = static_cast<std::size_t>(width) * height * 3;
    if (byte_count > gamebub::capture_buffer::max_rgb_bytes) {
      throw std::length_error {"source exceeds 64 MiB bound"};
    }
    std::vector<std::uint8_t> pixels(byte_count);
    if (std::string {argv[3]} == "-") {
      std::cin.read(reinterpret_cast<char *>(pixels.data()), static_cast<std::streamsize>(pixels.size()));
      if (std::cin.gcount() != static_cast<std::streamsize>(pixels.size()) ||
          std::cin.peek() != std::char_traits<char>::eof()) {
        throw std::runtime_error {"stdin size does not match RGB dimensions"};
      }
    } else {
      std::ifstream input {argv[3], std::ios::binary};
      if (!input || !input.read(reinterpret_cast<char *>(pixels.data()),
                                static_cast<std::streamsize>(pixels.size())) ||
          input.peek() != std::ifstream::traits_type::eof()) {
        throw std::runtime_error {"input file size does not match RGB dimensions"};
      }
    }
    const gamebub::capture_buffer::rgb_frame_t source {width, height, std::move(pixels)};
    const auto start = std::chrono::steady_clock::now();
    const auto output = gamebub::capture_buffer::optimized_area_letterbox_720x480(source);
    const auto finish = std::chrono::steady_clock::now();
    const auto elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(finish - start).count();

    if (std::string {argv[4]} == "-") {
      std::cout.write(reinterpret_cast<const char *>(output.pixels.data()),
                       static_cast<std::streamsize>(output.pixels.size()));
      if (!std::cout) {
        throw std::runtime_error {"could not write scaled RGB output to stdout"};
      }
    } else {
      std::ofstream result {argv[4], std::ios::binary | std::ios::trunc};
      result.write(reinterpret_cast<const char *>(output.pixels.data()),
                   static_cast<std::streamsize>(output.pixels.size()));
      if (!result) {
        throw std::runtime_error {"could not write scaled RGB output"};
      }
    }
    std::cerr << elapsed_ns << '\t' << __VERSION__ << '\n';
    return 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
}
