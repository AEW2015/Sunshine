/**
 * @file bench_capture_buffer.cpp
 * @brief Small synthetic CPU timing probe for the bilinear canvas candidate.
 */
#include "capture_buffer.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <string_view>
#include <vector>

namespace {
  template<class Scale>
  void measure(std::string_view name, const gamebub::capture_buffer::rgb_frame_t &source, Scale &&scale) {
  using clock_t = std::chrono::steady_clock;
  std::uint64_t checksum = 0;
  for (int iteration = 0; iteration < 3; ++iteration) {
    const auto image = scale(source);
    checksum += image.pixels[400'000];
  }

  std::vector<double> elapsed_ms;
  elapsed_ms.reserve(35);
  for (int iteration = 0; iteration < 35; ++iteration) {
    const auto start = clock_t::now();
    const auto image = scale(source);
    const auto finish = clock_t::now();
    checksum += image.pixels[400'000];
    elapsed_ms.push_back(std::chrono::duration<double, std::milli>(finish - start).count());
  }
  std::sort(elapsed_ms.begin(), elapsed_ms.end());
  const auto percentile = [&](double p) {
    const auto index = static_cast<std::size_t>(p * static_cast<double>(elapsed_ms.size() - 1));
    return elapsed_ms[index];
  };
  std::cout << name << ": synthetic 1280x720 RGB to 720x480; 3 warmups, " << elapsed_ms.size()
            << " measured calls; scaler+output allocation only; checksum=" << checksum << '\n'
            << "min_ms=" << elapsed_ms.front() << " p50_ms=" << percentile(0.50)
            << " p95_ms=" << percentile(0.95) << " max_ms=" << elapsed_ms.back() << '\n';
  }
}  // namespace

int main() {
  gamebub::capture_buffer::rgb_frame_t source {1280, 720, std::vector<std::uint8_t>(1280 * 720 * 3)};
  for (std::size_t i = 0; i < source.pixels.size(); ++i) {
    source.pixels[i] = static_cast<std::uint8_t>((i * 37 + i / 11) & 0xff);
  }
  measure("bilinear", source, gamebub::capture_buffer::bilinear_letterbox_720x480);
  measure("area", source, gamebub::capture_buffer::area_letterbox_720x480);
  measure("area_optimized", source, gamebub::capture_buffer::optimized_area_letterbox_720x480);
  return 0;
}
