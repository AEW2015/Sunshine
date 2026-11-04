"""@brief Export complete mandatory-HUD body decoder fixtures from pinned MoonBub."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import prepare_v20_fixtures as common

BODY_SCHEMA = "gamebub-v20-body-case-v1"
MANIFEST_SCHEMA = "gamebub-v20-body-fixtures-v1"
MAX_CASES = 20
MAX_WIDTH = 4096
MAX_HEIGHT = 4096
DTYPE_BYTES = {"|u1": 1, "<u2": 2, "<i2": 2}


class BodyFixtureError(common.FixtureError):
    """@brief Report malformed mandatory-HUD body fixture metadata."""


def _array_shape(descriptor: dict, label: str) -> tuple[str, list[int], int]:
    """@brief Validate explicit little-endian dtype and bounded array geometry."""
    if not isinstance(descriptor, dict):
        raise BodyFixtureError(f"missing array descriptor for {label}")
    dtype = descriptor.get("dtype")
    shape = descriptor.get("shape")
    if dtype not in DTYPE_BYTES or not isinstance(shape, list) or not 1 <= len(shape) <= 3:
        raise BodyFixtureError(f"unsupported dtype or shape for {label}")
    if any(type(dim) is not int or dim <= 0 or dim > MAX_WIDTH for dim in shape):
        raise BodyFixtureError(f"invalid array dimensions for {label}")
    blob = descriptor.get("blob", descriptor)
    if not isinstance(blob, dict):
        raise BodyFixtureError(f"invalid blob descriptor for {label}")
    count = DTYPE_BYTES[dtype]
    for dim in shape:
        count *= dim
        if count > common.MAX_RAW_BYTES:
            raise BodyFixtureError(f"array exceeds size limit for {label}")
    if blob.get("raw_bytes") != count:
        raise BodyFixtureError(f"array byte count mismatch for {label}")
    return dtype, shape, count


def _array(exporter: common.Exporter, descriptor: dict, root: Path, stem: str, label: str) -> dict:
    """@brief Export a validated content-addressed array without dtype conversion."""
    dtype, shape, byte_count = _array_shape(descriptor, label)
    blob = descriptor.get("blob", descriptor)
    raw = exporter._blob(blob, common.STUDY)
    if len(raw) != byte_count:
        raise BodyFixtureError(f"array length mismatch for {label}")
    path = f"{stem}.bin"
    common._write_new(root, path, raw)
    return {
        "dtype": dtype,
        "shape": shape,
        "path": path,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _require_array_shape(array: dict, dtype: str, shape: list[int], label: str) -> None:
    """@brief Require an exported array to use the exact declared geometry and dtype."""
    if array["dtype"] != dtype or array["shape"] != shape:
        raise BodyFixtureError(f"unexpected dtype or geometry for {label}")


def _banks(
    exporter: common.Exporter,
    banks: dict,
    root: Path,
    stem: str,
    label: str,
    include_planes: bool,
    width: int,
    height: int,
) -> dict:
    """@brief Export bank identities and, for preconditions, all exact plane samples."""
    if not isinstance(banks, dict) or set(banks) != {"0", "1"}:
        raise BodyFixtureError(f"invalid bank set for {label}")
    result = {}
    for bank_index in ("0", "1"):
        bank = banks[bank_index]
        if bank is None:
            result[bank_index] = None
            continue
        if not isinstance(bank, dict):
            raise BodyFixtureError(f"invalid bank {bank_index} for {label}")
        bank_id, tag = bank.get("id"), bank.get("tag")
        if (
            type(bank_id) is not int
            or not 0 <= bank_id <= 0xFFFFFFFF
            or not isinstance(tag, str)
            or not re.fullmatch(r"[0-9a-f]{32}", tag)
        ):
            raise BodyFixtureError(f"invalid bank identity for {label}")
        entry = {"id": bank_id, "tag": tag}
        if include_planes:
            planes = bank.get("planes")
            if not isinstance(planes, list) or len(planes) != 3:
                raise BodyFixtureError(f"invalid bank planes for {label}")
            entry["planes"] = [
                _array(exporter, plane, root, f"{stem}.bank{bank_index}.plane{n}", label)
                for n, plane in enumerate(planes)
            ]
            for n, plane in enumerate(entry["planes"]):
                shape = [[height, width], [height // 2, width // 2], [height // 2, width // 2]][n]
                _require_array_shape(plane, "<i2", shape, f"{label} bank {bank_index} plane {n}")
        result[bank_index] = entry
    return result


class BodyExporter(common.Exporter):
    """@brief Export the 20 pinned mandatory-HUD packet and decoder vectors."""

    def _case(self, case: dict, vector: dict, root: Path) -> dict:
        """@brief Validate and materialize one complete decoder input and expected output."""
        if not isinstance(case, dict) or not isinstance(vector, dict):
            raise BodyFixtureError("invalid case or vector metadata")
        scene, policy, fixture_id = case.get("scene"), case.get("policy"), vector.get("id")
        if (
            not isinstance(scene, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", scene)
            or policy not in ("baseline", "mandatory")
            or type(fixture_id) is not int
            or fixture_id < 0
        ):
            raise BodyFixtureError("invalid mandatory-HUD fixture identity")
        label = f"{scene}-{policy}-{fixture_id:02d}"
        manifest = case.get("manifest")
        if not isinstance(manifest, dict):
            raise BodyFixtureError(f"missing case manifest for {label}")
        width, height = manifest.get("target_width"), manifest.get("target_height")
        if (
            type(width) is not int
            or type(height) is not int
            or not (1 <= width <= MAX_WIDTH and 1 <= height <= MAX_HEIGHT)
            or width % 2
            or height % 2
        ):
            raise BodyFixtureError(f"invalid geometry for {label}")
        rows = case.get("rows", [])
        if not isinstance(rows, list):
            raise BodyFixtureError(f"invalid state rows for {label}")
        row = next(
            (item for item in rows if isinstance(item, dict) and item.get("id") == fixture_id), None
        )
        if row is None:
            raise BodyFixtureError(f"missing state row for {label}")
        case_root = root / "cases"
        case_root.mkdir(exist_ok=True)
        stem = label
        packet = self._blob(
            vector.get("packet", {}), common.STUDY, max_raw_bytes=common.MAX_AR03_BYTES
        )
        ack = self._blob(vector.get("ack", {}), common.STUDY, max_raw_bytes=43)
        if not packet or len(packet) > common.MAX_AR03_BYTES or len(ack) != 43:
            raise BodyFixtureError(f"invalid packet or ACK length for {label}")
        common._write_new(case_root, f"{stem}.ar03", packet)
        common._write_new(case_root, f"{stem}.af03", ack)
        source = _array(self, vector.get("source"), case_root, f"{stem}.source.rgb", label)
        _require_array_shape(source, "|u1", [height, width, 3], f"{label} source RGB")
        decoded = vector.get("decoded_yuv")
        if not isinstance(decoded, list) or len(decoded) != 3:
            raise BodyFixtureError(f"invalid decoded YUV planes for {label}")
        decoded_yuv = [
            _array(self, d, case_root, f"{stem}.decoded.yuv{n}", label)
            for n, d in enumerate(decoded)
        ]
        for n, plane in enumerate(decoded_yuv):
            shape = [[height, width], [height // 2, width // 2], [height // 2, width // 2]][n]
            _require_array_shape(plane, "<i2", shape, f"{label} decoded YUV plane {n}")
        display = _array(
            self, vector.get("display_rgb565"), case_root, f"{stem}.expected.rgb565", label
        )
        _require_array_shape(display, "<u2", [height, width], f"{label} display RGB565")
        pre_banks = _banks(
            self, vector.get("pre_banks"), case_root, stem, label, True, width, height
        )
        post_banks = _banks(
            self, vector.get("post_banks"), case_root, stem, label, False, width, height
        )
        row_data = {
            key: row.get(key)
            for key in (
                "reference_bank",
                "reference_id",
                "reference_tag",
                "destination_bank",
                "stored_tag",
            )
        }
        state_before = row.get("state_before")
        if not isinstance(state_before, dict) or type(state_before.get("last_issued")) is not int:
            raise BodyFixtureError(f"missing receiver last frame state for {label}")
        row_data["encoder_last_issued"] = state_before["last_issued"]
        if any(value is None for value in row_data.values()):
            raise BodyFixtureError(f"missing reference/destination bank state for {label}")
        if type(vector.get("key")) is not bool or type(vector.get("promoted")) is not bool:
            raise BodyFixtureError(f"invalid frame flags for {label}")
        if (
            type(row_data["reference_bank"]) is not int
            or not 0 <= row_data["reference_bank"] <= 255
            or type(row_data["destination_bank"]) is not int
            or not 0 <= row_data["destination_bank"] <= 255
            or type(row_data["reference_id"]) is not int
            or not 0 <= row_data["reference_id"] <= 0xFFFFFFFF
            or not isinstance(row_data["reference_tag"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", row_data["reference_tag"])
        ):
            raise BodyFixtureError(f"invalid reference or destination state for {label}")
        payload = {
            "schema": BODY_SCHEMA,
            "label": label,
            "scene": scene,
            "policy": policy,
            "id": fixture_id,
            "key": vector.get("key"),
            "promoted": vector.get("promoted"),
            "geometry": {"width": width, "height": height},
            "packet": {
                "path": f"{stem}.ar03",
                "bytes": len(packet),
                "sha256": hashlib.sha256(packet).hexdigest(),
            },
            "ack": {
                "path": f"{stem}.af03",
                "bytes": len(ack),
                "sha256": hashlib.sha256(ack).hexdigest(),
            },
            "source_rgb": source,
            "decoded_yuv": decoded_yuv,
            "display_rgb565": display,
            "pre_banks": pre_banks,
            "post_banks": post_banks,
            "epoch": 1,
            "last_frame": -1,
            "replay_state_note": "isolated packet: sequence baseline unset; encoder last_issued retained as provenance only",
            "state": row_data,
            "selected_rectangles": vector.get("selected_rectangles"),
            "omitted_rectangles": vector.get("omitted_rectangles"),
            "rgb_sha256": vector.get("rgb_sha256"),
        }
        case_path = f"{stem}.json"
        case_bytes = json.dumps(payload, indent=2).encode() + b"\n"
        common._write_new(case_root, case_path, case_bytes)
        return {
            "label": label,
            "case_path": f"cases/{case_path}",
            "case_sha256": hashlib.sha256(case_bytes).hexdigest(),
            "policy": policy,
            "id": fixture_id,
            "scene": scene,
            "packet_sha256": payload["packet"]["sha256"],
            "ack_sha256": payload["ack"]["sha256"],
        }

    def export(self, output: Path) -> dict:
        """@brief Create a new directory containing the complete 20-case body fixture set."""
        output = output.resolve()
        if output.exists():
            raise BodyFixtureError(f"output already exists: {output}")
        output.mkdir(parents=True)
        results_raw = self.read_moonbub(f"{common.STUDY}/results.json")
        results = common._json(results_raw, "mandatory-HUD results")
        if not isinstance(results, dict) or results.get("schema") != "gamebub-mandatory-hud-v1":
            raise BodyFixtureError("unexpected mandatory-HUD result schema")
        if not isinstance(results.get("cases"), list):
            raise BodyFixtureError("invalid mandatory-HUD cases index")
        rows = []
        labels = set()
        for case in results.get("cases", []):
            if not isinstance(case, dict) or not isinstance(case.get("vectors"), list):
                raise BodyFixtureError("invalid mandatory-HUD case entry")
            for vector in case.get("vectors", []):
                row = self._case(case, vector, output)
                if row["label"] in labels:
                    raise BodyFixtureError(f"duplicate mandatory fixture {row['label']}")
                labels.add(row["label"])
                rows.append(row)
        if len(rows) != MAX_CASES:
            raise BodyFixtureError(f"expected {MAX_CASES} mandatory fixtures, found {len(rows)}")
        common._write_new(output, "source-results.json", results_raw)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "source_commit": common.MOONBUB_COMMIT,
            "source_results_sha256": hashlib.sha256(results_raw).hexdigest(),
            "cases": rows,
        }
        common._write_new(output, "manifest.json", json.dumps(manifest, indent=2).encode() + b"\n")
        return manifest


def main(argv=None) -> int:
    """@brief Export body fixtures from a pinned no-checkout MoonBub repository."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=Path, required=True, help="MoonBub Git repository")
    parser.add_argument("--output", type=Path, required=True, help="new output directory")
    args = parser.parse_args(argv)
    manifest = BodyExporter(args.reference_repo).export(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "cases": len(manifest["cases"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
