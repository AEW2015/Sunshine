"""@brief Tests for bounded, nonblocking JSONL logging."""

import io
import threading
import unittest

from event_log import EventLog


class EventLogTests(unittest.TestCase):
    """@brief Exercise queue and file bounds, blocked writers, and errors."""

    def test_blocked_writer_does_not_block_producer_and_queue_is_bounded(self):
        """@brief A stalled file write fills only the configured waiting buffer."""
        entered, release = threading.Event(), threading.Event()

        class SlowFile(io.StringIO):
            """@brief Controlled writer that blocks until released by the test."""

            def write(self, value):
                """@brief Hold the first write to model slow storage."""
                entered.set()
                if not release.wait(5):
                    raise OSError("writer timed out")
                return super().write(value)

        output = SlowFile()
        log = EventLog(output, max_queued_bytes=8, max_file_bytes=100)
        try:
            self.assertTrue(log.submit({"x": 1}))
            self.assertTrue(entered.wait(5))
            self.assertTrue(log.submit({"x": 2}))
            self.assertFalse(log.submit({"x": 3}))
        finally:
            release.set()
            result = log.close()
        self.assertEqual(output.getvalue(), '{"x":1}\n{"x":2}\n')
        self.assertEqual((result["written"], result["dropped"], result["bytes"]), (2, 1, 16))
        self.assertFalse(log.submit({"x": 4}))

    def test_file_byte_limit_and_invalid_bounds(self):
        """@brief Output cannot grow past its configured bound and limits are validated."""
        for args in ((0, 1), (1, 0), (True, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                EventLog(io.StringIO(), *args)
        output = io.StringIO()
        log = EventLog(output, 128, 8)
        log.submit({"x": 1})
        log.submit({"x": 2})
        result = log.close()
        self.assertEqual(output.getvalue(), '{"x":1}\n')
        self.assertEqual((result["written"], result["dropped"], result["bytes"]), (1, 1, 8))

    def test_write_errors_and_short_writes_are_reported(self):
        """@brief Disk and short-write failures are counted without crashing callers."""
        for result in (OSError("full"), 0):
            with self.subTest(result=result):
                attempted = threading.Event()

                class BrokenFile(io.StringIO):
                    """@brief File that reports a controlled write failure."""

                    def write(self, value, outcome=result, signal=attempted):
                        """@brief Signal the attempted write and return or raise."""
                        signal.set()
                        if isinstance(outcome, Exception):
                            raise outcome
                        return outcome

                log = EventLog(BrokenFile())
                self.assertTrue(log.submit({"x": 1}))
                self.assertTrue(attempted.wait(5))
                with log.condition:
                    self.assertTrue(
                        log.condition.wait_for(lambda log=log: log.error is not None, 5)
                    )
                self.assertFalse(log.submit({"x": 2}))
                summary = log.close()
                self.assertEqual(summary["dropped"], 2)
                self.assertIn("OSError", summary["error"])

    def test_flush_failure_is_reported(self):
        """@brief A final flush failure is included in the returned summary."""

        class FlushFailure(io.StringIO):
            """@brief Report a deterministic flush failure."""

            def flush(self):
                """@brief Fail the caller's final flush."""
                raise OSError("flush failed")

        log = EventLog(FlushFailure())
        self.assertTrue(log.submit({"x": 1}))
        self.assertIn("flush failed", log.close()["error"])


if __name__ == "__main__":
    unittest.main()
