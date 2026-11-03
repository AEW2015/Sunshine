"""@brief Tests for bounded sender JSONL log analysis."""

import io
import json
import random
import runpy
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import analyze_sender_log
from analyze_sender_log import LogFormatError, Reservoir, analyze_log


class SenderLogAnalysisTests(unittest.TestCase):
    """@brief Validate event summaries, timing sampling, and damaged logs."""

    def _write(self, directory, content):
        """@brief Write test bytes and return their path."""
        path = Path(directory) / "sender.jsonl"
        path.write_bytes(content)
        return path

    def test_summarizes_events_sends_timing_counters_and_summary(self):
        """@brief Aggregate deltas but retain cumulative counters as snapshots."""
        records = [
            {"event": "encode", "bytes": 500, "quality": 70},
            {"event": "send", "complete": True, "age_ms": 12, "queue_age_ms": 2},
            {"event": "send", "complete": False, "age_ms": 22, "queue_age_ms": 4},
            {
                "event": "receiver_counters",
                "received_delta": 1,
                "dropped_delta": 2,
                "received_frames": 8,
                "dropped_frames": 3,
                "reset": True,
            },
            {
                "event": "receiver_counters",
                "received_delta": 2,
                "dropped_delta": 1,
                "received_frames": 10,
                "dropped_frames": 4,
                "reset": False,
            },
            {"event": "summary", "duration_s": 1.5},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(
                directory, "".join(json.dumps(item) + "\n" for item in records).encode()
            )
            result = analyze_log(path, max_samples=1)

        self.assertEqual(
            result["events"], {"encode": 1, "receiver_counters": 2, "send": 2, "summary": 1}
        )
        self.assertEqual(result["sends"], {"complete": 1, "incomplete": 1})
        self.assertEqual(result["encoded"], {"events": 1, "jpeg_bytes": 500})
        self.assertEqual(result["quality_counts"], {"70": 1})
        counters = result["receiver_counters"]
        self.assertEqual(counters["event_count"], 2)
        self.assertEqual(
            counters["reported_delta_totals"], {"dropped_delta": 3, "received_delta": 3}
        )
        self.assertEqual(
            counters["last_cumulative_snapshot"], {"received_frames": 10, "dropped_frames": 4}
        )
        self.assertEqual(counters["reset_events"], 1)
        self.assertIn("baseline/reset", counters["limits"])
        self.assertEqual(result["sender_log_summary"]["duration_s"], 1.5)
        self.assertEqual(result["sender_log_summary_status"], "present")
        complete = result["send_timing_by_completion"]["complete"]
        incomplete = result["send_timing_by_completion"]["incomplete"]
        metric = complete["host_assigned_timestamp_to_send_age_ms"]
        self.assertEqual(metric["population_count"], 1)
        self.assertIn("reservoir", metric["sampling"])
        self.assertIn("nearest rank", metric["quantile_method"])
        self.assertEqual(incomplete["encoded_queue_age_ms"]["population_count"], 1)
        self.assertIn("no receiver display", result["scope"])

    def test_empty_and_truncated_final_records_are_reported(self):
        """@brief Accept empty logs and report an unterminated torn tail."""
        with tempfile.TemporaryDirectory() as directory:
            empty = self._write(directory, b"")
            self.assertEqual(analyze_log(empty)["records"], 0)
            self.assertEqual(analyze_log(empty)["sender_log_summary_status"], "missing")
            path = self._write(directory, b'{"event":"send","complete":true}\n{"event":')
            result = analyze_log(path)
        self.assertEqual(result["records"], 1)
        self.assertTrue(result["truncated_final_record_ignored"])
        self.assertEqual(result["sender_log_summary_status"], "missing_or_truncated")

    def test_invalid_interior_or_terminated_final_records_fail(self):
        """@brief Reject malformed complete records rather than hiding corruption."""
        with tempfile.TemporaryDirectory() as directory:
            for content in (b'{"event":"ok"}\nnope\n', b"nope\n"):
                path = self._write(directory, content)
                with (
                    self.subTest(content=content),
                    self.assertRaisesRegex(LogFormatError, "Invalid JSON"),
                ):
                    analyze_log(path)

    def test_nonfinite_numbers_are_rejected_anywhere_in_a_record(self):
        """@brief Reject non-standard constants and exponent overflow, including tails."""
        tokens = (b"NaN", b"Infinity", b"-Infinity", b"1e999")
        with tempfile.TemporaryDirectory() as directory:
            for token in tokens:
                content = b'{"event":"x","nested":[{"value":' + token + b"}]}\n"
                path = self._write(directory, content)
                with (
                    self.subTest(token=token),
                    self.assertRaisesRegex(LogFormatError, "Non-finite JSON number on line 1"),
                ):
                    analyze_log(path)
            path = self._write(directory, b'{"event":"x","value":NaN}')
            with self.assertRaisesRegex(LogFormatError, "Non-finite JSON number"):
                analyze_log(path)

    def test_limits_and_record_shape_are_validated(self):
        """@brief Enforce bounded samples and require object records with event names."""
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, b"[]\n")
            limits = (0, -1, True, analyze_sender_log.DEFAULT_MAX_SAMPLES + 1)
            for limit in limits:
                with self.subTest(limit=limit), self.assertRaises(ValueError):
                    analyze_log(path, max_samples=limit)
            with self.assertRaisesRegex(LogFormatError, "JSON object"):
                analyze_log(path)
            path = self._write(directory, b'{"other":1}\n')
            with self.assertRaisesRegex(LogFormatError, "event name"):
                analyze_log(path)

    def test_population_max_is_exact_when_sample_max_is_lower(self):
        """@brief Keep the true maximum separately from sampled maximum."""
        reservoir = Reservoir(1, random.Random(0))
        for value in (1.0, 10.0):
            reservoir.add(value)
        summary = reservoir.summary()
        self.assertEqual(summary["population_max"], 10.0)
        self.assertEqual(summary["sample_max"], 1.0)

    def test_reservoir_replaces_an_existing_sample(self):
        """@brief Exercise Algorithm R replacement when its chosen slot is retained."""

        class FirstSlot:
            """@brief Choose reservoir slot zero deterministically."""

            def randrange(self, stop):
                """@brief Return the first valid index."""
                return 0

        reservoir = Reservoir(1, FirstSlot())
        reservoir.add(1.0)
        reservoir.add(2.0)
        self.assertEqual(reservoir.values, [2.0])

    def test_file_and_record_limits_reject_oversized_inputs(self):
        """@brief Cover stat-size and both newline and unterminated line bounds."""
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, b"123456")
            with (
                patch.object(analyze_sender_log, "MAX_LOG_BYTES", 5),
                self.assertRaisesRegex(LogFormatError, "byte limit"),
            ):
                analyze_log(path)
            for content in (b"123456", b"12345\n"):
                path = self._write(directory, content)
                with (
                    patch.object(analyze_sender_log, "MAX_LOG_BYTES", 100),
                    patch.object(analyze_sender_log, "MAX_RECORD_BYTES", 5),
                    self.assertRaisesRegex(LogFormatError, "record size limit"),
                ):
                    analyze_log(path)

    def test_invalid_seed_and_ignored_bad_optional_fields(self):
        """@brief Reject non-integer seed and ignore invalid optional measurements."""
        records = [
            {"event": "encode", "bytes": -1, "quality": True},
            {"event": "encode", "bytes": "20", "quality": "bad"},
            {
                "event": "receiver_counters",
                "received_delta": -1,
                "dropped_delta": False,
                "received_frames": -2,
                "dropped_frames": "bad",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(
                directory, "".join(json.dumps(item) + "\n" for item in records).encode()
            )
            with self.assertRaisesRegex(ValueError, "seed must be an integer"):
                analyze_log(path, seed=True)
            result = analyze_log(path)
        self.assertEqual(result["encoded"]["jpeg_bytes"], 0)
        self.assertEqual(result["quality_counts"], {})
        self.assertEqual(result["receiver_counters"]["reported_delta_totals"], {})
        self.assertEqual(result["receiver_counters"]["last_cumulative_snapshot"], {})

    def test_read_limit_is_enforced_even_when_stat_size_is_stale(self):
        """@brief Enforce the cumulative byte cap while consuming the file."""
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, b'{"event":"x"}\n')
            stale_stat = type("Stat", (), {"st_size": 0})()
            with (
                patch.object(analyze_sender_log, "MAX_LOG_BYTES", 5),
                patch.object(Path, "stat", return_value=stale_stat),
                self.assertRaisesRegex(LogFormatError, "while reading"),
            ):
                analyze_log(path)

    def test_cli_prints_json_and_reports_input_errors(self):
        """@brief Exercise successful CLI output and parser error handling."""
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, b'{"event":"summary"}\n')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(analyze_sender_log.main([str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["sender_log_summary_status"], "present")
            with self.assertRaises(SystemExit) as error:
                analyze_sender_log.main([str(Path(directory) / "absent.jsonl")])
            self.assertEqual(error.exception.code, 2)

    def test_cli_reports_nonfinite_json_as_a_parser_error(self):
        """@brief Keep invalid numeric tokens from failing later during output."""
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, b'{"event":"summary","nested":{"value":1e999}}\n')
            errors = io.StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit) as error:
                analyze_sender_log.main([str(path)])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("Non-finite JSON number on line 1", errors.getvalue())

    def test_module_entry_point_exits_successfully(self):
        """@brief Exercise the script guard and successful process exit path."""
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(directory, b'{"event":"summary"}\n')
            output = io.StringIO()
            with (
                patch("sys.argv", [analyze_sender_log.__file__, str(path)]),
                redirect_stdout(output),
                self.assertRaises(SystemExit) as error,
            ):
                runpy.run_path(analyze_sender_log.__file__, run_name="__main__")
            self.assertEqual(error.exception.code, 0)
            self.assertEqual(json.loads(output.getvalue())["sender_log_summary_status"], "present")

    def test_reservoir_empty_percentiles_are_null(self):
        """@brief Return null percentile metrics when there are no observations."""
        self.assertIsNone(Reservoir(3, random.Random(1)).summary()["p50"])


if __name__ == "__main__":
    unittest.main()
