"""@brief Local preparation of the receiver's fixed AV v1 IMA ADPCM profile.

Raw blocks use WAV IMA syntax and product-rounded predictor updates, not a RIFF
header per block. Network framing is supplied separately by av_protocol.py.
Clock stability is not yet measured end-to-end or qualified for drift management.
"""

import argparse
import json
import struct
import wave
from fractions import Fraction
from pathlib import Path

import av

RATE = 48293
BLOCK_BYTES = 512
BLOCK_SAMPLES = 505

# Standard IMA step/index tables; AV v1 requires full-product reconstruction.
STEP_TABLE = tuple(
    int(value)
    for value in [
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "16",
        "17",
        "19",
        "21",
        "23",
        "25",
        "28",
        "31",
        "34",
        "37",
        "41",
        "45",
        "50",
        "55",
        "60",
        "66",
        "73",
        "80",
        "88",
        "97",
        "107",
        "118",
        "130",
        "143",
        "157",
        "173",
        "190",
        "209",
        "230",
        "253",
        "279",
        "307",
        "337",
        "371",
        "408",
        "449",
        "494",
        "544",
        "598",
        "658",
        "724",
        "796",
        "876",
        "963",
        "1060",
        "1166",
        "1282",
        "1411",
        "1552",
        "1707",
        "1878",
        "2066",
        "2272",
        "2499",
        "2749",
        "3024",
        "3327",
        "3660",
        "4026",
        "4428",
        "4871",
        "5358",
        "5894",
        "6484",
        "7132",
        "7845",
        "8630",
        "9493",
        "10442",
        "11487",
        "12635",
        "13899",
        "15289",
        "16818",
        "18500",
        "20350",
        "22385",
        "24623",
        "27086",
        "29794",
        "32767",
    ]
)
INDEX_DELTAS = (-1, -1, -1, -1, 2, 4, 6, 8)


def _advance(predictor, index, code):
    """@brief Reconstruct one nibble with AV v1 product rounding before index update.

    @param predictor Current signed16 predictor.
    @param index Current valid IMA step-table index.
    @param code Four-bit IMA code.
    @return Clamped reconstructed predictor and clamped next index.
    """
    delta = (STEP_TABLE[index] * (2 * (code & 7) + 1)) >> 3
    predictor += -delta if code & 8 else delta
    return max(-32768, min(32767, predictor)), max(0, min(88, index + INDEX_DELTAS[code & 7]))


def validate_block(block):
    """@brief Require one complete stereo IMA WAV block with valid channel headers."""
    if not isinstance(block, bytes) or len(block) != BLOCK_BYTES:
        raise ValueError("Expected one 512-byte IMA ADPCM WAV block")
    for offset in (0, 4):
        if block[offset + 2] > 88 or block[offset + 3]:
            raise ValueError("Invalid IMA step index or reserved header byte")


def wav_bytes(blocks):
    """@brief Wrap complete raw blocks in a diagnostic WAV; never use as a packet header."""
    if not isinstance(blocks, bytes) or not blocks or len(blocks) % BLOCK_BYTES:
        raise ValueError("Expected nonempty complete ADPCM blocks")
    for offset in range(0, len(blocks), BLOCK_BYTES):
        validate_block(blocks[offset : offset + BLOCK_BYTES])
    fmt = struct.pack(
        "<HHIIHHHH",
        0x11,
        2,
        RATE,
        BLOCK_BYTES * RATE // BLOCK_SAMPLES,
        BLOCK_BYTES,
        4,
        2,
        BLOCK_SAMPLES,
    )
    body = (
        b"WAVEfmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"fact"
        + struct.pack("<II", 4, len(blocks) // BLOCK_BYTES * BLOCK_SAMPLES)
        + b"data"
        + struct.pack("<I", len(blocks))
        + blocks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def decode_block(block):
    """@brief Decode a self-contained block with the required AV v1 product rounding.

    @return Exactly 505 interleaved stereo signed little-endian PCM frames.
    """
    validate_block(block)
    channels = []
    for channel in (0, 1):
        predictor, index, _ = struct.unpack_from("<hBB", block, channel * 4)
        samples = [predictor]
        for group in range(63):
            offset = 8 + group * 8 + channel * 4
            for value in block[offset : offset + 4]:
                for code in (value & 15, value >> 4):
                    predictor, index = _advance(predictor, index, code)
                    samples.append(predictor)
        channels.append(samples)
    return struct.pack("<1010h", *(sample for pair in zip(*channels) for sample in pair))


def encode_block(pcm, indices=(0, 0)):
    """@brief Encode exactly505 stereo frames with product-rounded predictor feedback.

    @param pcm Exactly2020 signed16 little-endian, left/right interleaved PCM bytes.
    @param indices Two starting IMA step indices, copied into the block headers.
    @return Independent512-byte block and final per-channel indices for the next block.
    """
    if not isinstance(pcm, bytes) or len(pcm) != BLOCK_SAMPLES * 4:
        raise ValueError("Expected505 complete stereo PCM frames")
    if (
        not isinstance(indices, tuple)
        or len(indices) != 2
        or any(type(index) is not int or not 0 <= index <= 88 for index in indices)
    ):
        raise ValueError("Expected two valid IMA step indices")
    samples = struct.unpack("<1010h", pcm)
    headers, channels, final_indices = [], [], []
    for channel in (0, 1):
        predictor, index = samples[channel], indices[channel]
        headers.append(struct.pack("<hBB", predictor, index, 0))
        codes = []
        for target in samples[channel + 2 :: 2]:
            difference = target - predictor
            magnitude = min(7, abs(difference) * 4 // STEP_TABLE[index])
            code = magnitude | (8 if difference < 0 else 0)
            predictor, index = _advance(predictor, index, code)
            codes.append(code)
        channels.append(codes)
        final_indices.append(index)
    payload = bytearray()
    for group in range(63):
        for codes in channels:
            for position in range(group * 8, group * 8 + 8, 2):
                payload.append(codes[position] | (codes[position + 1] << 4))
    return b"".join(headers) + bytes(payload), tuple(final_indices)


class AudioEncoder:
    """@brief Resample stereo/mono PCM to fixed-size independently decodable blocks."""

    def __init__(self, source_rate=48000, channels=2):
        """@brief Configure explicit source format and product-rounded block reconstruction."""
        if type(source_rate) is not int or not 8000 <= source_rate <= 192000:
            raise ValueError("Invalid source sample rate")
        if type(channels) is not int or channels not in (1, 2):
            raise ValueError("Capture must supply mono or stereo PCM")
        self.source_rate, self.channels = source_rate, channels
        self.source_frames = self.blocks = 0
        self.finished = False
        self.resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
        self.fifo = av.AudioFifo()
        self.indices = (0, 0)

    def _packets(self, frames):
        """@brief Queue resampled frames and encode only complete blocks."""
        blocks = []
        for frame in frames:
            self.fifo.write(frame)
        while self.fifo.samples >= BLOCK_SAMPLES:
            frame = self.fifo.read(BLOCK_SAMPLES)
            block, self.indices = encode_block(
                bytes(frame.planes[0])[: BLOCK_SAMPLES * 4], self.indices
            )
            blocks.append(block)
            self.blocks += 1
        return blocks

    def push(self, pcm):
        """@brief Accept at most one second of packed source PCM; return complete blocks."""
        if self.finished:
            raise RuntimeError("Audio encoder has been finished")
        if (
            not isinstance(pcm, bytes)
            or not pcm
            or len(pcm) % (2 * self.channels)
            or len(pcm) > self.source_rate * self.channels * 2
        ):
            raise ValueError("Expected complete bounded source PCM frames")
        samples = len(pcm) // (2 * self.channels)
        frame = av.AudioFrame(
            format="s16", layout="mono" if self.channels == 1 else "stereo", samples=samples
        )
        frame.planes[0].update(pcm)
        frame.sample_rate = self.source_rate
        frame.time_base = Fraction(1, self.source_rate)
        frame.pts = self.source_frames
        self.source_frames += samples
        return self._packets(self.resampler.resample(frame))

    def finish(self):
        """@brief Drain resampling; report and discard a sub-block tail without padding.

        @return Final complete blocks and the dropped tail's stereo sample-frame count.
        """
        if self.finished:
            raise RuntimeError("Audio encoder has been finished")
        self.finished = True
        blocks = self._packets(self.resampler.resample(None))
        tail = self.fifo.samples
        return blocks, tail


def convert(source, output):
    """@brief Convert a bounded PCM WAV diagnostic to a new ADPCM WAV and validate blocks."""
    with wave.open(str(source), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getnframes() > wav.getframerate() * 60:
            raise ValueError("Expected at most sixty seconds of signed 16-bit PCM")
        encoder = AudioEncoder(wav.getframerate(), wav.getnchannels())
        blocks = []
        while pcm := wav.readframes(1024):
            blocks.extend(encoder.push(pcm))
        final, tail = encoder.finish()
        blocks.extend(final)
    for block in blocks:
        decode_block(block)
    with Path(output).open("xb") as file:
        file.write(wav_bytes(b"".join(blocks)))
    return {
        "scope": "local AV v1 product-rounded encode/decode; not receiver playback",
        "rate": RATE,
        "channels": 2,
        "block_bytes": BLOCK_BYTES,
        "samples_per_block": BLOCK_SAMPLES,
        "blocks": len(blocks),
        "source_frames": encoder.source_frames,
        "discarded_tail_frames": tail,
        "decoded_frames": len(blocks) * BLOCK_SAMPLES,
        "payload_bitrate": BLOCK_BYTES * 8 * RATE / BLOCK_SAMPLES,
    }


def main(argv=None):
    """@brief Encode and check a local capture; this command never sends packets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(convert(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
