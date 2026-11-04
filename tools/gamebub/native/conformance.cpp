/**
 * @file tools/gamebub/native/conformance.cpp
 * @brief Offline fixture/wire replay and finite generated-motion encoder profiling.
 */

// standard includes
#include <bit>
#include <charconv>
#include <fstream>
#include <iostream>
#include <vector>

// local includes
#include "body_case.h"
#include "composed_case.h"
#include "encoder_benchmark.h"
#include "encoder_case.h"
#include "hud_delta_case.h"
#include "packet_model.h"
#include "recovery_case.h"
#include "recovery_replay.h"
#include "transport_case.h"
#include "v20.h"

/**
 * @brief Replay bounded fixtures and profile generated-motion encoding without sockets.
 * @param argc Number of arguments.
 * @param argv Mode plus fixture paths and optional finite benchmark frame count.
 * @return Zero for a matching offline replay, nonzero for malformed/mismatched input.
 */
int main(int argc, char **argv) {
  using namespace gamebub::v20;
  if (argc == 3 && std::string_view(argv[1]) == "--hud-delta-contract") {
    try {
      std::cout << gamebub::v24::hud_delta_case::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "HUD delta contract rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--composed-contract") {
    try {
      std::cout << gamebub::v24::composed_case::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Composed contract rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--recovery-replay") {
    try {
      std::cout << gamebub::v24::recovery_replay::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Recovery replay rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--recovery-contract") {
    try {
      std::cout << gamebub::v24::recovery_case::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Recovery contract rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--packet-model") {
    try {
      const std::string_view text(argv[2]);
      unsigned rounds = 0;
      const auto parsed = std::from_chars(text.data(), text.data() + text.size(), rounds);
      body::require(parsed.ec == std::errc() && parsed.ptr == text.data() + text.size() && rounds >= 1 && rounds <= 100000, "packet model rounds must be 1..100000");
      std::cout << packet_model::run(rounds).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Packet model rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--transport-contract") {
    try {
      std::cout << transport_case::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Transport contract rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 4 && (std::string_view(argv[1]) == "--encoder-benchmark" || std::string_view(argv[1]) == "--encoder-benchmark-cached")) {
    try {
      const std::string_view text(argv[3]);
      unsigned frames = 0;
      const auto parsed = std::from_chars(text.data(), text.data() + text.size(), frames);
      body::require(parsed.ec == std::errc() && parsed.ptr == text.data() + text.size() && frames >= 1 && frames <= 1800, "benchmark frame count must be1..1800");
      benchmark::Options options;
      options.frames = frames;
      options.reuse_analysis = std::string_view(argv[1]) == "--encoder-benchmark-cached";
      std::cout << benchmark::run_case(argv[2], options).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Encoder benchmark rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--encoder-case") {
    try {
      std::cout << encoder_case::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Encoder fixture rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 3 && std::string_view(argv[1]) == "--body-case") {
    try {
      std::cout << body_case::run(argv[2]).dump() << '\n';
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "Body fixture rejected: " << error.what() << '\n';
      return 1;
    }
  }
  if (argc == 4 && std::string_view(argv[1]) == "--inverse") {
    std::ifstream input(argv[2], std::ios::binary), expected(argv[3], std::ios::binary);
    if (!input || !expected) {
      std::cerr << "Cannot open inverse files\n";
      return 2;
    }
    std::uint64_t blocks = 0;
    std::array<std::uint8_t, 256> in {}, gold {};
    while (input.peek() != std::char_traits<char>::eof()) {
      input.read(reinterpret_cast<char *>(in.data()), in.size());
      expected.read(reinterpret_cast<char *>(gold.data()), gold.size());
      if (input.gcount() != 256 || expected.gcount() != 256) {
        std::cerr << "Truncated inverse block\n";
        return 2;
      }
      block_t values {}, output {};
      for (unsigned i = 0; i < 64; ++i) {
        values[i] = std::bit_cast<std::int32_t>(le32(in, i * 4));
      }
      if (!inverse(values, output)) {
        std::cerr << "Illegal inverse input\n";
        return 1;
      }
      for (unsigned i = 0; i < 64; ++i) {
        if (output[i] != std::bit_cast<std::int32_t>(le32(gold, i * 4))) {
          std::cerr << "Residual mismatch at block " << blocks << " sample " << i << '\n';
          return 1;
        }
      }
      ++blocks;
    }
    expected.peek();
    if (!blocks || !input.eof() || !expected.eof() || expected.bad()) {
      std::cerr << "Empty, unreadable or unequal inverse arrays\n";
      return 2;
    }
    std::cout << "{\"scope\":\"inverse_only\",\"blocks\":" << blocks << ",\"samples\":" << blocks * 64 << "}\n";
    return 0;
  }
  if (argc == 3 && (std::string_view(argv[1]) == "--ar03" || std::string_view(argv[1]) == "--af03")) {
    std::ifstream input(argv[2], std::ios::binary);
    std::vector<std::uint8_t> bytes(49153);
    input.read(reinterpret_cast<char *>(bytes.data()), bytes.size());
    const auto count = input.gcount();
    if (count == 0 || input.bad()) {
      std::cerr << "Cannot read packet\n";
      return 2;
    }
    bytes.resize(static_cast<std::size_t>(count));
    const auto error = envelope(bytes, std::string_view(argv[1]) == "--af03");
    if (!error.empty()) {
      std::cerr << "Envelope rejected: " << error << '\n';
      return 1;
    }
    std::cout << "{\"scope\":\"envelope_only\",\"bytes\":" << bytes.size() << "}\n";
    return 0;
  }
  std::cerr << "Usage: gamebub-v20-conformance --inverse INPUT EXPECTED | --ar03 PACKET | --af03 PACKET | --body-case CASE.json | --encoder-case CASE.json | --transport-contract CONTRACT.json | --recovery-contract RESULTS.json | --recovery-replay RESULTS.json | --composed-contract RESULTS.json | --hud-delta-contract DIRECTORY | --packet-model ROUNDS | --encoder-benchmark CASE.json FRAMES | --encoder-benchmark-cached CASE.json FRAMES\n";
  return 2;
}
