"""@brief Stream and summarize a bounded Game Bub sender JSONL log."""

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
DEFAULT_MAX_SAMPLES = 100_000


class LogFormatError(ValueError):
    """@brief Identify an invalid sender-log record or oversized input."""


class Reservoir:
    """@brief Keep a reproducible, uniformly sampled bounded set of values."""

    def __init__(self, limit, rng):
        """@brief Create a reservoir with a fixed maximum size.

        @param limit Maximum retained values.
        @param rng Random generator used for reservoir replacement.
        """
        self.limit = limit
        self.rng = rng
        self.seen = 0
        self.values = []
        self.population_max = None

    def add(self, value):
        """@brief Add a value using Algorithm R reservoir sampling.

        @param value Finite numeric observation.
        """
        self.seen += 1
        self.population_max = (
            value if self.population_max is None else max(self.population_max, value)
        )
        if len(self.values) < self.limit:
            self.values.append(value)
        else:
            index = self.rng.randrange(self.seen)
            if index < self.limit:
                self.values[index] = value

    def summary(self):
        """@brief Return nearest-rank percentiles and explicit sampling details.

        @return Bounded sample count, population count, method, and p50/p95/max.
        """
        ordered = sorted(self.values)

        def nearest_rank(percentile):
            """@brief Select the nearest-rank percentile from the retained sample."""
            if not ordered:
                return None
            return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]

        return {
            "population_count": self.seen,
            "sample_count": len(ordered),
            "sampling": "uniform reservoir sampling (Algorithm R)",
            "quantile_method": "nearest rank on the retained reservoir sample",
            "p50": nearest_rank(0.50),
            "p95": nearest_rank(0.95),
            "population_max": self.population_max,
            "sample_max": max(ordered) if ordered else None,
        }


def _read_records(path):
    """@brief Yield valid JSON objects from a capped JSONL file.

    @param path Sender log path.
    @return Pairs of one-based line number and decoded JSON object.
    @throws LogFormatError For invalid interior records or exceeded size limits.

    An invalid, unterminated final record is treated as a torn write. Invalid
    newline-terminated records always fail, including the last one.
    """
    size = path.stat().st_size
    if size > MAX_LOG_BYTES:
        raise LogFormatError(f"Log exceeds {MAX_LOG_BYTES} byte limit")
    with path.open("rb") as stream:
        line_number = 0
        bytes_read = 0
        while True:
            raw = stream.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                return
            bytes_read += len(raw)
            if bytes_read > MAX_LOG_BYTES:
                raise LogFormatError(f"Log exceeds {MAX_LOG_BYTES} byte limit while reading")
            line_number += 1
            if len(raw) > MAX_RECORD_BYTES and not raw.endswith(b"\n"):
                raise LogFormatError(f"Line {line_number} exceeds record size limit")
            if len(raw) > MAX_RECORD_BYTES:
                raise LogFormatError(f"Line {line_number} exceeds record size limit")
            try:
                record = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                if not raw.endswith(b"\n") and stream.peek(1) == b"":
                    yield line_number, None
                    return
                raise LogFormatError(f"Invalid JSON on line {line_number}: {error}") from error
            if not isinstance(record, dict):
                raise LogFormatError(f"Line {line_number} must contain a JSON object")
            yield line_number, record


def analyze_log(path, max_samples=DEFAULT_MAX_SAMPLES, seed=0):
    """@brief Summarize sender events and bounded timing samples.

    @param path Path to the sender JSONL log.
    @param max_samples Maximum retained measurements per timing metric.
    @param seed Seed for reproducible reservoir sampling.
    @return JSON-serializable summary of events, sends, timing, counters and summary.
    @throws ValueError If max_samples or seed is invalid, or log data is malformed.

    Timing uses sender-recorded host-assigned capture timestamp-to-send age and
    encoded queue age, separated by send completion. The capture timestamp is
    assigned after frame acquisition and can exclude earlier source capture or
    waiting delay. Neither measure is receiver display latency. No pixel or
    image payload is read.
    """
    if type(max_samples) is not int or not 1 <= max_samples <= DEFAULT_MAX_SAMPLES:
        raise ValueError(f"max_samples must be between 1 and {DEFAULT_MAX_SAMPLES}")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rng = random.Random(seed)
    timings = {
        status: {
            "host_assigned_timestamp_to_send_age_ms": Reservoir(max_samples, rng),
            "encoded_queue_age_ms": Reservoir(max_samples, rng),
        }
        for status in ("complete", "incomplete")
    }
    events = Counter()
    qualities = Counter()
    send_complete = Counter()
    encoded_bytes = 0
    encoded_events = 0
    counter_events = 0
    receiver_counter_deltas = Counter()
    receiver_counter_snapshot = {}
    receiver_counter_resets = 0
    log_summary = None
    records = 0
    ignored_trailing_record = False

    for _, event in _read_records(path):
        if event is None:
            ignored_trailing_record = True
            continue
        records += 1
        name = event.get("event")
        if not isinstance(name, str) or not name:
            raise LogFormatError(f"Record {records} has no non-empty event name")
        events[name] += 1
        if name == "encode":
            encoded_events += 1
            amount = event.get("bytes")
            if type(amount) is int and amount >= 0:
                encoded_bytes += amount
            quality = event.get("quality")
            if type(quality) is int:
                qualities[str(quality)] += 1
        elif name == "send":
            status = "complete" if event.get("complete") is True else "incomplete"
            send_complete[status] += 1
            for field, reservoir in (
                ("age_ms", timings[status]["host_assigned_timestamp_to_send_age_ms"]),
                ("queue_age_ms", timings[status]["encoded_queue_age_ms"]),
            ):
                value = event.get(field)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                ):
                    reservoir.add(float(value))
        elif name == "receiver_counters":
            counter_events += 1
            for key in ("received_delta", "dropped_delta"):
                value = event.get(key)
                if type(value) is int and value >= 0:
                    receiver_counter_deltas[key] += value
            for key in ("received_frames", "dropped_frames"):
                value = event.get(key)
                if type(value) is int and value >= 0:
                    receiver_counter_snapshot[key] = value
            if event.get("reset") is True:
                receiver_counter_resets += 1
        elif name == "summary":
            log_summary = event

    return {
        "scope": "sender-side log analysis; no receiver display or source capture latency claim",
        "records": records,
        "events": dict(sorted(events.items())),
        "sends": {
            "complete": send_complete["complete"],
            "incomplete": send_complete["incomplete"],
        },
        "encoded": {"events": encoded_events, "jpeg_bytes": encoded_bytes},
        "quality_counts": dict(sorted(qualities.items())),
        "send_timing_by_completion": {
            status: {name: metric.summary() for name, metric in values.items()}
            for status, values in timings.items()
        },
        "receiver_counters": {
            "event_count": counter_events,
            "reported_delta_totals": dict(sorted(receiver_counter_deltas.items())),
            "last_cumulative_snapshot": receiver_counter_snapshot,
            "reset_events": receiver_counter_resets,
            "limits": "Delta totals reflect sender-reported deltas across recorded baseline/reset events; cumulative fields are last snapshots, never summed.",
        },
        "sender_log_summary": log_summary,
        "sender_log_summary_status": "present"
        if log_summary is not None
        else ("missing_or_truncated" if ignored_trailing_record else "missing"),
        "truncated_final_record_ignored": ignored_trailing_record,
    }


def main(argv=None):
    """@brief Parse CLI options and print the sender-log analysis as JSON.

    @param argv Optional command-line argument sequence.
    @return Process exit status (zero on successful analysis).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Sender JSONL log to analyze")
    parser.add_argument("--max-samples", type=int, default=DEFAULT_MAX_SAMPLES)
    parser.add_argument("--seed", type=int, default=0, help="Reservoir sampling seed")
    args = parser.parse_args(argv)
    try:
        result = analyze_log(args.log, args.max_samples, args.seed)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
