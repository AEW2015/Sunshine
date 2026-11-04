/**
 * @file tools/gamebub/native/packet_model.h
 * @brief Bounded deterministic sender packet/frame bookkeeping faults, without a live peer.
 */
#pragma once

// standard includes
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <span>
#include <vector>

// local includes
#include "body_case.h"
#include "packet_ledger.h"

namespace gamebub::v20::packet_model {
  /**
   * @brief Run independent laboratory cases using real packet serializers and sender ledgers.
   * @param rounds Finite independent model cases, from1 through100000.
   * @param seed Nonzero deterministic xorshift seed, not an authentication secret.
   * @return Host bookkeeping counts; no network, real drain or production recovery is proved.
   */
  inline body_case::Json run(unsigned rounds, std::uint32_t seed = 0xb0b2026) {
    namespace wire = transport;
    wire::require(rounds >= 1 && rounds <= 100000 && seed, "packet model rounds1..100000 and nonzero seed");
    const auto began = std::chrono::steady_clock::now();
    const auto original_seed = seed;
    unsigned completed = 0, stopped = 0, unknown = 0, corrupt = 0, stale = 0, rejections = 0;
    unsigned peak_data = 0, peak_mailbox = 0, retained_data = 0;
    for (unsigned round = 0; round < rounds; ++round) {
      seed ^= seed << 13;
      seed ^= seed >> 17;
      seed ^= seed << 5;
      const unsigned pattern = seed & 3;
      // Each case owns a new, independent model. This is not a live peer reset.
      wire::PacketLedger packets;
      wire::SenderFrames frames;
      std::vector<std::uint8_t> payload(5 * wire::payload_cap + 17, static_cast<std::uint8_t>(seed));
      const auto chunks = wire::datagrams(payload, 1, round);
      wire::require(chunks.size() == 6, "packet model fragment shape");
      const auto request = frames.request(round, static_cast<std::uint32_t>(payload.size()), crc32(std::span(payload).first(payload.size() - 4)));
      const auto request_permit = packets.acquire_control();
      wire::require(request && request_permit, "packet model request mailbox");
      peak_mailbox = 1;
      auto grant = *request;
      grant.kind = wire::Kind::grant;
      wire::require(frames.reply(wire::parse_frame(wire::serialize(grant))) && packets.register_frame(grant) && packets.release_control(*request_permit), "packet model external grant");
      wire::require(packets.may_cancel(round), "empty frame cancel eligibility");
      const auto unsent = packets.reserve(chunks.front());
      wire::require(unsent && !packets.may_cancel(round) && packets.cancel_unsent(unsent->token) && packets.may_cancel(round) && !packets.mark_enqueued(unsent->token), "unsent cancellation generation");
      std::vector<wire::Token> active;
      for (unsigned index = 0; index < 5; ++index) {
        const auto outbound = packets.reserve(chunks[index]);
        wire::require(outbound && packets.mark_enqueued(outbound->token), "packet model DATA enqueue");
        const auto decoded = wire::unwrap(outbound->bytes);
        wire::require(decoded.route_crc == outbound->token.route_crc && decoded.chunk.index == index, "packet model wrapped route");
        active.push_back(outbound->token);
      }
      peak_data = std::max(peak_data, packets.owned_data());
      wire::require(packets.owned_data() == 5 && !packets.reserve(chunks.back()) && !packets.may_cancel(round) && !packets.packets_resolved(round), "packet model backpressure");
      const auto receipt = [](const wire::Token &token, bool queried, std::uint8_t status) {
        return wire::PacketCredit {token.slot, queried, token.sequence, status, token.route_crc};
      };
      auto bad = wire::serialize(receipt(active.front(), false, 0));
      bad.back() ^= 1;
      bool rejected_crc = false;
      try {
        wire::parse_credit(bad);
      } catch (const std::invalid_argument &) {
        rejected_crc = true;
      }
      wire::require(rejected_crc && packets.owned_data() == 5, "corrupt receipt mutation");
      ++corrupt;
      auto wrong = receipt(active.front(), false, 0);
      ++wrong.sequence;
      const auto ignored = packets.credit(wire::parse_credit(wire::serialize(wrong)));
      wire::require(!ignored.data_released && !ignored.query_released && packets.owned_data() == 5, "stale receipt mutation");
      ++stale;
      bool last_enqueued = false;
      if (pattern != 0) {
        const auto query = packets.query(active.front());
        wire::require(query && wire::parse_query(wire::serialize(*query)) == *query && packets.mailbox_owned(), "query mailbox identity");
        peak_mailbox = 1;
        if (pattern == 3) {
          // The queried reply is lost. Retain ownership and stop; do not invent recovery.
          packets.stop();
          frames.stop();
          wire::require(packets.stopped() && frames.stopped() && packets.owned_data() == 5 && packets.mailbox_owned() && frames.owned() == 1 && !packets.forget_frame(round) && !packets.acquire_control() && !packets.reserve(chunks.back()) && !packets.query(active.front()), "unknown outcome must stay owned");
          retained_data += packets.owned_data();
          ++stopped;
          continue;
        }
        if (pattern == 1) {
          const auto old = active.front();
          wire::require(packets.credit(receipt(old, false, 0)).data_released && packets.mailbox_owned(), "unqueried DATA credit retains query");
          const auto last = packets.reserve(chunks.back());
          wire::require(last && last->token.sequence != old.sequence && packets.mark_enqueued(last->token), "reuse only returned DATA permit");
          const auto duplicate = packets.credit(receipt(old, false, 0));
          const auto delayed = packets.credit(receipt(old, true, 0));
          wire::require(!duplicate.data_released && delayed.query_released && !delayed.data_released && packets.owned_data() == 5, "late query cannot return reused DATA");
          active.front() = last->token;
          last_enqueued = true;
        } else {
          const auto uncertain = packets.credit(receipt(active.front(), true, 2));
          wire::require(uncertain.unknown && uncertain.query_released && !uncertain.data_released && packets.owned_data() == 5 && !packets.mailbox_owned(), "unknown PC18 retains DATA");
          ++unknown;
        }
      }
      for (std::size_t index = active.size(); index != 0; --index) {
        const auto status = static_cast<std::uint8_t>(pattern == 2 && index == 1 ? 1 : 0);
        const auto result = packets.credit(wire::parse_credit(wire::serialize(receipt(active[index - 1], false, status))));
        wire::require(result.data_released && result.rejected == bool(status), "exact DATA receipt");
        rejections += result.rejected;
      }
      if (!last_enqueued) {
        const auto last = packets.reserve(chunks.back());
        wire::require(last && packets.mark_enqueued(last->token) && packets.credit(receipt(last->token, false, 0)).data_released, "last fragment credit");
      }
      wire::require(packets.packets_resolved(round) && packets.owned_data() == 0 && !packets.mailbox_owned(), "all packet permits returned");
      const auto finish = frames.control(round, wire::Kind::finish);
      const auto finish_permit = packets.acquire_control();
      wire::require(finish && finish_permit, "FINISH requires resolved packets");
      auto finished = *finish;
      finished.kind = wire::Kind::finished;
      wire::require(frames.reply(finished) && packets.release_control(*finish_permit) && frames.owned() == 1, "FINISHED must retain frame storage");
      // Explicit external model event; receipt of packet credits did not prove this drain.
      auto released = finished;
      released.kind = wire::Kind::release;
      wire::require(frames.reply(released) && frames.owned() == 0 && packets.forget_frame(round) && packets.registered_frames() == 0, "modeled external frame RELEASE");
      ++completed;
    }
    const auto wall_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - began).count();
    return {{"scope", "independent_sender_packet_fault_models"}, {"rounds", rounds}, {"seed", original_seed}, {"completed_cases", completed}, {"safe_stopped_cases", stopped}, {"unknown_credit_cases", unknown}, {"corrupt_receipts_rejected", corrupt}, {"stale_receipts_ignored", stale}, {"rejected_packet_receipts", rejections}, {"peak_data_permits", peak_data}, {"peak_control_mailbox", peak_mailbox}, {"stopped_case_retained_data_sum", retained_data}, {"wall_ns", wall_ns}, {"payload_is_valid_codec_frame", false}, {"network_measured", false}, {"physical_drain_proven", false}, {"full_receiver_ownership_proven", false}, {"production_reset_or_recovery_proven", false}, {"hardware_playback", false}};
  }
}  // namespace gamebub::v20::packet_model
