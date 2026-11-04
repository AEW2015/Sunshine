"""@brief Verify the bounded native GameBub v20 inverse and envelope runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

MOONBUB_COMMIT = "27a4dde6a7e2ea4fab09d892551ef542f05c8965"
SUNSHINE_COMMIT = "3d49c6fe87753eb5b35d693991fdff0365e4bbbf"
MANIFEST_SCHEMA = "gamebub-v20-native-fixtures-v1"
MANIFEST_SCOPE = "raw inverse pairs and AR03/AF03 envelope fixtures; no full entropy/YUV/HUD decode"
MAX_FILE_BYTES = 512 * 1024 * 1024


class VerificationError(ValueError):
    """@brief Report unsafe fixtures or failed native conformance checks."""


def _relative_file(root: Path, value: object) -> Path:
    """@brief Resolve a normalized fixture path and keep symlinks beneath root."""
    value = _safe_relative_name(value)
    rel = PurePosixPath(value)
    base = root.resolve()
    target = base.joinpath(*rel.parts).resolve(strict=True)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise VerificationError(f"fixture path escapes root: {value!r}") from exc
    if not target.is_file():
        raise VerificationError(f"fixture is not a file: {value!r}")
    return target


def _safe_relative_name(value: object) -> str:
    """@brief Validate one manifest path before using it as a set key or disk path."""
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise VerificationError("invalid fixture path")
    rel = PurePosixPath(value)
    if rel.is_absolute() or rel.as_posix() != value or ":" in rel.parts[0] or any(
        part in ("", ".", "..") for part in rel.parts
    ):
        raise VerificationError(f"unsafe fixture path: {value!r}")
    return value


def _verified_bytes(root: Path, value: object, expected_size: int, expected_hash: object, label: str) -> bytes:
    """@brief Read one size- and SHA-256-checked fixture file."""
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise VerificationError(f"invalid SHA-256 for {label}")
    path = _relative_file(root, value)
    if expected_size < 0 or expected_size > MAX_FILE_BYTES or path.stat().st_size != expected_size:
        raise VerificationError(f"byte length mismatch for {label}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise VerificationError(f"SHA-256 mismatch for {label}")
    return raw


def _load_manifest(fixtures: Path, expected_inverse_datasets: int, expected_envelopes: int) -> tuple[dict, list]:
    """@brief Validate all manifest metadata and fixture bytes before child execution."""
    manifest_path = _relative_file(fixtures, "manifest.json")
    if manifest_path.stat().st_size > 4 * 1024 * 1024:
        raise VerificationError("fixture manifest exceeds size limit")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("invalid fixture manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise VerificationError("unexpected manifest schema")
    if manifest.get("scope") != MANIFEST_SCOPE:
        raise VerificationError("unexpected manifest scope")
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("moonbub_commit") != MOONBUB_COMMIT or source.get("sunshine_commit") != SUNSHINE_COMMIT:
        raise VerificationError("fixture source pin mismatch")

    inverse = manifest.get("inverse")
    datasets = inverse.get("datasets") if isinstance(inverse, dict) else None
    if not isinstance(inverse, dict) or inverse.get("schema") != "gamebub-v20-native-inverse-fixtures-v1":
        raise VerificationError("unexpected inverse schema")
    if not isinstance(datasets, list) or len(datasets) != expected_inverse_datasets:
        raise VerificationError("inverse dataset count mismatch")

    seen_paths: set[str] = {"manifest.json"}
    entries: list[tuple[str, Path, Path, int]] = []
    for row in datasets:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            raise VerificationError("invalid inverse dataset row")
        blocks = row.get("blocks")
        if isinstance(blocks, bool) or not isinstance(blocks, int) or blocks <= 0 or row.get("bytes_per_block") != 256:
            raise VerificationError(f"invalid inverse dimensions for {row.get('name')}")
        size = blocks * 256
        in_name, out_name = row.get("input_path"), row.get("expected_path")
        for name in (in_name, out_name):
            name = _safe_relative_name(name)
            if name in seen_paths:
                raise VerificationError("duplicate fixture path")
            seen_paths.add(name)
        _verified_bytes(fixtures, in_name, size, row.get("input_sha256"), f"{row['name']} input")
        _verified_bytes(fixtures, out_name, size, row.get("expected_sha256"), f"{row['name']} expected")
        entries.append(("inverse", _relative_file(fixtures, in_name), _relative_file(fixtures, out_name), blocks))

    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict) or set(contracts) != {"wire-contract.json", "development-profile.json"}:
        raise VerificationError("contract manifest entries mismatch")
    for name, descriptor in contracts.items():
        if not isinstance(descriptor, dict):
            raise VerificationError(f"invalid contract entry: {name}")
        _verified_bytes(fixtures, descriptor.get("path"),
                        _relative_file(fixtures, descriptor.get("path")).stat().st_size,
                        descriptor.get("sha256"), name)

    packets = manifest.get("ar03_fixtures")
    if not isinstance(packets, list) or len(packets) != expected_envelopes:
        raise VerificationError("envelope fixture count mismatch")
    for row in packets:
        if not isinstance(row, dict):
            raise VerificationError("invalid envelope fixture row")
        for field, size_field, hash_field, fixed_size in (
            ("ar03_path", "ar03_bytes", "ar03_sha256", None),
            ("af03_path", "af03_bytes", "af03_sha256", 43),
        ):
            name = row.get(field)
            name = _safe_relative_name(name)
            if name in seen_paths:
                raise VerificationError("duplicate fixture path")
            seen_paths.add(name)
            size = row.get(size_field)
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0 or (fixed_size and size != fixed_size):
                raise VerificationError(f"invalid envelope length for {row.get('label')}")
            if field == "ar03_path" and size > 49_152:
                raise VerificationError(f"AR03 exceeds byte cap for {row.get('label')}")
            _verified_bytes(fixtures, name, size, row.get(hash_field), str(row.get("label")))
            entries.append(("ar03" if field == "ar03_path" else "af03", _relative_file(fixtures, name), Path(), size))
    return manifest, entries


def _run_checked(executable: Path, args: list[str], runner=subprocess.run) -> dict:
    """@brief Run the offline CLI with a hard timeout and validate its JSON scope."""
    try:
        result = runner([str(executable), *args], capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError(f"native command failed to run: {args[0]}") from exc
    if result.returncode != 0:
        raise VerificationError(f"native command rejected {args[0]} (exit {result.returncode})")
    try:
        report = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"native command returned invalid JSON for {args[0]}") from exc
    if not isinstance(report, dict):
        raise VerificationError(f"native command returned invalid report for {args[0]}")
    return report


def verify_fixtures(fixtures: Path, executable: Path, *, runner=subprocess.run,
                    expected_inverse_datasets: int = 4, expected_envelopes: int = 20) -> dict:
    """@brief Verify inverse vectors and envelope acceptance/rejection behavior."""
    fixtures = fixtures.resolve(strict=True)
    executable = executable.resolve(strict=True)
    if not executable.is_file():
        raise VerificationError("executable is not a file")
    manifest, entries = _load_manifest(fixtures, expected_inverse_datasets, expected_envelopes)
    inverse_reports = []
    envelope_count = {"ar03": 0, "af03": 0}
    for kind, first, second, count in entries:
        if kind == "inverse":
            result = _run_checked(executable, ["--inverse", str(first), str(second)], runner)
            if result.get("scope") != "inverse_only" or result.get("blocks") != count or result.get("samples") != count * 64:
                raise VerificationError("native inverse report scope/count mismatch")
            inverse_reports.append({"dataset": first.name.removesuffix(".input.i32le.bin"), "blocks": count, "samples": count * 64})
        else:
            result = _run_checked(executable, [f"--{kind}", str(first)], runner)
            if result.get("scope") != "envelope_only" or result.get("bytes") != count:
                raise VerificationError(f"native {kind} report scope/length mismatch")
            envelope_count[kind] += 1

    negative_checks = 0
    for kind, packet in (("ar03", row[1]) for row in entries if row[0] == "ar03"):
        raw = packet.read_bytes()
        corruptions = (raw[:-1] + bytes([raw[-1] ^ 1]), raw[:-1])
        for corrupted in corruptions:
            with tempfile.NamedTemporaryFile(prefix="gamebub-v20-", suffix=f".{kind}", delete=False) as temp:
                temp.write(corrupted)
                temp_path = Path(temp.name)
            try:
                result = runner([str(executable), f"--{kind}", str(temp_path)], capture_output=True, text=True, timeout=60, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise VerificationError("native negative envelope check failed to run") from exc
            finally:
                temp_path.unlink(missing_ok=True)
            if result.returncode != 1:
                raise VerificationError("native AR03 corruption was not rejected with exit 1")
            negative_checks += 1
    for kind, packet in (("af03", row[1]) for row in entries if row[0] == "af03"):
        raw = packet.read_bytes()
        for corrupted in (raw[:-1] + bytes([raw[-1] ^ 1]), raw[:-1]):
            with tempfile.NamedTemporaryFile(prefix="gamebub-v20-", suffix=f".{kind}", delete=False) as temp:
                temp.write(corrupted)
                temp_path = Path(temp.name)
            try:
                result = runner([str(executable), f"--{kind}", str(temp_path)], capture_output=True, text=True, timeout=60, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise VerificationError("native negative envelope check failed to run") from exc
            finally:
                temp_path.unlink(missing_ok=True)
            if result.returncode != 1:
                raise VerificationError("native AF03 corruption was not rejected with exit 1")
            negative_checks += 1

    return {
        "schema": "gamebub-v20-native-verification-v1",
        "source": manifest["source"],
        "scope": {"inverse": "inverse_only", "envelopes": "envelope_only"},
        "inverse": {"datasets": inverse_reports, "blocks": sum(row["blocks"] for row in inverse_reports),
                    "samples": sum(row["samples"] for row in inverse_reports)},
        "envelopes": envelope_count,
        "negative_envelope_checks": negative_checks,
    }


def main(argv: list[str] | None = None) -> int:
    """@brief Validate fixtures, execute the native verifier, and write a JSON report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify_fixtures(args.fixtures, args.executable)
        report_path = args.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    except (OSError, VerificationError) as exc:
        parser.error(str(exc))
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
