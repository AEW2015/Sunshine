"""@brief Run an explicit sequential bitrate sweep against the pinned localhost receiver.

The sweep invokes only reference_loopback.run_reference, which binds the receiver
to an ephemeral 127.0.0.1 UDP port. Results do not measure physical networking,
FPGA decode, or display.
"""

import argparse
import json
import math
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import av

from reference_loopback import REVISION, run_reference

MAX_RATES = 32
MIN_RATE_MBPS = 0.1
MAX_RATE_MBPS = 1000.0
MAX_FRAMES = 1_080_000
MAX_TOTAL_FRAMES = 1_080_000
MAX_DEADLINE_MS = 60_000.0


def parse_rates(value):
    """@brief Parse an explicitly ordered comma-separated rate list.

    @param value User-supplied decimal rates in Mbps.
    @return Tuple of finite, strictly increasing Mbps values.
    @throws argparse.ArgumentTypeError If syntax, order, or bounds are invalid.
    """
    try:
        rates = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Rates must be comma-separated numbers") from error
    if (
        not 1 <= len(rates) <= MAX_RATES
        or any(
            not math.isfinite(rate) or not MIN_RATE_MBPS <= rate <= MAX_RATE_MBPS for rate in rates
        )
        or any(left >= right for left, right in pairwise(rates))
    ):
        raise argparse.ArgumentTypeError(
            f"Provide 1..{MAX_RATES} strictly increasing rates from "
            f"{MIN_RATE_MBPS} to {MAX_RATE_MBPS} Mbps"
        )
    return rates


def _validate(args):
    """@brief Validate fixed sweep inputs before creating any output.

    @param args Parsed options or a compatible namespace.
    @return Normalized paths and rates.
    @throws ValueError If an input is missing, outside bounds, or not a file/directory.
    """
    rates = tuple(args.rates)
    if (
        not rates
        or len(rates) > MAX_RATES
        or any(
            type(rate) not in (int, float)
            or not math.isfinite(rate)
            or not MIN_RATE_MBPS <= rate <= MAX_RATE_MBPS
            for rate in rates
        )
        or any(left >= right for left, right in pairwise(rates))
    ):
        raise ValueError("Rates must be strictly increasing and within the supported bounds")
    if type(args.frames) is not int or not 1 <= args.frames <= MAX_FRAMES:
        raise ValueError(f"Frame count must be 1..{MAX_FRAMES}")
    if args.frames * len(rates) > MAX_TOTAL_FRAMES:
        raise ValueError(f"Total sweep frames must not exceed {MAX_TOTAL_FRAMES}")
    if type(args.fps) is not int or not 1 <= args.fps <= 30:
        raise ValueError("FPS must be 1..30")
    if (
        type(args.quality) is not int
        or type(args.min_quality) is not int
        or not 1 <= args.min_quality <= args.quality <= 95
    ):
        raise ValueError("JPEG quality must satisfy 1 <= min-quality <= quality <= 95")
    if (
        type(args.max_age_ms) not in (int, float)
        or not math.isfinite(args.max_age_ms)
        or not 0.001 <= args.max_age_ms <= MAX_DEADLINE_MS
    ):
        raise ValueError(f"Maximum age must be 0.001..{MAX_DEADLINE_MS} ms")

    reference_repo = Path(args.reference_repo).expanduser().resolve()
    clip = Path(args.clip).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not reference_repo.is_dir():
        raise ValueError(f"Reference repository is not a directory: {reference_repo}")
    if not clip.is_file():
        raise ValueError(f"Clip is not a file: {clip}")
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    return reference_repo, clip, output_dir, rates


def _write_record(output, record):
    """@brief Append and flush one JSONL result record.

    @param output Open exclusive sweep results file.
    @param record JSON-serializable event object.
    """
    output.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
    output.flush()


def _stage_health(result, log_path):
    """@brief Classify receiver completion and internal sender, peer, or log errors.

    @param result Reference runner result mapping.
    @param log_path Stage event log path.
    @return A health mapping with a boolean and specific error reasons.

    Stale-frame and send-failure counts are intentionally excluded: those are
    expected overload signals. A stage with no complete receiver frames is unhealthy.
    """
    errors = []
    if not isinstance(result, dict):
        return {"healthy": False, "errors": ["invalid_runner_result"]}
    receiver = result.get("receiver")
    sender = result.get("sender")
    if not isinstance(receiver, dict) or not isinstance(sender, dict):
        return {"healthy": False, "errors": ["missing_receiver_or_sender_summary"]}

    if type(receiver.get("complete")) is not int or receiver["complete"] <= 0:
        errors.append("no_complete_receiver_frames")
    if receiver.get("invalid_datagrams", 0):
        errors.append("receiver_invalid_datagrams")
    if receiver.get("reply_errors", 0):
        errors.append("receiver_reply_errors")

    pipeline = sender.get("pipeline")
    if not isinstance(pipeline, dict):
        errors.append("missing_pipeline_summary")
    else:
        if pipeline.get("last_error"):
            errors.append("pipeline_error")
        pipeline_counts = pipeline.get("counts", {})
        if not isinstance(pipeline_counts, dict):
            errors.append("invalid_pipeline_counts")
        elif pipeline_counts.get("encode_failures", 0):
            errors.append("pipeline_encode_failures")

    logging = sender.get("logging")
    if not isinstance(logging, dict):
        errors.append("missing_logging_summary")
    else:
        if logging.get("error"):
            errors.append("logging_error")
        if logging.get("dropped", 0):
            errors.append("logging_dropped_events")

    counts = sender.get("counts", {})
    if not isinstance(counts, dict):
        errors.append("invalid_sender_counts")
    else:
        if counts.get("socket_failures", 0):
            errors.append("sender_socket_failures")
        if counts.get("packet_failures", 0):
            errors.append("sender_packet_failures")

    try:
        with log_path.open(encoding="utf-8") as stage_log:
            for line in stage_log:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise TypeError("event is not an object")
                if event.get("event") in {
                    "capture_error",
                    "encode_error",
                    "send_error",
                    "feedback_error",
                }:
                    errors.append(f"event_{event['event']}")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        errors.append("stage_log_unreadable_or_invalid")

    return {"healthy": not errors, "errors": sorted(set(errors))}


def run_sweep(args, runner=None):
    """@brief Sequentially run each cap against the pinned reference on localhost.

    @param args Explicit sweep configuration.
    @param runner Injectable reference runner for tests.
    @return Summary with counts and the newly created output paths.
    @throws FileExistsError If the requested output directory already exists.
    @throws OSError If output creation or report writing fails.
    @throws ValueError If sweep inputs are invalid.

    The reference runner owns peer cleanup on ordinary errors and interruption.
    Logs remain in the new output directory so failed or partial stages are reviewable.
    """
    reference_repo, clip, output_dir, rates = _validate(args)
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir = output_dir.resolve()
    results_path = output_dir / "results.jsonl"
    runner = run_reference if runner is None else runner
    records = []
    interrupted = False

    with results_path.open("x", encoding="utf-8", newline="\n") as output:
        _write_record(
            output,
            {
                "event": "sweep",
                "status": "started",
                "scope": "pinned localhost receiver ingress only; no physical network, hardware decode, or display claim",
                "reference_revision": REVISION,
                "reference_repo": str(reference_repo),
                "clip": str(clip),
                "rates_mbps": rates,
                "fps": args.fps,
                "frames_per_stage": args.frames,
                "quality": args.quality,
                "min_quality": args.min_quality,
                "max_age_ms": args.max_age_ms,
                "hardware_playback_verified": False,
            },
        )
        for index, rate in enumerate(rates, start=1):
            log_path = output_dir / f"stage-{index:02d}.jsonl"
            stage = {
                "event": "stage",
                "index": index,
                "rate_mbps": rate,
                "log": str(log_path),
            }
            run_args = SimpleNamespace(
                reference_repo=reference_repo,
                clip=clip,
                log=log_path,
                fps=args.fps,
                mbps=rate,
                max_age_ms=args.max_age_ms,
                quality=args.quality,
                min_quality=args.min_quality,
                frames=args.frames,
                loop=True,
            )
            try:
                _write_record(output, {**stage, "status": "running"})
                result = runner(run_args)
            except KeyboardInterrupt:
                interrupted = True
                records.append({**stage, "status": "interrupted"})
                _write_record(output, records[-1])
                for later_index, later_rate in enumerate(rates[index:], start=index + 1):
                    skipped = {
                        "event": "stage",
                        "index": later_index,
                        "rate_mbps": later_rate,
                        "log": str(output_dir / f"stage-{later_index:02d}.jsonl"),
                        "status": "not_run",
                        "reason": "interrupted during an earlier stage",
                    }
                    records.append(skipped)
                    _write_record(output, skipped)
                break
            except Exception as error:  # noqa: BLE001 - report each failed cap and continue.
                record = {
                    **stage,
                    "status": "failed",
                    "health": {"healthy": False, "errors": ["stage_exception"]},
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            else:
                health = _stage_health(result, log_path)
                record = {
                    **stage,
                    "status": "completed" if health["healthy"] else "failed",
                    "health": health,
                    "result": result,
                }
            records.append(record)
            _write_record(output, record)

        completed = sum(record["status"] == "completed" for record in records)
        failed = sum(record["status"] == "failed" for record in records)
        not_run = sum(record["status"] == "not_run" for record in records)
        summary = {
            "event": "sweep_summary",
            "status": "interrupted" if interrupted else "failed" if failed else "finished",
            "completed": completed,
            "failed": failed,
            "not_run": not_run,
            "interrupted": interrupted,
            "results": str(results_path),
            "output_dir": str(output_dir),
            "hardware_playback_verified": False,
        }
        _write_record(output, summary)

    return summary


def main(argv=None):
    """@brief Parse explicit sweep settings and print the recorded outcome summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=Path, required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rates", type=parse_rates, required=True, metavar="MBPS,...")
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--quality", type=int, required=True)
    parser.add_argument("--min-quality", type=int, required=True)
    parser.add_argument("--max-age-ms", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        summary = run_sweep(args)
    except (FileExistsError, OSError, ValueError, av.FFmpegError) as error:
        parser.error(str(error))
    print(json.dumps(summary, indent=2))
    if summary["interrupted"]:
        return 130
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
