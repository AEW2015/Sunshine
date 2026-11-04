"""@brief Add pinned encoder oracle metadata to exported v20 body cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath

import prepare_v20_fixtures as common

PINNED_SOURCE_COMMIT = "27a4dde6a7e2ea4fab09d892551ef542f05c8965"
PINNED_SOURCE_RESULTS_SHA256 = common.PINNED_SOURCE_RESULTS_SHA256
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_CASE_BYTES = 1024 * 1024
MAX_SOURCE_RESULTS_BYTES = 16 * 1024 * 1024
MAX_RAW_BYTES = 64 * 1024 * 1024
SELECTED_PROFILES = {(8, 16), (8, 32), (16, 32), (32, 32)}


class EncoderCaseError(ValueError):
    """@brief Report an invalid or unsafe encoder fixture export."""


def _json(path: Path) -> tuple[dict, bytes]:
    """@brief Read a JSON object and retain its exact bytes for digest validation."""
    if path.stat().st_size > _json_limit(path.name):
        raise EncoderCaseError(f"JSON exceeds size limit: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncoderCaseError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EncoderCaseError(f"expected JSON object: {path}")
    return value, raw


def _json_limit(name: str) -> int:
    """@brief Select a bounded metadata size by known export filename."""
    if name == "source-results.json":
        return MAX_SOURCE_RESULTS_BYTES
    return MAX_MANIFEST_BYTES if name == "manifest.json" else MAX_CASE_BYTES


def _safe_relative(value: object) -> PurePosixPath:
    """@brief Accept only ordinary relative POSIX fixture paths."""
    try:
        return common._safe_relpath(value)
    except common.FixtureError as exc:
        raise EncoderCaseError(str(exc)) from exc


def _descendant(root: Path, name: object) -> Path:
    """@brief Resolve a declared fixture file inside its source root, including symlinks."""
    path = root.joinpath(*_safe_relative(name).parts).resolve(strict=True)
    try:
        path.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise EncoderCaseError("fixture path escapes source root") from exc
    if not path.is_file():
        raise EncoderCaseError("fixture path is not a regular file")
    return path


def _descriptors(case: dict) -> list[dict]:
    """@brief Collect every content-addressed byte file declared by an exported case."""
    fields = ("packet", "ack", "source_rgb", "display_rgb565")
    result = [case.get(field) for field in fields]
    decoded = case.get("decoded_yuv")
    banks = case.get("pre_banks")
    if not isinstance(decoded, list) or not isinstance(banks, dict):
        raise EncoderCaseError("missing case array descriptors")
    result.extend(decoded)
    for bank in banks.values():
        if bank is not None:
            if not isinstance(bank, dict) or not isinstance(bank.get("planes"), list):
                raise EncoderCaseError("invalid reference bank descriptors")
            result.extend(bank["planes"])
    for descriptor in result:
        if not isinstance(descriptor, dict):
            raise EncoderCaseError("invalid declared byte descriptor")
        name, length, digest = descriptor.get("path"), descriptor.get("bytes"), descriptor.get("sha256")
        if (type(length) is not int or not 0 <= length <= MAX_RAW_BYTES
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise EncoderCaseError("invalid declared byte length or digest")
        _safe_relative(name)
    return result


def _validate_preconditions(case: dict, source_case: dict, vector: dict, row: dict) -> None:
    """@brief Confirm exported receiver preconditions agree with the pinned encoder row."""
    state = case.get("state")
    geometry = case.get("geometry")
    manifest = source_case.get("manifest")
    if not isinstance(state, dict) or not isinstance(geometry, dict) or not isinstance(manifest, dict):
        raise EncoderCaseError("missing body precondition metadata")
    if geometry != {"width": manifest.get("target_width"), "height": manifest.get("target_height")}:
        raise EncoderCaseError("reference geometry mismatch")
    if any(state.get(field) != row.get(row_field) for field, row_field in (
        ("reference_bank", "reference_bank"),
        ("reference_id", "reference_id"),
        ("reference_tag", "reference_tag"),
        ("destination_bank", "destination_bank"),
        ("stored_tag", "stored_tag"),
    )):
        raise EncoderCaseError("reference or destination identity mismatch")
    if (type(case.get("key")) is not bool or case["key"] != vector.get("key")
            or type(case.get("promoted")) is not bool or case["promoted"] != vector.get("promoted")
            or case["promoted"] != row.get("promoted")):
        raise EncoderCaseError("key/promotion precondition mismatch")
    reference_bank = row.get("reference_bank")
    if reference_bank in (0, 1):
        banks = case.get("pre_banks")
        reference = banks.get(str(reference_bank)) if isinstance(banks, dict) else None
        if (not isinstance(reference, dict) or reference.get("id") != row.get("reference_id")
                or reference.get("tag") != row.get("reference_tag")):
            raise EncoderCaseError("reference bank precondition mismatch")


def _sha(raw: bytes) -> str:
    """@brief Return the SHA-256 digest of bytes."""
    return hashlib.sha256(raw).hexdigest()


def _case_row(case: dict, vector: dict) -> dict:
    """@brief Find the unique encoder decision row matching a vector ID."""
    rows = case.get("rows")
    if not isinstance(rows, list):
        raise EncoderCaseError("missing encoder rows")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == vector.get("id")]
    if len(matches) != 1:
        raise EncoderCaseError("missing or duplicate encoder decision row")
    return matches[0]


def _oracle(source_case: dict, vector: dict) -> dict:
    """@brief Select precise native encoder expectations from pinned decision metadata."""
    row = _case_row(source_case, vector)
    profile = row.get("selected_profile")
    if (not isinstance(profile, list) or len(profile) != 2 or any(type(x) is not int for x in profile)
            or tuple(profile) not in SELECTED_PROFILES):
        raise EncoderCaseError("missing selected quantmap profile")
    for field in ("inner_bytes", "patch_bytes", "packet_bytes", "reference_bank", "reference_id", "destination_bank"):
        if type(row.get(field)) is not int or row[field] < 0:
            raise EncoderCaseError(f"invalid encoder oracle field: {field}")
    for field in ("reference_tag", "stored_tag"):
        if not isinstance(row.get(field), str) or not re.fullmatch(r"[0-9a-f]{32}", row[field]):
            raise EncoderCaseError(f"invalid encoder oracle field: {field}")
    if not isinstance(row.get("packet_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["packet_sha256"]):
        raise EncoderCaseError("invalid encoder oracle field: packet_sha256")
    if type(row.get("key")) is not bool or type(row.get("promoted")) is not bool:
        raise EncoderCaseError("invalid encoder key/promotion oracle")
    attempts = row.get("attempts")
    if not isinstance(attempts, list):
        raise EncoderCaseError("missing ordered encoder attempts")
    ordered_attempts = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise EncoderCaseError("invalid encoder attempt")
        roi, background = attempt.get("roi_scale"), attempt.get("background_scale")
        complete_bytes = attempt.get("attempted_complete_bytes")
        if any(type(value) is not int or value <= 0 for value in (roi, background, complete_bytes)):
            raise EncoderCaseError("invalid attempted map or size")
        if type(attempt.get("accepted")) is not bool:
            raise EncoderCaseError("invalid attempt acceptance")
        ordered_attempts.append({
            "roi_scale": roi,
            "background_scale": background,
            "attempted_complete_bytes": complete_bytes,
            "accepted": attempt["accepted"],
        })
    return {
        "selected_profile": profile,
        "roi_quantmap": {"roi_scale": profile[0], "background_scale": profile[1]},
        "inner_bytes": row["inner_bytes"],
        "patch_bytes": row["patch_bytes"],
        "packet_bytes": row["packet_bytes"],
        "candidate_control_id": row.get("candidate_control_id", row.get("control_id")),
        "key": row["key"],
        "promoted": row["promoted"],
        "reference": {
            "bank": row["reference_bank"],
            "id": row["reference_id"],
            "tag": row["reference_tag"],
            "geometry": {
                "width": source_case["manifest"].get("target_width"),
                "height": source_case["manifest"].get("target_height"),
            },
        },
        "destination": {"bank": row["destination_bank"], "tag": row["stored_tag"]},
        "packet_sha256": row["packet_sha256"],
        "attempts": ordered_attempts,
    }


def prepare(
    source: Path,
    output: Path,
    *,
    expected_cases: int = 20,
    expected_source_results_sha256: str = PINNED_SOURCE_RESULTS_SHA256,
) -> dict:
    """@brief Write a hash-checked, new derived fixture directory with encoder metadata."""
    source = source.resolve()
    output = output.resolve()
    if output.exists() or output == source or source in output.parents or output in source.parents:
        raise EncoderCaseError("output must be a new directory outside the source")
    manifest, _ = _json(source / "manifest.json")
    results, results_raw = _json(source / "source-results.json")
    if (
        manifest.get("schema") != "gamebub-v20-body-fixtures-v1"
        or manifest.get("source_commit") != PINNED_SOURCE_COMMIT
        or results.get("schema") != "gamebub-mandatory-hud-v1"
    ):
        raise EncoderCaseError("unsupported fixture schema")
    if (manifest.get("source_results_sha256") != expected_source_results_sha256
            or _sha(results_raw) != expected_source_results_sha256):
        raise EncoderCaseError("pinned source-results hash mismatch")
    index = manifest.get("cases")
    if not isinstance(index, list) or len(index) != expected_cases:
        raise EncoderCaseError("unexpected fixture case count")
    result_cases = results.get("cases")
    if not isinstance(result_cases, list):
        raise EncoderCaseError("invalid source case index")
    source_cases = {
        (case.get("scene"), case.get("policy")): case
        for case in result_cases
        if isinstance(case, dict)
    }
    if any(case.get("policy") not in ("baseline", "mandatory") for case in source_cases.values()):
        raise EncoderCaseError("invalid source case policy")
    output.mkdir(parents=True)
    for item in index:
        if not isinstance(item, dict):
            raise EncoderCaseError("invalid fixture index row")
        case_rel = _safe_relative(item.get("case_path"))
        case_path = _descendant(source, case_rel.as_posix())
        case, case_raw = _json(case_path)
        if item.get("case_sha256") != _sha(case_raw):
            raise EncoderCaseError("case digest mismatch")
        if case.get("policy") not in ("baseline", "mandatory"):
            raise EncoderCaseError("invalid body case policy")
        descriptors = _descriptors(case)
        for descriptor in descriptors:
            data_path = _descendant(source / "cases", descriptor["path"])
            if data_path.stat().st_size != descriptor["bytes"] or _sha(data_path.read_bytes()) != descriptor["sha256"]:
                raise EncoderCaseError("declared byte file length/hash mismatch")
            rel = data_path.relative_to(source).as_posix()
            target = output / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(data_path, target)
        key = (case.get("scene"), case.get("policy"))
        original = source_cases.get(key)
        if original is None:
            raise EncoderCaseError("missing pinned source case")
        matches = [v for v in original.get("vectors", []) if isinstance(v, dict) and v.get("id") == case.get("id")]
        if len(matches) != 1:
            raise EncoderCaseError("missing or duplicate pinned vector")
        vector = matches[0]
        row = _case_row(original, vector)
        _validate_preconditions(case, original, vector, row)
        if (row.get("packet_sha256") != case["packet"].get("sha256")
                or row.get("packet_bytes") != case["packet"].get("bytes")):
            raise EncoderCaseError("packet oracle disagrees with body case")
        case["encoder_oracle"] = _oracle(original, vector)
        target_case = output.joinpath(*case_rel.parts)
        target_case.parent.mkdir(parents=True, exist_ok=True)
        target_case.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        item["case_sha256"] = _sha(target_case.read_bytes())
    source_results = _descendant(source, "source-results.json")
    shutil.copyfile(source_results, output / "source-results.json")
    manifest["body_manifest_sha256"] = _sha(_descendant(source, "manifest.json").read_bytes())
    manifest["schema"] = "gamebub-v20-encoder-cases-v1"
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    """@brief Run the encoder case normalizer from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="existing immutable body fixture export")
    parser.add_argument("--output", type=Path, required=True, help="new normalized output directory")
    parser.add_argument("--expected-cases", type=int, default=20, help="expected source case count")
    args = parser.parse_args(argv)
    manifest = prepare(
        args.source,
        args.output,
        expected_cases=args.expected_cases,
        expected_source_results_sha256=common.PINNED_SOURCE_RESULTS_SHA256,
    )
    print(json.dumps({"output": str(args.output.resolve()), "cases": len(manifest["cases"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
