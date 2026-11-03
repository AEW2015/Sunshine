"""@brief Reproduce receiver fixtures without selecting a codec for the wire protocol."""

import argparse
import hashlib
import io
import json
import zlib
from pathlib import Path

from PIL import Image

from host import Profile, canvas, encode, pattern


def generate(output: Path) -> dict:
    """@brief Write moving test-pattern samples with integrity and decoder references.

    @param output Destination directory for PNG, JPEG, and manifest files.
    @return Versioned fixture manifest; these are exploratory JPEG settings only.
    """
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "fixture_version": 1,
        "status": "exploratory_not_receiver_approved",
        "canvas": [720, 480],
        "content_rect": [0, 37, 720, 405],
        "frames": [],
    }
    for frame_id in (0, 1, 29, 30, 255):
        image = canvas(pattern(frame_id))
        png = io.BytesIO()
        image.save(png, format="PNG")
        png_path = output / f"frame-{frame_id:08d}.png"
        png_path.write_bytes(png.getvalue())
        for subsampling, restart in (("4:2:0", 0), ("4:2:2", 10), ("4:4:4", 0)):
            jpeg, metadata = encode(image, 75, Profile(subsampling, restart))
            name = f"frame-{frame_id:08d}-{subsampling.replace(':', '')}-r{restart}.jpg"
            (output / name).write_bytes(jpeg)
            with Image.open(io.BytesIO(jpeg)) as decoded:
                decoded_hash = hashlib.sha256(decoded.tobytes()).hexdigest()
            manifest["frames"].append(
                {
                    "frame_id": frame_id,
                    "png": png_path.name,
                    "png_sha256": hashlib.sha256(png.getvalue()).hexdigest(),
                    "raw_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                    "jpeg": name,
                    "quality": 75,
                    "bytes": len(jpeg),
                    "jpeg_sha256": hashlib.sha256(jpeg).hexdigest(),
                    "jpeg_crc32": f"{zlib.crc32(jpeg):08x}",
                    "host_decoded_rgb_sha256": decoded_hash,
                    **metadata,
                }
            )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    """@brief Generate fixtures in an explicitly selected output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    generate(parser.parse_args().output)


if __name__ == "__main__":
    main()
