"""@brief Replay full native AR03 body fixtures without touching a device or socket."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from prepare_v20_body_fixtures import BODY_SCHEMA, MANIFEST_SCHEMA
from prepare_v20_fixtures import MOONBUB_COMMIT, _safe_relpath


def bounded_json(path, maximum=1024 * 1024):
    """@brief Read a bounded JSON object, rejecting oversized or non-object metadata."""
    path = Path(path)
    if path.stat().st_size > maximum:
        raise ValueError("Body fixture metadata exceeds bound")
    result = json.loads(path.read_bytes())
    if not isinstance(result, dict):
        raise TypeError("Body fixture metadata must be an object")
    return result


def descendant(root, name):
    """@brief Confine canonical fixture paths, including symlink resolution."""
    result = root.joinpath(*_safe_relpath(name).parts).resolve(strict=True)
    result.relative_to(root.resolve())
    if not result.is_file():
        raise ValueError("Body fixture must be a regular file")
    return result


def descriptors(case):
    """@brief Enumerate every raw oracle required to replay one isolated packet."""
    yield from (case["packet"], case["ack"], case["source_rgb"], case["display_rgb565"])
    yield from case["decoded_yuv"]
    for bank in case["pre_banks"].values():
        if bank is not None:
            yield from bank["planes"]


def invoke(executable, case, runner=subprocess.run):
    """@brief Run the scoped native decoder with a finite timeout."""
    return runner(
        [str(executable), "--body-case", str(case)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def negative_replays(executable, case_path, metadata, runner):
    """@brief Corrupt only private copies; update hashes to reach the actual decoder."""
    with tempfile.TemporaryDirectory(prefix="gamebub-v20-body-") as directory:
        temporary = Path(directory)
        for descriptor in descriptors(metadata):
            source = descendant(case_path.parent, descriptor["path"])
            target = temporary.joinpath(*_safe_relpath(descriptor["path"]).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        packet = descendant(temporary, metadata["packet"]["path"])
        original = packet.read_bytes()
        for data in (original[:-1] + bytes([original[-1] ^ 1]), original[:-1]):
            packet.write_bytes(data)
            metadata["packet"]["bytes"] = len(data)
            metadata["packet"]["sha256"] = hashlib.sha256(data).hexdigest()
            private_case = temporary / "negative.json"
            private_case.write_text(json.dumps(metadata), encoding="utf-8")
            result = invoke(executable, private_case, runner)
            if result.returncode != 1 or "body decode:" not in result.stderr:
                raise ValueError("Corrupted body did not reach/reject in native decoder")
    return 2


def verify(fixtures, executable, *, runner=subprocess.run, expected_cases=20):
    """@brief Validate fixture identities and exact native frame/bank/display/ACK reports."""
    fixtures = Path(fixtures).resolve(strict=True)
    executable = Path(executable).resolve(strict=True)
    if not executable.is_file():
        raise ValueError("Native executable must be a regular file")
    manifest = bounded_json(fixtures / "manifest.json")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("source_commit") != MOONBUB_COMMIT:
        raise ValueError("Body fixture schema/source pin mismatch")
    source = descendant(fixtures, "source-results.json")
    if source.stat().st_size > 16 * 1024 * 1024 or hashlib.sha256(
        source.read_bytes()
    ).hexdigest() != manifest.get("source_results_sha256"):
        raise ValueError("Body fixture source-results mismatch")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != expected_cases:
        raise ValueError("Unexpected body case count")
    reports, labels, negatives = [], set(), 0
    for row in cases:
        path = descendant(fixtures, row["case_path"])
        case = bounded_json(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != row.get("case_sha256"):
            raise ValueError("Body fixture case metadata hash mismatch")
        if (
            case.get("schema") != BODY_SCHEMA
            or case.get("label") != row["label"]
            or case.get("id") != row["id"]
            or row["label"] in labels
            or case.get("policy") != row["policy"]
            or case["packet"]["sha256"] != row["packet_sha256"]
            or case["ack"]["sha256"] != row["ack_sha256"]
        ):
            raise ValueError("Body fixture identity mismatch")
        labels.add(row["label"])
        result = invoke(executable, path, runner)
        if result.returncode:
            raise ValueError(f"Native body replay failed:{row['label']}:{result.stderr}")
        report = json.loads(result.stdout)
        width, height = case["geometry"]["width"], case["geometry"]["height"]
        expected_hud = 21120 if case["policy"] == "mandatory" else 0
        if (
            not isinstance(report, dict)
            or report.get("scope") != "full_body_fixture"
            or report.get("id") != row["id"]
            or report.get("label") != row["label"]
            or report.get("yuv_samples") != width * height * 3 // 2
            or report.get("display_words") != width * height
            or report.get("mandatory_hud_words_verified") != expected_hud
            or report.get("af03_exact") is not True
            or report.get("post_banks_exact") is not True
        ):
            raise ValueError("Native body report scope/oracle count mismatch")
        reports.append(report)
        negatives += negative_replays(executable, path, case, runner)
    return {
        "schema": "gamebub-v20-body-verification-v1",
        "source_commit": MOONBUB_COMMIT,
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "scope": "isolated full-body software fixtures, not streaming or hardware",
        "cases": reports,
        "case_count": len(reports),
        "negative_body_replays": negatives,
        "yuv_samples": sum(r["yuv_samples"] for r in reports),
        "display_words": sum(r["display_words"] for r in reports),
        "mandatory_hud_words_verified": sum(r["mandatory_hud_words_verified"] for r in reports),
    }


def main(argv=None):
    """@brief Run one pinned offline campaign and exclusively create its report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args.fixtures, args.executable)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
