/**
 * @file dump_canvas_pattern.cpp
 * @brief Emit one deterministic C++ canvas result as packed RGB bytes on stdout.
 */
#include "capture_buffer.hpp"

#ifdef _WIN32
  #include <fcntl.h>
  #include <io.h>
#endif

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace {
  constexpr std::uint32_t source_width = 1280;
  constexpr std::uint32_t source_height = 720;

  gamebub::capture_buffer::rgb_frame_t make_pattern(std::string_view name) {
    gamebub::capture_buffer::rgb_frame_t frame {
      source_width, source_height, std::vector<std::uint8_t>(source_width * source_height * 3)
    };
    for (std::uint32_t y = 0; y < source_height; ++y) {
      for (std::uint32_t x = 0; x < source_width; ++x) {
        const auto i = (static_cast<std::size_t>(y) * source_width + x) * 3;
        if (name == "gradient") {
          frame.pixels[i] = static_cast<std::uint8_t>((x * 255 + (source_width - 1) / 2) / (source_width - 1));
          frame.pixels[i + 1] = static_cast<std::uint8_t>((y * 255 + (source_height - 1) / 2) / (source_height - 1));
          frame.pixels[i + 2] = static_cast<std::uint8_t>(((x + y) * 255 + (source_width + source_height - 2) / 2) / (source_width + source_height - 2));
        } else if (name == "edge") {
          const bool right = x >= source_width / 2;
          const bool lower = y >= source_height / 2;
          const std::uint8_t red = lower ? 0 : (right ? 0 : 255);
          const std::uint8_t green = lower ? 0 : (right ? 255 : 0);
          const std::uint8_t blue = lower ? (right ? 255 : 255) : 0;
          frame.pixels[i] = lower && right ? 255 : red;
          frame.pixels[i + 1] = lower && right ? 255 : green;
          frame.pixels[i + 2] = lower && right ? 255 : blue;
        } else if (name == "checker1") {
          const auto value = static_cast<std::uint8_t>((x + y) % 2 == 0 ? 0 : 255);
          frame.pixels[i] = value;
          frame.pixels[i + 1] = value;
          frame.pixels[i + 2] = value;
        } else if (name == "stripes4") {
          const bool bright = (x / 4) % 2 != 0;
          frame.pixels[i] = bright ? 255 : 10;
          frame.pixels[i + 1] = bright ? 220 : 30;
          frame.pixels[i + 2] = bright ? 30 : 180;
        } else {
          throw std::invalid_argument {"unknown pattern name"};
        }
      }
    }
    return frame;
  }
}  // namespace

int main(int argc, char **argv) {
  if (argc != 3) {
    std::cerr << "usage: dump_canvas_pattern gradient|edge|checker1|stripes4 bilinear|area|area_fast\n";
    return 2;
  }
#ifdef _WIN32
  _setmode(_fileno(stdout), _O_BINARY);
#endif
  try {
    const auto source = make_pattern(argv[1]);
    const std::string_view mode = argv[2];
    const auto output = mode == "bilinear" ? gamebub::capture_buffer::bilinear_letterbox_720x480(source) :
                       mode == "area" ? gamebub::capture_buffer::area_letterbox_720x480(source) :
                       mode == "area_fast" ? gamebub::capture_buffer::optimized_area_letterbox_720x480(source) :
                                         throw std::invalid_argument {"unknown scaler mode"};
    std::cout.write(reinterpret_cast<const char *>(output.pixels.data()), static_cast<std::streamsize>(output.pixels.size()));
    return std::cout ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
}
