"""@brief Export bounded HD22 word/packet oracles from the pinned MoonBub Git tree."""

import argparse
import hashlib
import json
import re
import zlib
from pathlib import Path

from prepare_v20_fixtures import FixtureError, _git_show, _safe_relpath

COMMIT = "4025d35593e8b71b9d9f5e4fb68d1e7a9ed29189"
STUDY = "experiments/python-game-gap-span-study"
RESULTS_HASH = "2657a35912ca2b33b68f6ea75e705c0b2a88c8c5a8d4067fb8f85faecbe84971"


def unpack(repo, descriptor):
    """@brief Verify a content-addressed object before bounded single-stream decompression."""
    relative = _safe_relpath(descriptor["path"])
    size = descriptor["raw_bytes"]
    if type(size) is not int or not 0 < size <= 42290 or relative.parts[0] != "objects":
        raise FixtureError("HD22 object bounds")
    for key in ("raw_sha256", "stored_sha256"):
        if not isinstance(descriptor[key], str) or not re.fullmatch(
            "[0-9a-f]{64}", descriptor[key]
        ):
            raise FixtureError("HD22 object hash format")
    stored = _git_show(repo, COMMIT, f"{STUDY}/{relative}", 65536)
    if hashlib.sha256(stored).hexdigest() != descriptor["stored_sha256"]:
        raise FixtureError("HD22 stored object hash")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(stored, size + 1)
    if len(raw) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise FixtureError("HD22 exact decompressed size/stream")
    if hashlib.sha256(raw).hexdigest() != descriptor["raw_sha256"]:
        raise FixtureError("HD22 raw object hash")
    return raw


def export(repo, output):
    """@brief Exclusively export all seven frozen oracles without executing reference code."""
    raw = _git_show(repo, COMMIT, f"{STUDY}/results.json", 512 * 1024)
    if hashlib.sha256(raw).hexdigest() != RESULTS_HASH:
        raise FixtureError("pinned HD22 results hash")
    goldens = json.loads(raw)["goldens"]
    if not isinstance(goldens, list) or len(goldens) != 7:
        raise FixtureError("HD22 golden count")
    # Validate every descriptor and object before creating the destination.
    objects = {}
    for golden in goldens:
        shape = golden["shape"]
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or any(type(x) is not int or x <= 0 for x in shape)
            or shape[0] > 480
            or shape[1] > 720
            or shape[0] * shape[1] > 21120
        ):
            raise FixtureError("HD22 golden geometry")
        for key in ("packet", "current", "reference"):
            descriptor = golden[key]
            if descriptor is None and key == "reference":
                continue
            data = unpack(repo, descriptor)
            if key != "packet" and len(data) != 2 * shape[0] * shape[1]:
                raise FixtureError("HD22 golden words")
            objects[descriptor["raw_sha256"]] = data
    output.mkdir(parents=True, exist_ok=False)
    (output / "objects").mkdir()
    (output / "source_results.json").write_bytes(raw)
    for digest, data in objects.items():
        (output / "objects" / f"{digest}.bin").write_bytes(data)
    return {
        "vectors": 7,
        "objects": len(objects),
        "source_commit": COMMIT,
        "source_results_sha256": RESULTS_HASH,
        "hardware_verified": False,
    }


def main(argv=None):
    """@brief Materialize a reproducible offline fixture directory without overwriting evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(export(args.reference_repo, args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
