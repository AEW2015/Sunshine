"""@brief Verify pinned native encoder bytes and paid retries; never infer playback FPS."""

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

from prepare_v20_body_fixtures import BODY_SCHEMA
from prepare_v20_encoder_cases import PINNED_SOURCE_RESULTS_SHA256
from prepare_v20_fixtures import MOONBUB_COMMIT
from verify_v20_body import bounded_json, descendant, descriptors

MANIFEST_SCHEMA = "gamebub-v20-encoder-cases-v1"
MAPS = ((8, 16), (8, 32), (16, 32), (32, 32))


def integer(value, maximum=2**63 - 1):
    """@brief Reject boolean, negative and unbounded count/timing fields."""
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Encoder count/timing must be a bounded unsigned integer")
    return value


def checked_blob(root, descriptor):
    """@brief Validate safe paths and bounded raw bytes before invoking native code."""
    path = descendant(root, descriptor["path"])
    size = integer(descriptor["bytes"], 2 * 1024 * 1024)
    if path.stat().st_size != size:
        raise ValueError("Encoder raw fixture byte count mismatch")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != descriptor["sha256"]:
        raise ValueError("Encoder raw fixture hash mismatch")
    return data


def duplicated_oracles(packet, oracle):
    """@brief Match typed reference/destination/map metadata to the frozen wire fields."""
    reference, destination = oracle["reference"], oracle["destination"]
    profile, quantmap = oracle["selected_profile"], oracle["roi_quantmap"]
    if (
        integer(reference["bank"], 255) != packet[14]
        or integer(reference["id"], 0xFFFFFFFF) != struct.unpack_from("<I", packet, 16)[0]
        or reference["tag"] != packet[20:36].hex()
        or integer(reference["geometry"]["width"], 720) != 720
        or integer(reference["geometry"]["height"], 480) != 480
        or integer(destination["bank"], 255) != packet[15]
        or destination["tag"] != packet[36:52].hex()
        or integer(quantmap["roi_scale"], 32) != integer(profile[0], 32)
        or integer(quantmap["background_scale"], 32) != integer(profile[1], 32)
    ):
        raise ValueError("Encoder duplicated reference/destination/map oracle mismatch")


def preflight(path, row):
    """@brief Check metadata, every input hash and frozen packet/attempt oracles first."""
    case = bounded_json(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != row["case_sha256"]:
        raise ValueError("Encoder case metadata hash mismatch")
    if (
        case.get("schema") != BODY_SCHEMA
        or any(case.get(key) != row[key] for key in ("label", "id", "policy", "scene"))
        or case.get("policy") not in ("baseline", "mandatory")
        or case["packet"]["sha256"] != row["packet_sha256"]
        or case["ack"]["sha256"] != row["ack_sha256"]
        or case["geometry"] != {"width": 720, "height": 480}
    ):
        raise ValueError("Encoder case identity/geometry mismatch")
    integer(case["id"], 0xFFFFFFFE)
    for descriptor in descriptors(case):
        checked_blob(path.parent, descriptor)
    rgb = case["source_rgb"]
    if rgb["dtype"] != "|u1" or rgb["shape"] != [480, 720, 3] or rgb["bytes"] != 1036800:
        raise ValueError("Encoder original RGB8 geometry mismatch")
    packet = checked_blob(path.parent, case["packet"])
    oracle = case["encoder_oracle"]
    if len(packet) < 65 or packet[:5] != b"AR03\x03":
        raise ValueError("Encoder AR03 oracle header mismatch")
    if (
        struct.unpack_from("<I", packet, 6)[0] != integer(case["epoch"], 0xFFFFFFFE)
        or struct.unpack_from("<I", packet, 10)[0] != case["id"]
    ):
        raise ValueError("Encoder packet epoch/frame identity mismatch")
    inner, patches = (
        struct.unpack_from("<I", packet, 52)[0],
        struct.unpack_from("<I", packet, 57)[0],
    )
    if (
        integer(oracle["inner_bytes"]) != inner
        or integer(oracle["patch_bytes"]) != patches
        or integer(oracle["packet_bytes"], 49152) != len(packet)
        or len(packet) != 65 + inner + patches
        or packet[56] != len(case["selected_rectangles"])
        or oracle["packet_sha256"] != case["packet"]["sha256"]
        or type(case["key"]) is not bool
        or type(case["promoted"]) is not bool
        or case["key"] != (packet[5] == 1)
        or case["promoted"] != (packet[5] == 2)
        or oracle["key"] is not case["key"]
        or oracle["promoted"] is not case["promoted"]
        or tuple(oracle["selected_profile"]) not in MAPS
    ):
        raise ValueError("Encoder byte/profile/flag oracle mismatch")
    duplicated_oracles(packet, oracle)
    attempts = oracle["attempts"]
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 4:
        raise ValueError("Encoder attempt count mismatch")
    for i, attempt in enumerate(attempts):
        accepted = i == len(attempts) - 1
        size = integer(attempt["attempted_complete_bytes"], 2 * 1024 * 1024)
        if (
            (attempt["roi_scale"], attempt["background_scale"]) != MAPS[i]
            or attempt["accepted"] is not accepted
            or (size <= 49152) != accepted
            or (accepted and (size != len(packet) or list(MAPS[i]) != oracle["selected_profile"]))
        ):
            raise ValueError("Encoder ordered retry oracle mismatch")
    return case


def check_report(report, case):
    """@brief Require exact scoped native bytes, decode counters and retry work fields."""
    oracle = case["encoder_oracle"]
    mandatory = case["policy"] == "mandatory"
    if (
        not isinstance(report, dict)
        or report.get("scope") != "native_encoder_fixture"
        or any(report.get(key) != case[key] for key in ("label", "id"))
        or any(report.get(key) != oracle[key] for key in ("inner_bytes", "packet_bytes"))
        or report.get("selected_patch_count") != len(case["selected_rectangles"])
        or any(
            report.get(key) is not True
            for key in (
                "inner_byte_exact",
                "patches_byte_exact",
                "ar03_byte_exact",
                "profiling_not_playback",
            )
        )
        or report.get("mandatory_policy_verified") is not mandatory
    ):
        raise ValueError("Native encoder report scope/byte/flag mismatch")
    decode = report["frozen_decode"]
    if (
        decode.get("scope") != "full_body_fixture"
        or any(decode.get(key) != case[key] for key in ("label", "id"))
        or decode.get("yuv_samples") != 518400
        or decode.get("display_words") != 345600
        or decode.get("mandatory_hud_words_verified") != (21120 if mandatory else 0)
        or decode.get("af03_exact") is not True
        or decode.get("post_banks_exact") is not True
    ):
        raise ValueError("Native encoder frozen decode oracle mismatch")
    attempts = report["policy_attempts"]
    expected = oracle["attempts"] if mandatory else []
    if not isinstance(attempts, list) or len(attempts) != len(expected):
        raise ValueError("Native encoder policy attempt count mismatch")
    for actual, frozen in zip(attempts, expected):
        if (
            actual["roi"] != frozen["roi_scale"]
            or actual["background"] != frozen["background_scale"]
            or actual["complete_bytes"] != frozen["attempted_complete_bytes"]
            or actual["accepted"] is not frozen["accepted"]
        ):
            raise ValueError("Native encoder policy attempt oracle mismatch")
        for key in ("build_ns", "validation_ns", "discard_ns"):
            integer(actual[key])


def verify(
    fixtures,
    executable,
    *,
    runner=subprocess.run,
    expected_cases=20,
    expected_source_results_sha256=PINNED_SOURCE_RESULTS_SHA256,
):
    """@brief Replay all validated source cases and aggregate actual software work only."""
    fixtures, executable = (
        Path(fixtures).resolve(strict=True),
        Path(executable).resolve(strict=True),
    )
    if not executable.is_file():
        raise ValueError("Native executable must be a regular file")
    manifest = bounded_json(fixtures / "manifest.json")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("source_commit") != MOONBUB_COMMIT:
        raise ValueError("Encoder fixture schema/source pin mismatch")
    source = descendant(fixtures, "source-results.json")
    if source.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Encoder source-results hash mismatch")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if (
        manifest.get("source_results_sha256") != expected_source_results_sha256
        or source_hash != expected_source_results_sha256
    ):
        raise ValueError("Encoder source-results hash mismatch")
    rows = manifest.get("cases")
    if not isinstance(rows, list) or len(rows) != expected_cases:
        raise ValueError("Unexpected encoder case count")
    if expected_cases == 20 and sum(row.get("policy") == "mandatory" for row in rows) != 10:
        raise ValueError("Expected ten mandatory encoder cases")
    prepared, labels = [], set()
    for row in rows:
        path = descendant(fixtures, row["case_path"])
        case = preflight(path, row)
        if case["label"] in labels:
            raise ValueError("Duplicate encoder case label")
        labels.add(case["label"])
        prepared.append((path, case))
    reports = []
    for path, case in prepared:
        result = runner(
            [str(executable), "--encoder-case", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode:
            raise ValueError(f"Native encoder failed:{case['label']}:{result.stderr}")
        report = json.loads(result.stdout)
        check_report(report, case)
        reports.append(report)
    attempts = [attempt for report in reports for attempt in report["policy_attempts"]]
    return {
        "schema": "gamebub-v20-encoder-verification-v1",
        "source_commit": MOONBUB_COMMIT,
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "scope": "native byte-exact software fixtures; not capture, transport or playback",
        "profiling_not_playback": True,
        "case_count": len(reports),
        "mandatory_case_count": sum(r["mandatory_policy_verified"] for r in reports),
        "policy_attempt_count": len(attempts),
        "policy_cost_ns": {
            key: sum(a[key] for a in attempts)
            for key in ("build_ns", "validation_ns", "discard_ns")
        },
        "cases": reports,
    }


def main(argv=None):
    """@brief Run the offline campaign and exclusively create its evidence report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.report.exists():
            raise FileExistsError(args.report)
        report = verify(args.fixtures, args.executable)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
