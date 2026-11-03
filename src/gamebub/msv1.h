/**
 * @file src/gamebub/msv1.h
 * @brief Experimental MoonBub MSV1 packetization; no transport or codec negotiation.
 */
#pragma once

// standard includes
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace gamebub::msv1 {
  constexpr std::size_t header_size = 40;  ///< Bytes in an MSV1 v1 datagram header.
  constexpr std::size_t max_payload = 1024;  ///< Maximum JPEG bytes per datagram.
  constexpr std::size_t max_frame = 262144;  ///< Receiver's complete JPEG byte bound.

  /**
   * @brief Serialize a bounded JPEG into receiver-compatible MSV1 datagrams.
   *
   * The caller must verify JPEG compatibility and keep the borrowed frame
   * immutable and alive for the lifetime of this object. This class neither
   * sends data nor establishes a session or a Sunshine codec identifier.
   */
  class packetizer_t {
  public:
    /**
     * @brief Prepare a frame and calculate its whole-frame IEEE CRC32.
     *
     * @param frame Borrowed complete JPEG bytes, nonempty and within max_frame.
     * @param frame_id Wrapping unsigned frame identifier.
     * @param capture_us Unix capture timestamp in microseconds.
     * @param chunk_size JPEG bytes per chunk, from 1 through max_payload.
     * @throws std::invalid_argument If frame or chunk limits are invalid.
     */
    packetizer_t(std::span<const std::uint8_t> frame, std::uint32_t frame_id, std::uint64_t capture_us, std::size_t chunk_size = max_payload);

    /**
     * @brief Construct the datagram for an aligned frame offset.
     *
     * @param offset Chunk-aligned byte offset into the frame.
     * @return Header and payload in network byte order.
     * @throws std::invalid_argument If offset is out of bounds or not aligned.
     */
    [[nodiscard]] std::vector<std::uint8_t> packet_at(std::size_t offset) const;

  private:
    std::span<const std::uint8_t> frame_;  ///< Borrowed immutable JPEG frame.
    std::uint32_t frame_id_;  ///< Wrapping sender frame identifier.
    std::uint64_t capture_us_;  ///< Sender's Unix capture timestamp.
    std::size_t chunk_size_;  ///< Maximum data bytes in each datagram.
    std::uint32_t crc_;  ///< IEEE CRC32 of the entire frame.
  };
}  // namespace gamebub::msv1
