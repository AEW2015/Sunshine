/**
 * @file tests/unit/test_gamebub_v20_transport_case.cpp
 * @brief Offline contract input bounds and corruption-probe regression tests.
 */

// test includes
#include "../tests_common.h"

// standard includes
#include <chrono>
#include <filesystem>
#include <fstream>

// local includes
#include "tools/gamebub/native/transport_case.h"

namespace {
  /** @brief Remove only the exact temporary regular file owned by this test. */
  struct ContractFile {
    std::filesystem::path path = std::filesystem::temp_directory_path() / ("gamebub-contract-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".json");  ///< Unique private fixture path.

    /** @brief Preserve shared fixtures while removing this private file. */
    ~ContractFile() {
      std::error_code ignored;
      std::filesystem::remove(path, ignored);
    }
  };
}  // namespace

TEST(GamebubV20TransportCase, HexRejectsNoncanonicalAndOversizedBytes) {
  using gamebub::v20::transport_case::unhex;
  EXPECT_EQ(unhex("00af19"), (std::vector<std::uint8_t> {0, 175, 25}));
  EXPECT_TRUE(unhex("").empty());
  for (const auto *value : {"0", "GG", "AF", "0g", " 0", "/0", "0:"}) {
    EXPECT_THROW(unhex(value), std::invalid_argument);
  }
  EXPECT_THROW(unhex(std::string(2 * 49152 + 2, '0')), std::invalid_argument);
}

TEST(GamebubV20TransportCase, NegativeProbeFailsWhenValidControlIsAccepted) {
  namespace wire = gamebub::v20::transport;
  using gamebub::v20::transport_case::rejects_frame;
  const wire::FrameControl value {wire::Kind::request, 0, 1, 1, 1, 128, 0};
  auto bytes = wire::serialize(value);
  EXPECT_THROW(rejects_frame(bytes), std::invalid_argument);
  bytes.back() ^= 1;
  EXPECT_NO_THROW(rejects_frame(bytes));
  EXPECT_NO_THROW(rejects_frame({}));
}

TEST(GamebubV20TransportCase, ContractRequiresPinnedHashAndBoundedFile) {
  using gamebub::v20::transport_case::run;
  ContractFile fixture;
  EXPECT_THROW(run(fixture.path), std::filesystem::filesystem_error);
  {
    std::ofstream output(fixture.path, std::ios::binary);
    output << "{}";
  }
  EXPECT_THROW(run(fixture.path), std::invalid_argument);
  std::filesystem::resize_file(fixture.path, 1024 * 1024 + 1);
  EXPECT_THROW(run(fixture.path), std::invalid_argument);
}
