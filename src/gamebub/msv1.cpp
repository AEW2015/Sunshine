/**
 * @file src/gamebub/msv1.cpp
 * @brief Experimental bounded MSV1 packet serialization.
 */
// standard includes
#include <algorithm>
#include <stdexcept>

// lib includes
#include <boost/crc.hpp>

// local includes
#include "msv1.h"

namespace gamebub::msv1 {
  namespace {
    /**
     * @brief Append an unsigned integer in network byte order.
     * @param output Destination buffer.
     * @param value Integer value to serialize.
     * @param bytes Number of low-order bytes to append.
     */
    void append_be(std::vector<std::uint8_t> &output, std::uint64_t value, std::size_t bytes) {
      for (std::size_t index = bytes; index > 0; --index) {
        output.push_back(static_cast<std::uint8_t>(value >> ((index - 1) * 8)));
      }
    }
  }  // namespace

  packetizer_t::packetizer_t(std::span<const std::uint8_t> frame, std::uint32_t frame_id, std::uint64_t capture_us, std::size_t chunk_size):
      frame_ {frame},
      frame_id_ {frame_id},
      capture_us_ {capture_us},
      chunk_size_ {chunk_size},
      crc_ {0} {
    if (frame.empty() || frame.size() > max_frame || chunk_size == 0 || chunk_size > max_payload) {
      throw std::invalid_argument {"Invalid MSV1 frame or chunk size"};
    }
    boost::crc_32_type checksum;
    checksum.process_bytes(frame.data(), frame.size());
    crc_ = checksum.checksum();
  }

  std::vector<std::uint8_t> packetizer_t::packet_at(std::size_t offset) const {
    if (offset >= frame_.size() || offset % chunk_size_ != 0) {
      throw std::invalid_argument {"Invalid MSV1 chunk offset"};
    }
    const auto length = std::min(chunk_size_, frame_.size() - offset);
    const auto flags = (offset == 0 ? 1U : 0U) | (offset + length == frame_.size() ? 2U : 0U);
    std::vector<std::uint8_t> packet;
    packet.reserve(header_size + length);
    packet.insert(packet.end(), {'M', 'S', 'V', '1', 1, 1});
    append_be(packet, flags, 2);
    append_be(packet, frame_id_, 4);
    append_be(packet, 720, 2);
    append_be(packet, 480, 2);
    append_be(packet, frame_.size(), 4);
    append_be(packet, offset, 4);
    append_be(packet, length, 2);
    append_be(packet, 0, 2);
    append_be(packet, crc_, 4);
    append_be(packet, capture_us_, 8);
    packet.insert(packet.end(), frame_.begin() + offset, frame_.begin() + offset + length);
    return packet;
  }
}  // namespace gamebub::msv1
