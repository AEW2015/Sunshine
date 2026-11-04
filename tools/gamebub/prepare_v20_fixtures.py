"""@brief Export pinned GameBub v20 vectors for the native conformance runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zlib
from pathlib import Path, PurePosixPath

MOONBUB_COMMIT = "27a4dde6a7e2ea4fab09d892551ef542f05c8965"
PINNED_SOURCE_RESULTS_SHA256 = "6542a1fe19735217fa17c0efa2dc18c68b28ef2cd88a8c5baf8534901c1fa94d"
SUNSHINE_COMMIT = "3d49c6fe87753eb5b35d693991fdff0365e4bbbf"
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_STORED_BYTES = 32 * 1024 * 1024
MAX_RAW_BYTES = 64 * 1024 * 1024
MAX_TOTAL_RAW_BYTES = 512 * 1024 * 1024
MAX_AR03_BYTES = 49_152
STUDY = "experiments/python-game-mandatory-hud-study"
KIT = "hardware/gamebub-v20"


class FixtureError(ValueError):
    """@brief Report an invalid reference artifact or unsafe export request."""


def _git_show(repo: Path, revision: str, path: str, max_bytes: int) -> bytes:
    """@brief Read one bounded file from a pinned Git tree without changing checkout state."""
    _safe_relpath(path)
    object_spec = f"{revision}:{path}"
    size_result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-s", object_spec],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        object_size = int(size_result.stdout.strip())
    except ValueError as exc:
        raise FixtureError(f"invalid Git object size for {path}") from exc
    if object_size < 0 or object_size > max_bytes:
        raise FixtureError(f"Git object exceeds size limit: {path}")
    result = subprocess.run(
        ["git", "-C", str(repo), "show", object_spec],
        check=True,
        capture_output=True,
    )
    if len(result.stdout) > max_bytes:
        raise FixtureError(f"Git object exceeds size limit: {path}")
    return result.stdout


def _safe_relpath(value: str) -> PurePosixPath:
    """@brief Accept only normalized repository-relative POSIX paths."""
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise FixtureError("invalid relative artifact path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or ":" in path.parts[0]
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise FixtureError(f"unsafe relative artifact path: {value!r}")
    return path


def _json(raw: bytes, label: str):
    """@brief Parse bounded UTF-8 JSON and identify malformed reference metadata."""
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FixtureError(f"invalid JSON in {label}") from exc


def _write_new(root: Path, relpath: str, data: bytes) -> None:
    """@brief Write an artifact beneath a newly created output directory."""
    target = root.joinpath(*_safe_relpath(relpath).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


class Exporter:
    """@brief Export and validate the frozen inverse, wire, and envelope fixtures."""

    def __init__(self, moonbub_repo: Path, sunshine_repo: Path | None = None):
        self.moonbub_repo = moonbub_repo.resolve()
        self.sunshine_repo = sunshine_repo.resolve() if sunshine_repo else None
        self.total_raw_bytes = 0

    def read_moonbub(self, path: str, limit: int = MAX_JSON_BYTES) -> bytes:
        """@brief Read a file from the exact MoonBub source commit."""
        return _git_show(self.moonbub_repo, MOONBUB_COMMIT, path, limit)

    def _blob(
        self,
        descriptor: dict,
        source_prefix: str,
        expected_encoding: str = "zlib",
        max_raw_bytes: int = MAX_RAW_BYTES,
    ) -> bytes:
        """@brief Read and verify one safe content-addressed Git blob."""
        if descriptor.get("encoding", expected_encoding) != expected_encoding:
            raise FixtureError("unsupported fixture encoding")
        rel = _safe_relpath(descriptor.get("path"))
        raw_size = descriptor.get("raw_bytes")
        if not isinstance(raw_size, int) or raw_size < 0 or raw_size > min(MAX_RAW_BYTES, max_raw_bytes):
            raise FixtureError(f"invalid uncompressed length: {rel}")
        stored = self.read_moonbub(f"{source_prefix}/{rel.as_posix()}", MAX_STORED_BYTES)
        stored_hash = hashlib.sha256(stored).hexdigest()
        if stored_hash != descriptor.get("stored_sha256"):
            raise FixtureError(f"stored hash mismatch: {rel}")
        if expected_encoding == "zlib":
            decoder = zlib.decompressobj()
            raw = decoder.decompress(stored, raw_size + 1)
            if len(raw) > raw_size or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
                raise FixtureError(f"decompression exceeds declared size: {rel}")
        else:
            raw = stored
        if len(raw) != raw_size or hashlib.sha256(raw).hexdigest() != descriptor.get("raw_sha256"):
            raise FixtureError(f"raw size/hash mismatch: {rel}")
        self.total_raw_bytes += len(raw)
        if self.total_raw_bytes > MAX_TOTAL_RAW_BYTES:
            raise FixtureError("aggregate fixture size exceeds limit")
        return raw

    def _export_inverse(self, root: Path) -> dict:
        """@brief Export all golden inverse datasets as raw little-endian int32 pairs."""
        index_raw = self.read_moonbub(f"{KIT}/golden-index.json")
        index = _json(index_raw, "golden-index.json")
        if index.get("schema") != "gamebub-v20-inverse-golden-v1":
            raise FixtureError("unexpected inverse golden schema")
        rows = []
        for dataset in index.get("datasets", []):
            name = dataset.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
                raise FixtureError("invalid inverse dataset name")
            arrays = dataset.get("arrays", {})
            in_desc, out_desc = arrays.get("dequantized"), arrays.get("residual")
            if not isinstance(in_desc, dict) or not isinstance(out_desc, dict):
                raise FixtureError(f"missing inverse arrays for {name}")
            for desc in (in_desc, out_desc):
                if desc.get("dtype") != "<i4":
                    raise FixtureError(f"unexpected inverse dtype for {name}")
                shape = desc.get("shape")
                if not isinstance(shape, list) or len(shape) != 3 or shape[1:] != [8, 8]:
                    raise FixtureError(f"unexpected inverse shape for {name}")
            if in_desc["shape"] != out_desc["shape"] or in_desc["shape"][0] != dataset.get("blocks"):
                raise FixtureError(f"inverse shape/count mismatch for {name}")
            input_raw = self._blob(in_desc, KIT)
            expected_raw = self._blob(out_desc, KIT)
            expected_bytes = dataset["blocks"] * 64 * 4
            if len(input_raw) != expected_bytes or len(expected_raw) != expected_bytes:
                raise FixtureError(f"inverse array byte count mismatch for {name}")
            input_path = f"inverse/{name}.input.i32le.bin"
            expected_path = f"inverse/{name}.expected.i32le.bin"
            _write_new(root, input_path, input_raw)
            _write_new(root, expected_path, expected_raw)
            rows.append({
                "name": name,
                "blocks": dataset["blocks"],
                "bytes_per_block": 256,
                "input_path": input_path,
                "input_sha256": hashlib.sha256(input_raw).hexdigest(),
                "expected_path": expected_path,
                "expected_sha256": hashlib.sha256(expected_raw).hexdigest(),
            })
        if not rows:
            raise FixtureError("golden index contains no datasets")
        _write_new(root, "inverse/golden-index.json", index_raw)
        return {"schema": "gamebub-v20-native-inverse-fixtures-v1", "datasets": rows}

    def _export_contracts(self, root: Path) -> dict:
        """@brief Copy pinned wire/development JSON contracts from Sunshine Git."""
        if self.sunshine_repo is None:
            raise FixtureError("--sunshine-repo is required for pinned contracts")
        entries = {}
        for name in ("wire-contract.json", "development-profile.json"):
            rel = f"tools/gamebub/v20/{name}"
            raw = _git_show(self.sunshine_repo, SUNSHINE_COMMIT, rel, MAX_JSON_BYTES)
            _json(raw, name)
            out = f"contracts/{name}"
            _write_new(root, out, raw)
            entries[name] = {"path": out, "sha256": hashlib.sha256(raw).hexdigest()}
        return entries

    def _export_packets(self, root: Path) -> list:
        """@brief Export the 20 exact AR03 and AF03 envelope fixture blobs."""
        results = _json(self.read_moonbub(f"{STUDY}/results.json"), "mandatory-HUD results")
        rows = []
        for case in results.get("cases", []):
            scene, policy = case.get("scene"), case.get("policy")
            for vector in case.get("vectors", []):
                fixture_id = vector.get("id")
                if not isinstance(fixture_id, int) or fixture_id < 0:
                    raise FixtureError("invalid mandatory fixture id")
                label = f"{scene}-{policy}-{fixture_id:02d}"
                packet = self._blob(vector.get("packet", {}), STUDY, max_raw_bytes=MAX_AR03_BYTES)
                ack = self._blob(vector.get("ack", {}), STUDY, max_raw_bytes=43)
                if not packet or len(packet) > MAX_AR03_BYTES or len(ack) != 43:
                    raise FixtureError(f"invalid AR03/AF03 size for {label}")
                packet_path = f"ar03/{label}.ar03"
                ack_path = f"ar03/{label}.af03"
                _write_new(root, packet_path, packet)
                _write_new(root, ack_path, ack)
                rows.append({
                    "label": label,
                    "scene": scene,
                    "policy": policy,
                    "id": fixture_id,
                    "ar03_path": packet_path,
                    "ar03_bytes": len(packet),
                    "ar03_sha256": hashlib.sha256(packet).hexdigest(),
                    "af03_path": ack_path,
                    "af03_bytes": len(ack),
                    "af03_sha256": hashlib.sha256(ack).hexdigest(),
                })
        if len(rows) != 20 or len({row["label"] for row in rows}) != 20:
            raise FixtureError(f"expected 20 unique mandatory fixtures, found {len(rows)}")
        return rows

    def export(self, output: Path) -> dict:
        """@brief Create a new fixture directory and return its manifest."""
        output = output.resolve()
        if output.exists():
            raise FixtureError(f"output already exists: {output}")
        output.mkdir(parents=True)
        inverse = self._export_inverse(output)
        contracts = self._export_contracts(output)
        packets = self._export_packets(output)
        manifest = {
            "schema": "gamebub-v20-native-fixtures-v1",
            "source": {
                "moonbub_commit": MOONBUB_COMMIT,
                "sunshine_commit": SUNSHINE_COMMIT,
            },
            "inverse": inverse,
            "contracts": contracts,
            "ar03_fixtures": packets,
            "scope": "raw inverse pairs and AR03/AF03 envelope fixtures; no full entropy/YUV/HUD decode",
        }
        # Write the manifest last; its presence marks a complete export.
        _write_new(output, "manifest.json", json.dumps(manifest, indent=2).encode() + b"\n")
        return manifest


def main(argv=None) -> int:
    """@brief Export the pinned v20 fixtures without checking out either repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=Path, required=True, help="MoonBub Git repository")
    parser.add_argument("--sunshine-repo", type=Path, required=True, help="Sunshine Git repository")
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    args = parser.parse_args(argv)
    report = Exporter(args.reference_repo, args.sunshine_repo).export(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "inverse_datasets": len(report["inverse"]["datasets"]), "ar03_fixtures": len(report["ar03_fixtures"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
