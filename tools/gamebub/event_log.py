"""@brief Bounded asynchronous JSONL event logging for sender experiments."""

import json
from collections import deque
from threading import Condition, Thread


class EventLog:
    """@brief Write queued events away from capture, sender and feedback threads.

    Events are dropped when queue or file bounds are reached, or on an I/O
    error. The caller owns the file and must close this logger before the file.
    The writer must return in bounded time for close() to complete.
    """

    def __init__(self, output, max_queued_bytes=262144, max_file_bytes=67108864):
        """@brief Start a writer with bounded in-memory and output sizes.

        @param output Writable text stream owned by the caller.
        @param max_queued_bytes Maximum number of queued UTF-8 bytes.
        @param max_file_bytes Maximum output bytes across this run.
        """
        if any(type(v) is not int or v <= 0 for v in (max_queued_bytes, max_file_bytes)):
            raise ValueError("Log limits must be positive integers")
        self.output = output
        self.max_queued_bytes, self.max_file_bytes = max_queued_bytes, max_file_bytes
        self.condition = Condition()
        self.queue = deque()
        self.queued_bytes = self.written_bytes = self.written = self.dropped = 0
        self.error = None
        self.closed = False
        self.thread = Thread(target=self._run, name="gamebub-log")
        self.thread.start()

    def submit(self, event):
        """@brief Enqueue one JSON object without waiting for disk I/O.

        @param event JSON-serializable dictionary.
        @return True if queued, False if closed, failed, or queue capacity is exhausted.
        """
        line = json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n"
        size = len(line)
        with self.condition:
            if (
                self.closed
                or self.error is not None
                or self.queued_bytes + size > self.max_queued_bytes
            ):
                self.dropped += 1
                return False
            self.queue.append((line, size))
            self.queued_bytes += size
            self.condition.notify()
            return True

    def _run(self):
        """@brief Drain queued records and stop at the configured output bound."""
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.queue or self.closed)
                if not self.queue:
                    return
                line, size = self.queue.popleft()
                self.queued_bytes -= size
                if self.error is not None or self.written_bytes + size > self.max_file_bytes:
                    self.dropped += 1
                    continue
            try:
                if self.output.write(line) != len(line):
                    raise OSError("Incomplete log write")
            except (OSError, ValueError) as error:
                with self.condition:
                    self.error = f"{type(error).__name__}: {error}"
                    self.dropped += 1
                    self.condition.notify_all()
                continue
            with self.condition:
                self.written_bytes += size
                self.written += 1

    def close(self):
        """@brief Drain the queue and return counts and any write or flush failure."""
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.thread.join()
        try:
            self.output.flush()
        except (OSError, ValueError) as error:
            with self.condition:
                self.error = f"{type(error).__name__}: {error}"
        with self.condition:
            return {
                "written": self.written,
                "bytes": self.written_bytes,
                "dropped": self.dropped,
                "error": self.error,
            }
