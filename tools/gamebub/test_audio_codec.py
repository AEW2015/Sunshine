"""@brief Regression tests for proposed audio blocks and local preparation."""

import runpy
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import audio_codec as codec
from windows_audio import test_tone as tone


class AudioCodecTests(unittest.TestCase):
    """@brief Exercise actual block syntax, independent decoding and source clocks."""

    def test_exact_blocks_and_loss_recovery(self):
        """@brief Dropping an earlier packet cannot change later block reconstruction."""
        encoder = codec.AudioEncoder(codec.RATE)
        blocks = encoder.push(tone(505 * 5, codec.RATE))
        final, tail = encoder.finish()
        blocks.extend(final)
        self.assertEqual((len(blocks), tail), (5, 0))
        self.assertTrue(all(len(x) == 512 for x in blocks))
        standalone = codec.decode_block(blocks[4])
        self.assertEqual(len(standalone), 2020)
        for block in blocks[:4]:
            codec.decode_block(block)
        self.assertEqual(codec.decode_block(blocks[4]), standalone)
        self.assertNotEqual(standalone[0:2], standalone[2:4])
        with self.assertRaises(RuntimeError):
            encoder.push(bytes(4))
        with self.assertRaises(RuntimeError):
            encoder.finish()

    def test_source_resampling_and_mono(self):
        """@brief Continuous source PTS survives resampling and sub-block tails are explicit."""
        encoder = codec.AudioEncoder(48000, 1)
        blocks = []
        for _ in range(10):
            blocks.extend(encoder.push(bytes(480 * 2)))
        final, tail = encoder.finish()
        blocks.extend(final)
        self.assertLess(tail, 505)
        self.assertEqual(len(blocks) * 505 + tail, 4830)
        self.assertEqual(codec.decode_block(blocks[0]), bytes(2020))
        encoder = codec.AudioEncoder(8000)
        self.assertEqual(encoder.push(bytes(4)), [])

    def test_invalid_profile_and_inputs(self):
        """@brief Reject invalid bounds and verify the encoder applied its block size."""
        for rate in (True, 0, 192001):
            with self.assertRaises(ValueError):
                codec.AudioEncoder(rate)
        for channels in (True, 0, 8):
            with self.assertRaises(ValueError):
                codec.AudioEncoder(channels=channels)
        encoder = codec.AudioEncoder()
        for data in (None, b"", bytes(1), bytes(48000 * 4 + 4)):
            with self.assertRaises(ValueError):
                encoder.push(data)

    def test_malformed_headers_and_decoder_length(self):
        """@brief No truncated/oversized/index-invalid/reserved block reaches decoding."""
        for block in (None, b"", bytes(511), bytes(513)):
            with self.assertRaises(ValueError):
                codec.validate_block(block)
        for offset in (2, 3, 6, 7):
            block = bytearray(512)
            block[offset] = 89
            with self.assertRaises(ValueError):
                codec.decode_block(bytes(block))
        for data in (None, b"", bytes(513)):
            with self.assertRaises(ValueError):
                codec.wav_bytes(data)

    def test_product_rounding_encoder_feedback_and_clamps(self):
        """@brief A three-frame counterexample detects shift/add feedback in the encoder."""
        pcm = struct.pack("<hhhhhh", 0, 0, 13, -13, 16, -16) + bytes(502 * 4)
        block, indices = codec.encode_block(pcm)
        # Product reconstruction of code7 at step7 is13. Its next code is0;
        # shift/add reconstructs11 and would incorrectly choose code1 instead.
        self.assertEqual((block[8], block[12]), (0x07, 0x8F))
        self.assertEqual(
            struct.unpack_from("<6h", codec.decode_block(block)), (0, 0, 13, -13, 15, -15)
        )
        next_block, _ = codec.encode_block(pcm, indices)
        self.assertEqual((next_block[2], next_block[6]), indices)
        self.assertEqual(codec._advance(32767, 88, 7), (32767, 88))
        self.assertEqual(codec._advance(-32768, 88, 15), (-32768, 88))
        self.assertEqual(codec._advance(0, 0, 0), (0, 0))
        self.assertEqual(codec._advance(0, 0, 7), (13, 8))

    def test_block_encoder_rejects_invalid_pcm_and_indices(self):
        """@brief No partial PCM block or invalid step state can be emitted."""
        for pcm in (None, b"", bytes(2019), bytes(2021)):
            with self.assertRaises(ValueError):
                codec.encode_block(pcm)
        for indices in (None, [0, 0], (), (0,), (0, 0, 0), (True, 0), (-1, 0), (0, 89)):
            with self.assertRaises(ValueError):
                codec.encode_block(bytes(2020), indices)

    def test_convert_and_cli_no_overwrite(self):
        """@brief A deterministic source produces playable diagnostics with explicit tails."""
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "pcm.wav", Path(directory) / "adpcm.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setparams((2, 2, codec.RATE, 0, "NONE", "not compressed"))
                wav.writeframes(tone(1010, codec.RATE))
            result = codec.convert(source, output)
            self.assertEqual((result["blocks"], result["decoded_frames"]), (2, 1010))
            with self.assertRaises(FileExistsError):
                codec.convert(source, output)
            with patch.object(codec, "convert", return_value=result), patch("builtins.print"):
                codec.main([str(source), str(output)])
            for width, frames in ((1, 20), (2, codec.RATE * 61)):
                with wave.open(str(source), "wb") as wav:
                    wav.setparams((1, width, codec.RATE, 0, "NONE", "not compressed"))
                    wav.writeframes(bytes(frames * width))
                with self.assertRaises(ValueError):
                    codec.convert(source, output)

    def test_channel_headers_and_golden_silence(self):
        """@brief Header predictors are the first signed stereo samples in a fresh block."""
        block = struct.pack("<hBBhBB", 1234, 0, 0, -2345, 0, 0) + bytes(504)
        decoded = codec.decode_block(block)
        self.assertEqual(struct.unpack_from("<hh", decoded), (1234, -2345))
        self.assertEqual(codec.decode_block(bytes(512)), bytes(2020))

    def test_command_entrypoint(self):
        """@brief Exercise the actual module entrypoint with a deterministic PCM source."""
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "source.wav", Path(directory) / "encoded.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setparams((2, 2, codec.RATE, 0, "NONE", "not compressed"))
                wav.writeframes(tone(505, codec.RATE))
            with (
                patch("sys.argv", ["audio_codec.py", str(source), str(output)]),
                patch("builtins.print"),
            ):
                runpy.run_path(str(Path(codec.__file__)), run_name="__main__")
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
