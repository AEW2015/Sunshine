/**
 * @file tools/gamebub/native/recovery_case.h
 * @brief Offline RS24 byte conformance, without executing reset or negotiating a live profile.
 */
#pragma once

// local includes
#include "recovery_wire.h"
#include "transport_case.h"

namespace gamebub::v24::recovery_case {
  /**
   * @brief Replay all control bytes from the pinned MoonBub v24 result artifact.
   * @param path Unmodified results.json from MoonBub commit 4025d355.
   * @return Wire-only results; delivery flags do not constitute state-machine replay.
   */
  inline v20::body_case::Json run(const std::filesystem::path &path) {
    const auto raw = v20::body_case::read_file(path, 256 * 1024);
    const auto hash = v20::body_case::digest(raw);
    v20::body::require(hash == "93f91047a7b2ae82e866ac35de54d673ca228fa7331ea3d39fc3a62699dec802", "pinned RS24 results hash");
    const auto document = v20::body_case::Json::parse(raw);
    unsigned messages = 0, negatives = 0;
    const auto replay = [&](const auto &trace) {
      for (const auto &event : trace) {
        const auto bytes = v20::transport_case::unhex(event.at("bytes"));
        const auto parsed = recovery::parse(bytes);
        v20::body::require(static_cast<unsigned>(parsed.kind) == event.at("kind").template get<unsigned>(), "RS24 vector kind");
        const auto encoded = recovery::serialize(parsed);
        v20::body::require(std::equal(encoded.begin(), encoded.end(), bytes.begin(), bytes.end()), "RS24 vector serialization");
        for (std::size_t i = 0; i < bytes.size(); ++i) {
          auto corrupted = bytes;
          corrupted[i] ^= 1;
          bool rejected = false;
          try {
            recovery::parse(corrupted);
          } catch (const std::invalid_argument &) {
            rejected = true;
          }
          v20::body::require(rejected, "RS24 accepted bit corruption");
          ++negatives;
        }
        ++messages;
      }
    };
    const auto &results = document.at("results");
    for (const auto &campaign : results.at("cases")) {
      replay(campaign.at("trace"));
    }
    for (const auto &trace : results.at("reboot_sequence").at("traces")) {
      replay(trace);
    }
    v20::body::require(messages == 124 && negatives == 5704, "RS24 frozen vector count");
    return {{"scope", "pinned_rs24_wire_only"}, {"source_commit", "4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189"}, {"results_sha256", hash}, {"messages", messages}, {"corruption_rejections", negatives}, {"state_replayed", false}, {"physical_drain_proven", false}, {"live_profile_negotiated", false}, {"hardware_playback", false}};
  }
}  // namespace gamebub::v24::recovery_case
