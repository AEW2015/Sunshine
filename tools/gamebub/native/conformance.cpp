/**
 * @file tools/gamebub/native/conformance.cpp
 * @brief Offline CLI replay for inverse arrays, envelopes and full AR03 body fixtures.
 */

// standard includes
#include <bit>
#include <fstream>
#include <iostream>
#include <vector>

// local includes
#include "body_case.h"
#include "encoder_case.h"
#include "v20.h"

/**
 * @brief Replay bounded inverse files, outer packets or a full body case without sockets.
 * @param argc Number of arguments.
 * @param argv --inverse input expected, --ar03 packet, --af03 packet or --body-case JSON.
 * @return Zero for a matching offline replay, nonzero for malformed/mismatched input.
 */
int main(int argc, char **argv) {
  using namespace gamebub::v20;
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
  std::cerr << "Usage: gamebub-v20-conformance --inverse INPUT EXPECTED | --ar03 PACKET | --af03 PACKET | --body-case CASE.json | --encoder-case CASE.json\n";
  return 2;
}
