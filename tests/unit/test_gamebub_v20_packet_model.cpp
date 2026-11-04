/**
 * @file tests/unit/test_gamebub_v20_packet_model.cpp
 * @brief Independent packet fault-model bounds, determinism and ownership retention checks.
 */

// test includes
#include "../tests_common.h"

// local includes
#include "tools/gamebub/native/packet_model.h"

TEST(GamebubV20PacketModel, RejectsUnboundedCasesAndZeroSeed) {
  using gamebub::v20::packet_model::run;
  EXPECT_THROW(run(0), std::invalid_argument);
  EXPECT_THROW(run(100001), std::invalid_argument);
  EXPECT_THROW(run(1, 0), std::invalid_argument);
}

TEST(GamebubV20PacketModel, FaultsRemainBoundedAndUnknownOutcomesStayOwned) {
  const auto report = gamebub::v20::packet_model::run(96);
  EXPECT_EQ(report.at("completed_cases").get<unsigned>() + report.at("safe_stopped_cases").get<unsigned>(), 96);
  EXPECT_GT(report.at("completed_cases").get<unsigned>(), 0);
  EXPECT_GT(report.at("safe_stopped_cases").get<unsigned>(), 0);
  EXPECT_GT(report.at("unknown_credit_cases").get<unsigned>(), 0);
  EXPECT_EQ(report.at("corrupt_receipts_rejected"), 96);
  EXPECT_EQ(report.at("stale_receipts_ignored"), 96);
  EXPECT_EQ(report.at("peak_data_permits"), 5);
  EXPECT_EQ(report.at("peak_control_mailbox"), 1);
  EXPECT_EQ(report.at("stopped_case_retained_data_sum").get<unsigned>(), 5 * report.at("safe_stopped_cases").get<unsigned>());
  for (const auto *field : {"payload_is_valid_codec_frame", "network_measured", "physical_drain_proven", "full_receiver_ownership_proven", "production_reset_or_recovery_proven", "hardware_playback"}) {
    EXPECT_FALSE(report.at(field).get<bool>()) << field;
  }
}

TEST(GamebubV20PacketModel, SameSeedReplaysSameDecisionsWithoutInventingPeerReset) {
  auto first = gamebub::v20::packet_model::run(24, 0xa11ce);
  auto second = gamebub::v20::packet_model::run(24, 0xa11ce);
  first.erase("wall_ns");
  second.erase("wall_ns");
  EXPECT_EQ(first, second);
  EXPECT_EQ(first.at("scope"), "independent_sender_packet_fault_models");
}
