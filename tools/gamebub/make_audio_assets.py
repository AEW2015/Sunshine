"""@brief Generate deterministic audio fixtures for receiver codec validation."""

import argparse
import hashlib
import json
import wave
from pathlib import Path

import av

from audio_codec import RATE, AudioEncoder, decode_block, wav_bytes
from windows_audio import test_tone


def generate(output):
    """@brief Write source PCM, raw blocks, decoded PCM and versioned integrity metadata.

    @param output New destination directory; existing paths are never overwritten.
    @return Manifest including every raw block and reconstructed PCM SHA-256.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    pcm = test_tone(505 * 20, RATE)
    encoder = AudioEncoder(RATE)
    blocks = encoder.push(pcm)
    final, tail = encoder.finish()
    blocks.extend(final)
    decoded = b"".join(decode_block(block) for block in blocks)
    for name, data in (("source.wav", pcm), ("decoded.wav", decoded)):
        with wave.open(str(output / name), "wb") as wav:
            wav.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(data)
    (output / "blocks.ima").write_bytes(b"".join(blocks))
    (output / "encoded.wav").write_bytes(wav_bytes(b"".join(blocks)))
    manifest = {
        "version": 2,
        "encoder": "gamebub-ima-product-v1",
        "reconstruction": "full-product integer rounding",
        "status": "proposed profile; not receiver playback verified",
        "rate": RATE,
        "channels": 2,
        "block_bytes": 512,
        "samples_per_block": 505,
        "source": "left 440 Hz, right 880 Hz; amplitude 4096; phase zero",
        "discarded_tail_frames": tail,
        "pyav_version": av.__version__,
        "ffmpeg_libraries": {name: list(version) for name, version in av.library_versions.items()},
        "source_pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "decoded_pcm_sha256": hashlib.sha256(decoded).hexdigest(),
        "blocks": [
            {
                "index": index,
                "offset": index * 512,
                "sha256": hashlib.sha256(block).hexdigest(),
                "decoded_pcm_sha256": hashlib.sha256(decode_block(block)).hexdigest(),
            }
            for index, block in enumerate(blocks)
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv=None):
    """@brief Generate a new receiver-validation fixture directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(generate(args.output), indent=2))


if __name__ == "__main__":
    main()
