/**
 * @file tools/gamebub/native/transport_case.h
 * @brief Pinned laboratory wire replay without inferred receiver drain or live transport.
 */
#pragma once

// local includes
#include "body_case.h"
#include "transport.h"

namespace gamebub::v20::transport_case {
  /**
   * @brief Decode bounded lowercase hexadecimal from the pinned offline contract.
   * @param text Hexadecimal source bytes, never an executable instruction.
   * @return Owned decoded bytes; malformed encoding throws.
   */
  inline std::vector<std::uint8_t> unhex(const std::string &text) {
    body::require(text.size() <= 2 * transport::frame_cap && text.size() % 2 == 0, "contract hex size");
    const auto digit = [](char value) -> unsigned {
      if (value >= '0' && value <= '9') {
        return value - '0';
      }
      if (value >= 'a' && value <= 'f') {
        return value - 'a' + 10;
      }
      throw std::invalid_argument("contract lowercase hex");
    };
    std::vector<std::uint8_t> bytes;
    bytes.reserve(text.size() / 2);
    for (std::size_t i = 0; i < text.size(); i += 2) {
      bytes.push_back(static_cast<std::uint8_t>((digit(text[i]) << 4) | digit(text[i + 1])));
    }
    return bytes;
  }

  /**
   * @brief Require that a corrupted or truncated FG19 packet is rejected.
   * @param packet Private invalid bytes; golden inputs remain unchanged.
   */
  inline void rejects_frame(std::span<const std::uint8_t> packet) {
    try {
      transport::parse_frame(packet);
    } catch (const std::invalid_argument &) {
      return;
    }
    throw std::invalid_argument("native accepted corrupt frame control");
  }

  /**
   * @brief Verify all frozen FG19 bytes and representative packet-credit/fragment examples.
   * @param path Exact wire-contract.json exported by the existing pinned fixture tool.
   * @return Software wire conformance counts, explicitly excluding ownership/hardware proof.
   */
  inline body_case::Json run(const std::filesystem::path &path) {
    using body_case::number;
    const auto raw = body_case::read_file(path, 1024 * 1024);
    const auto hash = body_case::digest(raw);
    body::require(hash == "02a1655a56ac886ffad157753f07f8214325473f26b0227e2c17a3af4f42b0b7", "pinned transport contract hash");
    const auto contract = body_case::Json::parse(raw);
    body::require(contract.at("schema") == "gamebub-v20-lab-wire-contract-v1", "transport contract schema");
    const auto &sequences = contract.at("frame_control_sequences");
    body::require(sequences.is_array() && sequences.size() == 9, "transport history count");
    unsigned messages = 0, negatives = 0;
    for (const auto &sequence : sequences) {
      for (const auto &event : sequence.at("events")) {
        const auto bytes = unhex(event.at("wire_hex"));
        body::require(body_case::digest(bytes) == event.at("wire_sha256").get<std::string>(), "control vector hash");
        const auto value = transport::parse_frame(bytes);
        const auto &expected = event.at("parsed");
        body::require(static_cast<unsigned>(value.kind) == number(expected.at("kind"), 8) && value.slot == number(expected.at("slot"), 65535) && value.epoch == number(expected.at("epoch"), 0xffffffffU) && value.frame == number(expected.at("frame"), 0xffffffffU) && value.sequence == number(expected.at("seq"), 0xffffffffffffffffULL) && value.total == number(expected.at("total"), transport::frame_cap) && value.content_crc == number(expected.at("crc"), 0xffffffffU), "parsed frame control mismatch");
        body::require(transport::serialize(value) == bytes, "serialized frame control mismatch");
        auto corrupted = bytes;
        corrupted[28] ^= 1;
        rejects_frame(corrupted);
        rejects_frame(std::span(bytes).first(bytes.size() - 1));
        ++messages;
        negatives += 2;
      }
    }
    body::require(messages == 1725, "transport message count");
    const auto &example = contract.at("packet_example");
    const auto credit = unhex(example.at("pc18_hex"));
    const auto query = unhex(example.at("qc18_hex"));
    body::require(transport::serialize(transport::parse_credit(credit)) == credit, "PC18 golden mismatch");
    body::require(transport::serialize(transport::parse_query(query)) == query, "QC18 golden mismatch");
    const auto ar03 = unhex(example.at("ar03_packet_hex"));
    body::require(body_case::digest(ar03) == example.at("ar03_sha256").get<std::string>(), "example AR03 hash");
    const auto wrapped = unhex(example.at("wrapped_first_gf03_hex"));
    const auto decoded = transport::unwrap(wrapped);
    const auto chunks = transport::datagrams(ar03, decoded.chunk.epoch, decoded.chunk.frame);
    body::require(!chunks.empty() && transport::wrap(chunks.front(), decoded.slot, decoded.sequence) == wrapped, "wrapped GF03 golden mismatch");
    std::vector<std::uint8_t> assembled;
    for (const auto &packet : chunks) {
      const auto chunk = transport::parse_chunk(packet);
      assembled.insert(assembled.end(), chunk.payload.begin(), chunk.payload.end());
    }
    body::require(assembled == ar03, "GF03 fragment roundtrip");
    return {{"scope", "pinned_transport_wire_only"}, {"contract_sha256", hash}, {"history_count", sequences.size()}, {"fg19_messages", messages}, {"corruption_truncation_rejections", negatives}, {"pc18_examples", 1}, {"qc18_examples", 1}, {"gf03_fragments", chunks.size()}, {"ownership_proven", false}, {"hardware_playback", false}};
  }
}  // namespace gamebub::v20::transport_case
