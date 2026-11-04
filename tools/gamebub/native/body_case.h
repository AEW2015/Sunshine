/**
 * @file tools/gamebub/native/body_case.h
 * @brief Offline pinned-fixture replay; JSON is a test format, never a wire codec.
 */
#pragma once

// standard includes
#include <filesystem>
#include <fstream>
#include <string>

// lib includes
#include <nlohmann/json.hpp>

// local includes
#include "body_decoder.h"

namespace gamebub::v20::body_case {
  /** @brief Fixture metadata, parsed with a bounded local JSON dependency. */
  using Json = nlohmann::json;

  /**
   * @brief Read an explicitly bounded file with exact-length I/O checks.
   * @param path Existing fixture file.
   * @param limit Maximum allowed allocation.
   * @return Bytes; malformed or unreadable files throw before replay.
   */
  inline std::vector<std::uint8_t> read_file(const std::filesystem::path &path, std::size_t limit) {
    const auto size = std::filesystem::file_size(path);
    body::require(size <= limit, "fixture allocation bound");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    std::ifstream input(path, std::ios::binary);
    input.read(reinterpret_cast<char *>(bytes.data()), bytes.size());
    body::require(input && input.gcount() == static_cast<std::streamsize>(bytes.size()), "fixture read");
    return bytes;
  }

  /** @brief Parse a nonnegative bounded JSON integer without signed wrap. */
  inline std::uint64_t number(const Json &value, std::uint64_t limit) {
    body::require(value.is_number_integer(), "fixture integer type");
    if (!value.is_number_unsigned()) {
      body::require(value.get<std::int64_t>() >= 0, "negative fixture integer");
    }
    const auto result = value.get<std::uint64_t>();
    body::require(result <= limit, "fixture integer bound");
    return result;
  }

  /** @brief Calculate a lower-case file SHA256 without changing bytes. */
  inline std::string digest(std::span<const std::uint8_t> bytes) {
    std::array<unsigned char, SHA256_DIGEST_LENGTH> hash {};
    body::require(SHA256(bytes.data(), bytes.size(), hash.data()) != nullptr, "fixture SHA256");
    std::string text;
    for (auto byte : hash) {
      text += "0123456789abcdef"[byte >> 4];
      text += "0123456789abcdef"[byte & 15];
    }
    return text;
  }

  /** @brief Resolve a canonical descendant path, rejecting traversal and symlink escapes. */
  inline std::filesystem::path relative_file(const std::filesystem::path &base, const std::string &name) {
    body::require(!name.empty() && name.find_first_of("\\:\0", 0, 3) == std::string::npos, "fixture path encoding");
    const std::filesystem::path relative(name);
    body::require(!relative.is_absolute() && !relative.has_root_name() && relative.generic_string() == name, "fixture relative path");
    for (const auto &part : relative) {
      body::require(part != "." && part != ".." && !part.empty(), "fixture path traversal");
    }
    const auto root = std::filesystem::canonical(base);
    const auto target = std::filesystem::canonical(root / relative);
    const auto confined = target.lexically_relative(root);
    body::require(!confined.empty() && *confined.begin() != ".." && std::filesystem::is_regular_file(target), "fixture path escape");
    return target;
  }

  /** @brief Load a hash-bound descriptor with a caller-specified exact byte count. */
  inline std::vector<std::uint8_t> blob(const std::filesystem::path &base, const Json &descriptor, std::size_t size) {
    body::require(number(descriptor.at("bytes"), 4 * 1024 * 1024) == size, "fixture byte count");
    auto raw = read_file(relative_file(base, descriptor.at("path").get<std::string>()), size);
    body::require(raw.size() == size && digest(raw) == descriptor.at("sha256").get<std::string>(), "fixture size/hash");
    return raw;
  }

  /** @brief Require the exact published portable array dtype and dimensions. */
  inline void shape(const Json &descriptor, std::string_view dtype, std::initializer_list<unsigned> dimensions) {
    body::require(descriptor.at("dtype") == dtype && descriptor.at("shape") == Json(dimensions), "fixture dtype/shape");
  }

  /** @brief Load three canonical signed16 LE planes and reject illegal samples. */
  inline body::Planes planes(const std::filesystem::path &base, const Json &descriptors, unsigned width, unsigned height) {
    body::require(descriptors.is_array() && descriptors.size() == 3, "fixture plane count");
    body::Planes result;
    for (unsigned p = 0; p < 3; ++p) {
      const unsigned w = p ? width / 2 : width, h = p ? height / 2 : height;
      shape(descriptors[p], "<i2", {h, w});
      const auto raw = blob(base, descriptors[p], w * h * 2);
      result[p].reserve(w * h);
      for (std::size_t i = 0; i < raw.size(); i += 2) {
        const auto sample = body::u16(raw, i);
        body::require(sample <= 255, "fixture sample domain");
        result[p].push_back(static_cast<std::int16_t>(sample));
      }
    }
    return result;
  }

  /** @brief Parse the exact canonical16-byte tag, allowing no alternate spelling. */
  inline body::Tag tag(const Json &value) {
    const auto text = value.get<std::string>();
    body::require(text.size() == 32, "fixture tag size");
    body::Tag result {};
    for (unsigned i = 0; i < 32; ++i) {
      const auto digit = std::string_view("0123456789abcdef").find(text[i]);
      body::require(digit != std::string_view::npos, "fixture tag digit");
      result[i / 2] |= static_cast<std::uint8_t>(digit << ((i % 2) ? 0 : 4));
    }
    return result;
  }

  /**
   * @brief Decode one isolated fixture and compare all frozen output/state oracles.
   * @param path Case JSON; adjacent descriptors contain raw arrays with hashes.
   * @return Scoped report. A decoded-result mismatch throws; no hardware is touched.
   */
  inline Json run(const std::filesystem::path &path) {
    const auto json_bytes = read_file(path, 1024 * 1024);
    const auto metadata = Json::parse(json_bytes);
    body::require(metadata.at("schema") == "gamebub-v20-body-case-v1", "body fixture schema");
    const auto base = path.parent_path();
    const auto width = static_cast<unsigned>(number(metadata.at("geometry").at("width"), 720));
    const auto height = static_cast<unsigned>(number(metadata.at("geometry").at("height"), 480));
    body::require(width && height && width % 2 == 0 && height % 2 == 0, "body fixture geometry");
    const auto id = number(metadata.at("id"), 0xfffffffeU);
    body::State state;
    state.epoch = static_cast<std::uint32_t>(number(metadata.at("epoch"), 0xfffffffeU));
    body::require(metadata.at("last_frame").is_number_integer(), "fixture last frame type");
    state.last_frame = metadata.at("last_frame").is_number_unsigned() ?
                         static_cast<std::int64_t>(number(metadata.at("last_frame"), 0xfffffffeU)) :
                         metadata.at("last_frame").get<std::int64_t>();
    body::require(state.last_frame >= -1 && state.last_frame < 0xffffffffLL, "fixture last frame bound");
    for (unsigned i = 0; i < 2; ++i) {
      const auto &bank = metadata.at("pre_banks").at(std::to_string(i));
      if (!bank.is_null()) {
        const auto bank_id = static_cast<std::uint32_t>(number(bank.at("id"), 0xfffffffeU));
        auto data = planes(base, bank.at("planes"), width, height);
        const auto identity = tag(bank.at("tag"));
        body::require(body::canonical_tag(data, width, height) == identity, "prebank tag mismatch");
        state.banks[i] = body::Bank {bank_id, identity, std::move(data)};
        state.width = width;
        state.height = height;
      }
    }
    const auto before = state;
    const auto packet_bytes = static_cast<std::size_t>(number(metadata.at("packet").at("bytes"), 49152));
    const auto packet = blob(base, metadata.at("packet"), packet_bytes);
    const auto expected = planes(base, metadata.at("decoded_yuv"), width, height);
    shape(metadata.at("display_rgb565"), "<u2", {height, width});
    const auto display = blob(base, metadata.at("display_rgb565"), width * height * 2);
    const auto ack = blob(base, metadata.at("ack"), 43);
    shape(metadata.at("source_rgb"), "|u1", {height, width, 3});
    const auto source = blob(base, metadata.at("source_rgb"), width * height * 3);
    body::Frame frame;
    std::string error;
    const auto decoded = body::decode(packet, state, frame, error);
    body::require(decoded, ("body decode: " + error).c_str());
    body::require(frame.width == width && frame.height == height && frame.id == id && frame.planes == expected, "decoded YUV/identity mismatch");
    body::require(frame.display565.size() == width * height, "display size mismatch");
    for (std::size_t i = 0; i < frame.display565.size(); ++i) {
      body::require(frame.display565[i] == body::u16(display, i * 2), "display RGB565 mismatch");
    }
    body::require(std::equal(frame.feedback.begin(), frame.feedback.end(), ack.begin()), "AF03 bytes mismatch");
    body::require(state.last_frame == static_cast<std::int64_t>(id) && state.width == width && state.height == height && state.readers == before.readers, "publication metadata mismatch");
    for (unsigned i = 0; i < 2; ++i) {
      const auto &bank = metadata.at("post_banks").at(std::to_string(i));
      if (bank.is_null()) {
        body::require(!state.banks[i], "unexpected bank publication");
      } else {
        body::require(state.banks[i].has_value(), "missing bank publication");
        body::require(state.banks[i]->id == number(bank.at("id"), 0xfffffffeU) && state.banks[i]->tag == tag(bank.at("tag")), "bank identity mismatch");
        if (packet[15] == i) {
          body::require(state.banks[i]->planes == expected, "published bank pixels mismatch");
        } else {
          body::require(state.banks[i] == before.banks[i], "unwritten bank changed");
        }
      }
    }
    std::size_t hud_words = 0;
    if (metadata.at("policy") == "mandatory") {
      constexpr unsigned regions[4][4] = {{22, 54, 160, 24}, {22, 82, 160, 24}, {168, 360, 320, 24}, {168, 390, 240, 24}};
      for (const auto &region : regions) {
        body::require(region[0] + region[2] <= width && region[1] + region[3] <= height, "mandatory region geometry");
        for (unsigned y = region[1]; y < region[1] + region[3]; ++y) {
          for (unsigned x = region[0]; x < region[0] + region[2]; ++x) {
            const auto index = y * width + x;
            const auto word = static_cast<std::uint16_t>(((source[index * 3] >> 3) << 11) | ((source[index * 3 + 1] >> 2) << 5) | (source[index * 3 + 2] >> 3));
            body::require(frame.display565[index] == word, "mandatory source HUD mismatch");
            ++hud_words;
          }
        }
      }
    }
    return {{"scope", "full_body_fixture"}, {"label", metadata.at("label")}, {"id", id}, {"inner_magic", std::string(packet.begin() + 61, packet.begin() + 65)}, {"key", packet[5] == 1}, {"promoted", packet[5] == 2}, {"yuv_samples", width * height * 3 / 2}, {"display_words", width * height}, {"mandatory_hud_words_verified", hud_words}, {"af03_exact", true}, {"post_banks_exact", true}};
  }
}  // namespace gamebub::v20::body_case
