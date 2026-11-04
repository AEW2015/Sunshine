"""@brief Check published AV v1 vectors without concealing decoder-oracle disagreement."""

import argparse
import hashlib
import json
from pathlib import Path

import av

from audio_codec import decode_block
from av_protocol import HEADER, decode

FIXTURES = Path(__file__).parent / "fixtures" / "av-v1"


def verify(fixtures=FIXTURES):
    """@brief Return separate wire/fixture/PCM outcomes; no network traffic or input injection."""
    fixtures = Path(fixtures)
    vectors = json.loads((fixtures / "vectors.json").read_text())
    provenance = json.loads((fixtures / "provenance.json").read_text())
    integrity = all(
        hashlib.sha256((fixtures / name).read_bytes()).hexdigest() == digest
        for name, digest in provenance["sha256"].items()
    )
    checks = {}
    for name, vector in vectors["vectors"].items():
        wire = bytes.fromhex(vector["hex"])
        checks[name] = (
            decode(wire).encode() == wire and hashlib.sha256(wire).hexdigest() == vector["sha256"]
        )
    pcm = decode_block((fixtures / "stereo-505.ima").read_bytes())
    actual = hashlib.sha256(pcm).hexdigest()
    expected = vectors["decoded_pcm_sha256"]
    pcm_match = actual == expected and pcm == (fixtures / "stereo-505-decoded.s16le").read_bytes()
    return {
        "scope": "offline AV v1 conformance; no socket, receiver or physical playback test",
        "revision": provenance["revision"],
        "contract_revision": "aab1ba337550ba472c30ee417fcf6d439b5a7f1e",
        "codec_reconstruction": "IMA full-product integer rounding in encoder and decoder",
        "header_bytes": HEADER.size,
        "fixture_integrity": integrity,
        "packet_vectors": checks,
        "wire_match": all(checks.values()),
        "pcm_match": pcm_match,
        "expected_pcm_sha256": expected,
        "host_pcm_sha256": actual,
        "pyav_version": av.__version__,
        "libraries": av.library_versions,
        "complete_conformance": integrity and all(checks.values()) and pcm_match,
    }


def main(argv=None):
    """@brief Print results and return nonzero if wire, fixture or decoded PCM differs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    args = parser.parse_args(argv)
    report = verify(args.fixtures)
    print(json.dumps(report, indent=2))
    return 0 if report["complete_conformance"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
