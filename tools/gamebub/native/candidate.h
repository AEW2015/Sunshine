/**
 * @file tools/gamebub/native/candidate.h
 * @brief Offline mandatory-HUD admission and explicit AR03 candidate ownership.
 * @note The inner GM01/SR01 encoder is injected; this is not a native encoder or endpoint.
 */
#pragma once

// standard includes
#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <utility>

// local includes
#include "body_decoder.h"

namespace gamebub::v20::candidate {
  /** @brief Frozen mandatory-HUD development profile, separate from wire grammar. */
  inline constexpr std::string_view profile_schema = "gamebub-v20-development-profile-v1";
  /** @brief Fixed coded canvas dimensions. */
  inline constexpr unsigned width = 720, height = 480;
  /** @brief Complete AR03 fixed envelope, including final CRC. */
  inline constexpr std::size_t envelope_bytes = 65;

  /** @brief One exact source-canvas rectangle. */
  struct Rect {
    unsigned x, y, width, height;  ///< Bounded rectangle coordinates and extent.
    /** @brief Compare exact source rectangle identity. */
    bool operator==(const Rect &) const = default;
  };

  /** @brief Required exact RGB565 areas, in the frozen development-profile order. */
  inline constexpr std::array<Rect, 4> rectangles {{{22, 54, 160, 24}, {22, 82, 160, 24}, {168, 360, 320, 24}, {168, 390, 240, 24}}};
  /** @brief Base transform ROI areas; these do not detect application HUDs. */
  inline constexpr std::array<Rect, 2> base_regions {{{16, 48, 192, 80}, {160, 352, 400, 80}}};

  /** @brief One bounded ROI/background quantization choice. */
  struct Map {
    unsigned roi, background;  ///< Quantizer scales8,16 or32.
    /** @brief Compare a declared ROI/background map identity. */
    bool operator==(const Map &) const = default;
  };

  /** @brief Only the declared four ordered candidates may be attempted. */
  inline constexpr std::array<Map, 4> maps {{{8, 16}, {8, 32}, {16, 32}, {32, 32}}};

  /** @brief Immutable source snapshot, owned until candidate commit or discard. */
  class Source {
  public:
    /** @brief Capture snapshots cannot be copied by value through an alias. */
    Source(const Source &) = delete;
    /** @brief Moving an aliased snapshot must not empty retained capture storage. */
    Source(Source &&) = delete;
    /** @brief Prevent replacement of pixels through a mutable shared owner. */
    Source &operator=(const Source &) = delete;
    /** @brief Prevent replacement or movement of retained capture storage. */
    Source &operator=(Source &&) = delete;

    /**
     * @brief Copy the exact RGB565 canvas so later capture mutation cannot alter a build.
     * @param words 720x480 row-major original source words.
     * @note Patch-policy fixture mode only: original RGB8 is unavailable. A real base
     * encoder must reject the empty rgb8() span, not expand lossy RGB565 as original pixels.
     */
    explicit Source(std::span<const std::uint16_t> words) {
      body::require(words.size() == width * height, "mandatory source geometry");
      words_.assign(words.begin(), words.end());
    }

    /**
     * @brief Retain exact packed RGB8 and derive the frozen RGB565 patch words.
     * @param rgb8 Exactly720x480x3 row-major bytes in red/green/blue order.
     * @note Bounds are checked before either representation is allocated or copied.
     */
    explicit Source(std::span<const std::uint8_t> rgb8) {
      body::require(rgb8.size() == width * height * 3, "mandatory original RGB8 geometry");
      rgb8_.assign(rgb8.begin(), rgb8.end());
      words_.resize(width * height);
      for (std::size_t i = 0; i < words_.size(); ++i) {
        words_[i] = static_cast<std::uint16_t>(((rgb8_[3 * i] >> 3) << 11) | ((rgb8_[3 * i + 1] >> 2) << 5) | (rgb8_[3 * i + 2] >> 3));
      }
    }

    /** @brief Return immutable source words for patch/base encoders. */
    std::span<const std::uint16_t> words() const {
      return words_;
    }

    /** @brief Return exact owned RGB8, or empty for explicitly RGB565-only patch fixtures. */
    std::span<const std::uint8_t> rgb8() const {
      return rgb8_;
    }

  private:
    std::vector<std::uint16_t> words_;  ///< Owned immutable source pixels.
    std::vector<std::uint8_t> rgb8_;  ///< Original RGB8 bytes; never inferred from RGB565.
  };

  /** @brief One actual paid base attempt, including full-frame validation/discard. */
  struct Attempt {
    Map map;  ///< Declared quantizer selection.
    std::size_t inner_bytes = 0, complete_bytes = 0;  ///< Actual byte counts, never estimates.
    std::uint64_t build_ns = 0, validate_ns = 0, discard_ns = 0;  ///< Measured host work.
    bool accepted = false;  ///< True only for full validated mandatory coverage within cap.
  };

  /** @brief Complete preparation accounting, including losing builds. */
  struct Metrics {
    std::size_t patch_bytes = 0, reserved_inner_bytes = 0;  ///< Framed patches and remaining inner capacity.
    std::uint64_t patch_prepare_ns = 0;  ///< Paid patch encoding and source-word validation.
    std::vector<Attempt> attempts;  ///< At most four paid entries, in declared order.
    std::string reason;  ///< Stable accept/reject category.
  };

  /** @brief Explicit immutable inputs to an injected actual GM01/SR01 builder. */
  struct BuildRequest {
    std::shared_ptr<const Source> source;  ///< Snapshot retained independently of capture.
    std::shared_ptr<const body::Bank> reference;  ///< Exact confirmed predictor or null for a key.
    std::uint32_t epoch, frame_id;  ///< Session/frame identity, not consumed until commit.
    unsigned reference_slot, destination_slot;  ///< 255 means no bank.
    bool key, promoted;  ///< Requested reconstruction/publication behavior.
    Map map;  ///< One declared map to encode now.
  };

  /** @brief Real encoded inner bytes and expected newly reconstructed tag. */
  struct BuildResult {
    std::vector<std::uint8_t> inner;  ///< Complete GM01/SR01 including its own CRC.
    body::Tag stored_tag {};  ///< Nonzero only for a key or promoted reference.
  };

  /** @brief Callback that prepares all requested HP01/HR01 bytes from one source. */
  using PatchBuilder = std::function<std::vector<std::vector<std::uint8_t>>(const Source &)>;
  /** @brief Actual inner encoder boundary; no synthetic throughput claim. */
  using InnerBuilder = std::function<BuildResult(const BuildRequest &)>;

  /** @brief Reader accounting that outlives a policy if an external lease remains. */
  struct BankSlot {
    std::shared_ptr<const body::Bank> bank;  ///< Immutable confirmed sample planes.
    std::size_t readers = 0;  ///< Explicit active/external read owners.
  };

  /** @brief Noncopyable bank lease; destruction releases only its own reader. */
  class Lease {
  public:
    /** @brief A formal reader can have only one balancing release owner. */
    Lease(const Lease &) = delete;
    /** @brief Reader identity cannot be reassigned independently of its counter. */
    Lease &operator=(const Lease &) = delete;

    /** @brief Release the exact retained bank reader, independent of policy lifetime. */
    ~Lease() {
      --slot_->readers;
    }

    /** @brief Access the exact immutable bank protected by this lease. */
    const body::Bank &bank() const {
      return *bank_;
    }

  private:
    friend class Policy;

    /** @brief Increment a confirmed slot's reader count. */
    explicit Lease(std::shared_ptr<BankSlot> slot):
        slot_(std::move(slot)),
        bank_(slot_->bank) {
      ++slot_->readers;
    }

    std::shared_ptr<BankSlot> slot_;  ///< Reader counter owner.
    std::shared_ptr<const body::Bank> bank_;  ///< Exact sample-buffer owner.
  };

  /** @brief Opaque preparation identity; does not prolong source/lease ownership. */
  class Prepared {
  public:
    /** @brief An empty handle represents a whole-frame rejection. */
    Prepared() = default;

    /** @brief True only when the policy retained a candidate for explicit resolution. */
    bool accepted() const {
      return bool(token_);
    }

    /** @brief Return immutable paid-work metrics; not an authority for commit bytes. */
    const Metrics &metrics() const {
      return metrics_;
    }

  private:
    friend class Policy;

    /** @brief Bind the private identity and a metrics snapshot. */
    Prepared(std::shared_ptr<const std::uint64_t> token, Metrics metrics):
        token_(std::move(token)),
        metrics_(std::move(metrics)) {}

    std::shared_ptr<const std::uint64_t> token_;  ///< Identity only, not capture/reader storage.
    Metrics metrics_;  ///< Public reporting copy, never trusted to commit.
  };

  /**
   * @brief Single-owner-thread offline candidate policy with exact reference ACKs.
   * @note Builders may not re-enter policy mutation. This class has no transport or FPGA grants.
   */
  class Policy {
  public:
    /** @brief Fix the epoch/window/profile; an optional lower cap supports measured admission. */
    explicit Policy(std::size_t frame_cap = 49152, std::uint32_t epoch = 1):
        cap_(frame_cap),
        epoch_(epoch) {
      body::require(epoch != 0xffffffffU, "mandatory epoch");
      check_cap(frame_cap);
      for (auto &slot : banks_) {
        slot = std::make_shared<BankSlot>();
      }
    }

    /** @brief Return the last committed ID; rejected/discarded candidates do not burn IDs. */
    std::int64_t last_issued() const {
      return last_issued_;
    }

    /** @brief Return the number of committed transactions awaiting exact AF03 outcome. */
    std::size_t pending() const {
      return pending_.size();
    }

    /** @brief True while explicit commit/discard is required. */
    bool active() const {
      return bool(active_);
    }

    /** @brief Inspect explicit reader count without assuming an external baseline is zero. */
    std::size_t readers(unsigned slot) const {
      return checked_slot(slot)->readers;
    }

    /** @brief Return the current complete-frame cap. */
    std::size_t frame_cap() const {
      return cap_;
    }

    /** @brief Change admission cap; existing preparation becomes stale but remains discardable. */
    void set_frame_cap(std::size_t value) {
      body::require(!building_, "reentrant policy mutation");
      check_cap(value);
      if (value != cap_) {
        cap_ = value;
        ++generation_;
      }
    }

    /**
     * @brief Install a hash-validated offline precondition bank, never a speculative encode result.
     * @param slot Key0 or recent1.
     * @param bank Exact reconstructed samples and identity to copy.
     * @note A confirmed precondition advances the committed-ID lower bound, never backwards.
     */
    void seed_reference(unsigned slot, const body::Bank &bank) {
      body::require(!building_ && !active_ && pending_.empty(), "busy precondition setup");
      auto state = checked_slot(slot);
      body::require(!state->readers && bank.id != 0xffffffffU && bank.tag == body::canonical_tag(bank.planes, width, height), "invalid/read-owned precondition bank");
      state->bank = std::make_shared<const body::Bank>(bank);
      last_issued_ = std::max(last_issued_, static_cast<std::int64_t>(bank.id));
      ++generation_;
    }

    /** @brief Acquire one external immutable predictor lease. */
    std::unique_ptr<Lease> acquire(unsigned slot) {
      body::require(!building_, "reentrant external acquire");
      return acquire_impl(slot);
    }

    /**
     * @brief Encode/validate every exact patch, then build at most four declared base maps.
     * @param source Immutable720x480 capture snapshot.
     * @param frame_id Fresh non-sentinel ID; unchanged on rejected/discarded work.
     * @param patches Actual exact-patch encoder callback.
     * @param builder Actual inner encoder callback; every call is paid and reported.
     * @param force_key Request an independent key.
     * @param promote Request bank1 publication for a P frame.
     * @return Opaque retained candidate or whole-frame rejection and complete metrics.
     */
    Prepared prepare(std::shared_ptr<const Source> source, std::uint32_t frame_id, const PatchBuilder &patches, const InnerBuilder &builder, bool force_key = false, bool promote = false) {
      body::require(!building_ && !active_, "unresolved mandatory candidate");
      body::require(source && patches && builder && frame_id != 0xffffffffU && frame_id > last_issued_, "invalid mandatory source/builder/identity");
      body::require(pending_.size() < 3, "mandatory pending window");
      const bool key = force_key || (!banks_[0]->bank && !banks_[1]->bank);
      const bool promoted = promote && !key;
      const unsigned ref = key ? 255 : (!banks_[0]->bank ? 1 : !banks_[1]->bank                        ? 0 :
                                                             banks_[1]->bank->id > banks_[0]->bank->id ? 1 :
                                                                                                         0);
      const unsigned dest = key ? 0 : promoted ? 1 :
                                                 255;
      body::require(dest == 255 || (!banks_[dest]->readers && !pending_writer() && !pending_consumer(dest)), "mandatory destination busy");
      body::require(ref == 255 || !pending_writer(ref), "mandatory source writer");
      const auto generation = generation_;
      building_ = true;
      try {
        Metrics metrics;
        const auto start = Clock::now();
        const auto encoded = patches(*source);
        body::require(encoded.size() == rectangles.size(), "incomplete mandatory patch count");
        std::vector<std::uint8_t> blob;
        for (std::size_t i = 0; i < encoded.size(); ++i) {
          const auto decoded = body::decode_patch(encoded[i], width, height);
          const auto r = rectangles[i];
          body::require(Rect {decoded.x, decoded.y, decoded.width, decoded.height} == r, "mandatory patch rectangle/order");
          for (unsigned y = 0; y < r.height; ++y) {
            for (unsigned x = 0; x < r.width; ++x) {
              body::require(decoded.words[y * r.width + x] == source->words()[(r.y + y) * width + r.x + x], "mandatory patch changed current source");
            }
          }
          append32(blob, static_cast<std::uint32_t>(encoded[i].size()));
          blob.insert(blob.end(), encoded[i].begin(), encoded[i].end());
        }
        metrics.patch_prepare_ns = elapsed(start);
        metrics.patch_bytes = blob.size();
        if (blob.size() + envelope_bytes + 50 > cap_) {
          metrics.reason = "mandatory_ui_exceeds_complete_cap";
          building_ = false;
          return Prepared({}, std::move(metrics));
        }
        metrics.reserved_inner_bytes = cap_ - envelope_bytes - blob.size();
        for (const auto map : maps) {
          auto lease = ref == 255 ? nullptr : acquire_impl(ref);
          BuildRequest request {source, ref == 255 ? nullptr : banks_[ref]->bank, epoch_, frame_id, ref, dest, key, promoted, map};
          Attempt attempt;
          attempt.map = map;
          const auto began = Clock::now();
          auto built = builder(request);
          attempt.build_ns = elapsed(began);
          attempt.inner_bytes = built.inner.size();
          attempt.complete_bytes = envelope_bytes + built.inner.size() + blob.size();
          if (attempt.complete_bytes <= cap_) {
            const auto validation = Clock::now();
            validate_inner(built.inner, request);
            auto bytes = assemble(request, built, blob);
            // Decode private copies, never the host's read-owned sample banks.
            // Host destination/read ownership is checked independently at commit.
            body::State state;
            state.epoch = epoch_;
            state.last_frame = last_issued_;
            for (unsigned slot = 0; slot < 2; ++slot) {
              if (banks_[slot]->bank) {
                state.banks[slot] = *banks_[slot]->bank;
                state.width = width;
                state.height = height;
              }
            }
            body::Frame decoded;
            std::string error;
            const bool valid = body::decode(bytes, state, decoded, error);
            body::require(valid, error.c_str());
            attempt.validate_ns = elapsed(validation);
            attempt.accepted = true;
            metrics.attempts.push_back(attempt);
            metrics.reason = "mandatory_complete";
            auto token = std::make_shared<const std::uint64_t>(++next_token_);
            active_ = std::make_unique<Active>(Active {token, generation, source, std::move(lease), std::move(bytes), frame_id, ref, dest, dest == 255 ? nullptr : std::make_shared<const body::Bank>(*state.banks[dest])});
            building_ = false;
            return Prepared(std::move(token), std::move(metrics));
          }
          const auto discarded = Clock::now();
          built = {};
          lease.reset();
          attempt.discard_ns = elapsed(discarded);
          metrics.attempts.push_back(attempt);
        }
        metrics.reason = "all_declared_maps_exceed_complete_cap";
        building_ = false;
        return Prepared({}, std::move(metrics));
      } catch (...) {
        building_ = false;
        throw;
      }
    }

    /** @brief Inspect retained private bytes; valid only until commit/discard. */
    const std::vector<std::uint8_t> &packet(const Prepared &prepared) const {
      return owned(prepared).packet;
    }

    /**
     * @brief Consume identity and stage packet/reference expectations without publishing a bank.
     * @param prepared Exact unresolved handle produced by this policy.
     * @return Actual immutable validated AR03 bytes for the transport owner.
     */
    std::vector<std::uint8_t> commit(const Prepared &prepared) {
      body::require(!building_, "reentrant commit");
      auto &a = owned(prepared);
      body::require(a.generation == generation_ && a.packet.size() <= cap_ && a.id > last_issued_ && pending_.size() < 3, "stale mandatory candidate");
      body::require(a.ref == 255 || (banks_[a.ref]->bank && a.lease && &a.lease->bank() == banks_[a.ref]->bank.get()), "stale mandatory reference");
      if (a.dest != 255) {
        body::require(!pending_writer() && !pending_consumer(a.dest) && banks_[a.dest]->readers == (a.ref == a.dest ? 1U : 0U), "candidate destination became busy");
      } else {
        body::require(!pending_writer(a.ref), "candidate source became writer");
      }
      Pending row {a.packet, a.ref, a.dest, a.reconstructed};
      auto bytes = a.packet;
      pending_.emplace(a.id, std::move(row));
      if (a.dest != 255) {
        banks_[a.dest]->bank.reset();
      }
      last_issued_ = a.id;
      ++generation_;
      active_.reset();
      return bytes;
    }

    /** @brief Release only the candidate's capture and reader, even after configuration changes. */
    void discard(const Prepared &prepared) {
      body::require(!building_, "reentrant discard");
      owned(prepared);
      active_.reset();
    }

    /**
     * @brief Accept exact AF03 feedback; only ACK can publish its validated reconstructed bank.
     * @param bytes Complete feedback including CRC.
     * @return False for no matching pending ID, true after exact ACK/NACK resolution.
     */
    bool acknowledge(std::span<const std::uint8_t> bytes) {
      body::require(!building_ && envelope(bytes, true).empty(), "invalid AF03 envelope");
      body::require(le32(bytes, 6) == epoch_ && le32(bytes, 10) != 0xffffffffU, "AF03 epoch/frame");
      const auto found = pending_.find(le32(bytes, 10));
      if (found == pending_.end()) {
        return false;
      }
      const auto &row = found->second;
      body::require(le32(bytes, 14) == le32(row.packet, row.packet.size() - 4), "AF03 wrong outer content");
      const bool stored = bytes[5] == 1 && row.dest != 255;
      const auto expected_id = stored ? found->first : 0xffffffffU;
      const auto expected_tag = stored ? row.reconstructed->tag : body::Tag {};
      body::require(bytes[18] == (stored ? row.dest : 255) && le32(bytes, 19) == expected_id && body::tag_at(bytes, 23) == expected_tag, "AF03 wrong publication");
      if (stored) {
        body::require(!banks_[row.dest]->readers, "AF03 read-owned destination");
        banks_[row.dest]->bank = row.reconstructed;
      }
      pending_.erase(found);
      ++generation_;
      return true;
    }

  private:
    /** @brief One steady host clock; measured work is not throughput evidence. */
    using Clock = std::chrono::steady_clock;

    /** @brief Retained private candidate resources, separate from the public handle. */
    struct Active {
      std::shared_ptr<const std::uint64_t> token;  ///< Exact identity.
      std::uint64_t generation;  ///< Snapshot configuration/publication generation.
      std::shared_ptr<const Source> source;  ///< Capture ownership.
      std::unique_ptr<Lease> lease;  ///< Optional source-bank ownership.
      std::vector<std::uint8_t> packet;  ///< Private immutable commit authority.
      std::uint32_t id;  ///< Prospective identity.
      unsigned ref, dest;  ///< Bank identities.
      std::shared_ptr<const body::Bank> reconstructed;  ///< Private verified expected publication.
    };

    /** @brief Committed transport expectation, never an implicit packet/frame capacity grant. */
    struct Pending {
      std::vector<std::uint8_t> packet;  ///< Exact body/identity for AF03 matching.
      unsigned ref, dest;  ///< Read consumer and prospective writer.
      std::shared_ptr<const body::Bank> reconstructed;  ///< Publish only after exact decoded ACK.
    };

    /** @brief Validate the bounded development cap before changing configuration. */
    static void check_cap(std::size_t cap) {
      body::require(cap >= 115 && cap <= 49152, "mandatory frame cap");
    }

    /** @brief Return elapsed nanoseconds, including losing callback work. */
    static std::uint64_t elapsed(Clock::time_point began) {
      return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - began).count();
    }

    /** @brief Check one of the two confirmed-bank slots. */
    std::shared_ptr<BankSlot> checked_slot(unsigned slot) const {
      body::require(slot < 2, "reference slot");
      return banks_[slot];
    }

    /** @brief Pin a confirmed non-writer bank for one explicit reader. */
    std::unique_ptr<Lease> acquire_impl(unsigned slot) {
      auto state = checked_slot(slot);
      body::require(state->bank && !pending_writer(slot), "unconfirmed/writing reference");
      body::require(banks_[0]->readers + banks_[1]->readers < 3, "mandatory reader limit");
      return std::unique_ptr<Lease>(new Lease(std::move(state)));
    }

    /** @brief Detect an unresolved publication writer, optionally for one slot. */
    bool pending_writer(unsigned slot = 255) const {
      for (const auto &[id, row] : pending_) {
        if (row.dest != 255 && (slot == 255 || row.dest == slot)) {
          return true;
        }
      }
      return false;
    }

    /** @brief Keep a committed reference read alive through its feedback outcome. */
    bool pending_consumer(unsigned slot) const {
      for (const auto &[id, row] : pending_) {
        if (row.ref == slot) {
          return true;
        }
      }
      return false;
    }

    /** @brief Require the exact active object identity, never caller-supplied metrics. */
    Active &owned(const Prepared &prepared) const {
      body::require(active_ && prepared.token_ && active_->token == prepared.token_, "foreign/stale mandatory candidate");
      return *active_;
    }

    /** @brief Append one explicit little-endian framing word. */
    static void append32(std::vector<std::uint8_t> &bytes, std::uint32_t value) {
      const auto start = bytes.size();
      bytes.resize(start + 4);
      body::put32(bytes, start, value);
    }

    /** @brief Validate current identity, fixed geometry and the declared quantizer map. */
    static void validate_inner(std::span<const std::uint8_t> bytes, const BuildRequest &r) {
      body::require(bytes.size() >= 50 && (body::magic(bytes, "GM01") || body::magic(bytes, "SR01")), "mandatory inner type");
      const bool sr = body::magic(bytes, "SR01");
      body::require(bytes[4] == 1 && (bytes[5] == 0 || bytes[5] == 1 || (sr && (bytes[5] == 2 || bytes[5] == 4))) && bool(bytes[5] & 1) == r.key && le32(bytes, 6) == r.epoch && le32(bytes, 10) == r.frame_id && le32(bytes, 14) == (r.key ? 0xffffffffU : r.reference->id), "mandatory inner identity");
      body::require(body::u16(bytes, 18) == width && body::u16(bytes, 20) == height && !body::u16(bytes, 22) && !body::u16(bytes, 24), "mandatory inner geometry/motion");
      constexpr unsigned mw = 45, mh = 30, nmap = (mw * mh + 3) / 4;
      body::require(body::u16(bytes, 26) == mw && body::u16(bytes, 28) == mh && le32(bytes, 30) == nmap && static_cast<std::uint64_t>(46) + nmap + le32(bytes, 34) + le32(bytes, 38) + le32(bytes, 42) + 4 == bytes.size(), "mandatory inner lengths");
      body::check_crc(bytes);
      for (unsigned y = 0; y < mh; ++y) {
        for (unsigned x = 0; x < mw; ++x) {
          unsigned scale = r.map.background;
          for (const auto rect : base_regions) {
            if (x >= rect.x / 16 && x < (rect.x + rect.width + 15) / 16 && y >= rect.y / 16 && y < (rect.y + rect.height + 15) / 16) {
              scale = r.map.roi;
            }
          }
          const unsigned code = scale == 8 ? 0 : scale == 16 ? 1 :
                                                               2;
          const unsigned index = y * mw + x;
          body::require(((bytes[46 + index / 4] >> (6 - 2 * (index % 4))) & 3) == code, "mandatory inner quantizer map");
        }
      }
    }

    /** @brief Build complete AR03 bytes privately with every framed mandatory patch. */
    static std::vector<std::uint8_t> assemble(const BuildRequest &r, const BuildResult &built, std::span<const std::uint8_t> blob) {
      std::vector<std::uint8_t> result(61);
      std::copy_n("AR03", 4, result.begin());
      result[4] = 3;
      result[5] = r.key ? 1 : r.promoted ? 2 :
                                           0;
      body::put32(result, 6, r.epoch);
      body::put32(result, 10, r.frame_id);
      result[14] = r.reference_slot;
      result[15] = r.destination_slot;
      body::put32(result, 16, r.key ? 0xffffffffU : r.reference->id);
      if (r.reference) {
        std::copy(r.reference->tag.begin(), r.reference->tag.end(), result.begin() + 20);
      }
      std::copy(built.stored_tag.begin(), built.stored_tag.end(), result.begin() + 36);
      body::put32(result, 52, built.inner.size());
      result[56] = rectangles.size();
      body::put32(result, 57, blob.size());
      result.insert(result.end(), built.inner.begin(), built.inner.end());
      result.insert(result.end(), blob.begin(), blob.end());
      append32(result, crc32(result));
      return result;
    }

    std::size_t cap_;  ///< Current complete-frame cap.
    std::uint32_t epoch_;  ///< Fixed session; reset/rekey is outside this policy.
    std::int64_t last_issued_ = -1;  ///< Last committed identity.
    std::uint64_t generation_ = 0, next_token_ = 0;  ///< Configuration/publication and opaque handle generations.
    bool building_ = false;  ///< Owner-thread reentrancy guard.
    std::array<std::shared_ptr<BankSlot>, 2> banks_;  ///< Confirmed references and explicit readers.
    std::unique_ptr<Active> active_;  ///< Single unresolved private candidate.
    std::map<std::uint32_t, Pending> pending_;  ///< At most three unresolved transactions.
  };
}  // namespace gamebub::v20::candidate
