/**
 * @file tools/gamebub/native/recovery_replay.h
 * @brief Frozen RS24 host-control replay with explicitly modeled clear-owner evidence.
 */
#pragma once

// local includes
#include "recovery_host.h"
#include "transport_case.h"

namespace gamebub::v24::recovery_replay {
  /**
   * @brief Count observations of a bounded frozen control replay.
   * @note These are host-control observations, never measurements of native receiver drain.
   */
  struct Counts {
    unsigned controls {};  ///< All emitted controls, including modeled loss.
    unsigned accepted_replies {};  ///< Delivered replies accepted by the native host model.
    unsigned retry_calls {};  ///< Loss-triggered retries, including bounded exhaustion.
    unsigned safe_stops {};  ///< Exhaustions that leave host data blocked.
  };

  /**
   * @brief Replay a single frozen handshake, checking every request and host transition.
   * @param trace Frozen direction/kind/bytes/delivered observations.
   * @param ledger Explicit model ledger shared only across the reboot campaign.
   * @param expected_terminal Independently published terminal host phase.
   * @param counts Accumulated observations, excluding any receiver implementation.
   */
  inline void campaign(const v20::body_case::Json &trace, recovery::EpochLedger &ledger, std::string_view expected_terminal, Counts &counts) {
    v20::body::require(trace.is_array() && !trace.empty() && trace.size() <= 64, "bounded RS24 campaign");
    const auto first = recovery::parse(v20::transport_case::unhex(trace.at(0).at("bytes")));
    recovery::Host host(first.host_nonce, ledger);
    recovery::DrainEvidence modeled_clear;
    modeled_clear.transport_drained = true;
    host.start(modeled_clear);
    for (std::size_t index = 0; index < trace.size(); ++index) {
      const auto &event = trace.at(index);
      const auto bytes = v20::transport_case::unhex(event.at("bytes"));
      const auto parsed = recovery::parse(bytes);
      v20::body::require(static_cast<unsigned>(parsed.kind) == event.at("kind").get<unsigned>(), "RS24 replay kind");
      const auto direction = event.at("direction").get<std::string>();
      if (direction == "forward") {
        v20::body::require(host.outstanding().has_value() && std::equal(host.outstanding()->begin(), host.outstanding()->end(), bytes.begin(), bytes.end()), "RS24 outstanding bytes mismatch");
        const auto expected_phase = parsed.kind == recovery::Kind::hello ? "HELLO" : parsed.kind == recovery::Kind::offer ? "OFFER" :
                                                                                   parsed.kind == recovery::Kind::commit  ? "COMMIT" :
                                                                                                                            "GO";
        v20::body::require(host.phase_name() == expected_phase, "RS24 request phase");
      } else {
        v20::body::require(direction == "reverse", "RS24 direction");
      }
      ++counts.controls;
      if (!event.at("delivered").get<bool>()) {
        ++counts.retry_calls;
        try {
          host.retry();
        } catch (const std::invalid_argument &) {
          v20::body::require(index + 1 == trace.size() && expected_terminal == "SAFE_STOP" && host.phase_name() == "SAFE_STOP" && !host.data_allowed(), "RS24 unexpected retry failure");
          ++counts.safe_stops;
        }
      } else if (direction == "reverse") {
        host.accept(bytes, modeled_clear);
        const auto expected_phase = parsed.kind == recovery::Kind::hello_reply ? "OFFER" : parsed.kind == recovery::Kind::ready   ? "COMMIT" :
                                                                                         parsed.kind == recovery::Kind::committed ? "GO" :
                                                                                                                                    "RUNNING";
        v20::body::require(host.phase_name() == expected_phase, "RS24 reply phase");
        ++counts.accepted_replies;
      }
    }
    v20::body::require(host.phase_name() == expected_terminal && host.data_allowed() == (expected_terminal == "RUNNING"), "RS24 terminal host gate");
  }

  /**
   * @brief Replay the pinned v24 host handshake/loss/reboot campaigns without sockets.
   * @param path Exact published results.json blob from MoonBub4025d355.
   * @return Host-control results with receiver, media and physical-drain claims disabled.
   */
  inline v20::body_case::Json run(const std::filesystem::path &path) {
    const auto raw = v20::body_case::read_file(path, 256 * 1024);
    const auto hash = v20::body_case::digest(raw);
    v20::body::require(hash == "93f91047a7b2ae82e866ac35de54d673ca228fa7331ea3d39fc3a62699dec802", "pinned RS24 results hash");
    const auto document = v20::body_case::Json::parse(raw);
    Counts counts;
    for (const auto &entry : document.at("results").at("cases")) {
      recovery::EpochLedger ledger;
      campaign(entry.at("trace"), ledger, entry.at("host_phase").get<std::string>(), counts);
    }
    recovery::EpochLedger reboot_ledger;
    for (const auto &trace : document.at("results").at("reboot_sequence").at("traces")) {
      campaign(trace, reboot_ledger, "RUNNING", counts);
    }
    v20::body::require(counts.controls == 124 && counts.accepted_replies == 51 && counts.retry_calls == 13 && counts.safe_stops == 1 && reboot_ledger.last() == 3, "RS24 replay counts");
    return {{"scope", "pinned_rs24_host_control_replay"}, {"results_sha256", hash}, {"campaigns", 13}, {"controls", counts.controls}, {"accepted_replies", counts.accepted_replies}, {"retry_calls", counts.retry_calls}, {"safe_stops", counts.safe_stops}, {"last_reboot_epoch", reboot_ledger.last()}, {"host_control_replayed", true}, {"drain_input", "explicitly modeled clear owners"}, {"receiver_state_replayed", false}, {"media_reset_replayed", false}, {"physical_drain_proven", false}, {"hardware_playback", false}};
  }
}  // namespace gamebub::v24::recovery_replay
