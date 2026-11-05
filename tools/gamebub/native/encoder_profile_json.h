/**
 * @file tools/gamebub/native/encoder_profile_json.h
 * @brief Offline diagnostic serialization for explicit native encoder observations.
 */
#pragma once

// local includes
#include "body_case.h"
#include "encoder_profile.h"

namespace gamebub::v20::encoder {
  /**
   * @brief Export every observed stage with visible calls, partial work and clock overhead.
   * @param profile Caller-owned completed observer; no clocks are read during serialization.
   * @return Diagnostic JSON, never a transport message or uninstrumented performance claim.
   */
  inline body_case::Json profile_json(const Profile &profile) {
    body_case::Json stages = body_case::Json::object();
    std::uint64_t observed_ns = 0;
    for (unsigned i = 0; i < stage_names.size(); ++i) {
      const auto &bucket = profile.bucket(static_cast<Stage>(i));
      stages[std::string(stage_names[i])] = {{"nanoseconds", bucket.nanoseconds}, {"calls", bucket.calls}, {"aborted", bucket.aborted}};
      observed_ns += bucket.nanoseconds;
    }
    return {{"scope", "explicit_inner_encoder_wall_clocks_including_observer_overhead"}, {"attempts", profile.attempts}, {"clock_reads", profile.clock_reads}, {"clock_regressions", profile.clock_regressions}, {"observed_stage_ns", observed_ns}, {"clock_overhead_subtracted", false}, {"stages", stages}};
  }
}  // namespace gamebub::v20::encoder
