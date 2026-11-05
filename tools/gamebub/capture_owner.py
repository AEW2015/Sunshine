"""@brief Own one bounded dumpcap process and its capture evidence."""

import math
import os
import re
import subprocess
import time
from pathlib import Path


class CaptureOwner:
    """@brief Start, monitor and naturally finalize one explicit dumpcap capture.

    The caller must invoke start() before media begins, health() from its
    session loop, and record_stop() only after observing the protocol STOP.
    dumpcap's finite autostop is a safety bound; close() waits for it rather
    than ending a successful capture early.
    """

    def __init__(
        self,
        output_dir,
        interface,
        capture_filter,
        safety_seconds,
        *,
        executable=r"C:\Program Files\Wireshark\dumpcap.exe",
        readiness_timeout=10.0,
        close_grace=2.0,
        poll_interval=0.05,
        process_factory=subprocess.Popen,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        """@brief Prepare paths and timing without starting a capture.

        @param output_dir Existing fresh evidence directory.
        @param interface Explicit dumpcap interface name or index.
        @param capture_filter Explicit BPF capture filter.
        @param safety_seconds Finite dumpcap autostop duration, in seconds.
        @param executable Path to the installed dumpcap executable.
        @param readiness_timeout Maximum wait for dumpcap readiness.
        @param close_grace Extra bounded wait after the safety deadline.
        @param poll_interval Readiness polling interval.
        @param process_factory Injectable subprocess factory.
        @param clock Injectable monotonic clock.
        @param sleep Injectable bounded wait function.
        """
        if not interface or not capture_filter:
            raise ValueError("An explicit interface and BPF capture filter are required")
        if any(
            not math.isfinite(value) or value <= 0
            for value in (safety_seconds, readiness_timeout, close_grace, poll_interval)
        ):
            raise ValueError("Capture timing values must be finite and positive")
        self.output_dir = Path(output_dir)
        if not self.output_dir.is_dir():
            raise ValueError("Capture output directory must already exist")
        self.capture_path = self.output_dir / "link.pcapng"
        self.stderr_path = self.output_dir / "dumpcap-stderr.txt"
        if self.capture_path.exists() or self.stderr_path.exists():
            raise FileExistsError("Capture evidence paths already exist")

        self.interface = str(interface)
        self.capture_filter = str(capture_filter)
        self.safety_seconds = float(safety_seconds)
        self.executable = str(executable)
        self.readiness_timeout = float(readiness_timeout)
        self.close_grace = float(close_grace)
        self.poll_interval = float(poll_interval)
        self.process_factory = process_factory
        self.clock = clock
        self.sleep = sleep
        self.process = None
        self.stderr = None
        self.started_at = None
        self.ready_at = None
        self.stop_at = None
        self.result = None

    def command(self):
        """@brief Return the exact finite dumpcap argument vector."""
        return [
            self.executable,
            "-i",
            self.interface,
            "-f",
            self.capture_filter,
            "-s",
            "0",
            "-a",
            f"duration:{self.safety_seconds:g}",
            "-w",
            str(self.capture_path),
        ]

    def start(self):
        """@brief Launch dumpcap and wait until both readiness signals are present.

        @return Capture path, stderr path and process ID after readiness.
        @raises RuntimeError If startup fails, exits early or times out.
        """
        if self.process is not None:
            raise RuntimeError("Capture owner has already started")
        if self.capture_path.exists() or self.stderr_path.exists():
            raise FileExistsError("Capture evidence paths already exist")
        self.stderr = self.stderr_path.open("x", encoding="utf-8", buffering=1)
        try:
            self.started_at = self.clock()
            self.process = self.process_factory(
                self.command(),
                cwd=str(self.output_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=self.stderr,
                shell=False,
                creationflags=(
                    getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                ),
            )
            deadline = self.started_at + self.readiness_timeout
            while True:
                code = self.process.poll()
                if code is not None:
                    raise RuntimeError(f"dumpcap exited before capture readiness with {code}")
                if "Capturing on" in self._read_stderr() and self.capture_path.is_file():
                    self.ready_at = self.clock()
                    return {
                        "pid": self.process.pid,
                        "capture_path": str(self.capture_path),
                        "stderr_path": str(self.stderr_path),
                        "ready_at": self.ready_at,
                        "active": True,
                    }
                remaining = deadline - self.clock()
                if remaining <= 0:
                    raise TimeoutError("dumpcap did not become ready before the deadline")
                self.sleep(min(self.poll_interval, remaining))
        except BaseException:
            self._force_owned_process()
            try:
                self._close_stderr()
            except (OSError, ValueError):
                pass
            raise

    def health(self):
        """@brief Raise if dumpcap exits before STOP or report whether it remains active.

        @return True while capture is active, or False after a recorded STOP.
        """
        if self.process is None:
            raise RuntimeError("Capture owner has not started")
        code = self.process.poll()
        if code is not None and self.stop_at is None:
            raise RuntimeError(f"dumpcap exited before owner recorded STOP with {code}")
        return code is None

    def record_stop(self):
        """@brief Record the observed session STOP before capture finalization.

        @return Monotonic STOP time.
        """
        if self.process is None:
            raise RuntimeError("Capture owner has not started")
        if self.stop_at is not None:
            return self.stop_at
        self.health()
        self.stop_at = self.clock()
        return self.stop_at

    def close(self):
        """@brief Wait for natural safety autostop and report completeness explicitly.

        A missing STOP or a process that does not exit naturally is force-stopped
        only as failed cleanup. Forced termination can never produce a complete
        result, even if the resulting file happens to be readable.

        @return Capture status, native exit code, stats lines and artifact paths.
        """
        if self.result is not None:
            return self.result.copy()
        if self.process is None:
            raise RuntimeError("Capture owner has not started")

        force_cleanup_needed = False
        cleanup_errors = []
        exit_code = None
        if self.stop_at is None:
            force_cleanup_needed = True
        else:
            deadline = self.ready_at + self.safety_seconds
            timeout = max(0.0, deadline - self.clock()) + self.close_grace
            try:
                exit_code = self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                force_cleanup_needed = True
            except OSError as error:
                force_cleanup_needed = True
                cleanup_errors.append(f"wait:{error}")
        if force_cleanup_needed:
            exit_code = self._poll_exit_code(cleanup_errors, "poll-before-cleanup")
        forced = force_cleanup_needed and exit_code is None
        if forced:
            cleanup_errors.extend(self._force_owned_process())
            exit_code = self._poll_exit_code(cleanup_errors, "poll-after-cleanup")

        try:
            stderr_text = self._read_stderr()
        except OSError as error:
            stderr_text = ""
            cleanup_errors.append(f"stderr-read:{error}")
        stats = self._capture_stats(stderr_text)
        stats["available"] = stats["available"] and not forced
        try:
            file_exists = self.capture_path.is_file()
            file_bytes = self.capture_path.stat().st_size if file_exists else 0
        except OSError as error:
            file_exists, file_bytes = False, 0
            cleanup_errors.append(f"capture-stat:{error}")
        finished_at = self.clock()
        try:
            self._close_stderr()
        except (OSError, ValueError) as error:
            cleanup_errors.append(f"stderr:{error}")
        lifecycle_complete = bool(
            self.stop_at is not None
            and exit_code == 0
            and not forced
            and stats["available"]
            and file_exists
            and file_bytes > 0
            and not cleanup_errors
        )
        self.result = {
            "active": False,
            "stop_recorded": self.stop_at is not None,
            "exit_code": exit_code,
            "forced_stop": forced,
            "cleanup_errors": cleanup_errors,
            "lifecycle_complete": lifecycle_complete,
            "complete": lifecycle_complete,
            "completion_scope": "capture lifecycle only; STOP packet in savefile is unverified",
            "stop_packet_verified": None,
            "statistics_available": stats["available"],
            "statistics_unknown": not stats["available"],
            "statistics": stats,
            "capture_path": str(self.capture_path),
            "capture_exists": file_exists,
            "capture_bytes": file_bytes,
            "stderr_path": str(self.stderr_path),
            "stderr_text": stderr_text,
            "started_at": self.started_at,
            "ready_at": self.ready_at,
            "stop_at": self.stop_at,
            "finished_at": finished_at,
            "post_stop_capture_seconds": (
                None if self.stop_at is None else max(0.0, finished_at - self.stop_at)
            ),
        }
        return self.result.copy()

    def _read_stderr(self):
        """@brief Read captured diagnostics without taking ownership of the writer handle."""
        try:
            return self.stderr_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    @staticmethod
    def _capture_stats(stderr_text):
        """@brief Parse native packet totals while retaining raw summary lines."""
        lines = [
            line.strip()
            for line in stderr_text.splitlines()
            if "Packets captured:" in line
            or "Packets received/dropped on interface" in line
            or "capture drops:" in line
        ]
        captured_match = re.search(r"Packets captured:\s*(\d+)", stderr_text)
        interfaces = []
        for match in re.finditer(
            r"Packets received/dropped on interface (.+?):\s*(\d+)/(\d+)", stderr_text
        ):
            name = match.group(1).strip().strip("'\"")
            interfaces.append(
                {"interface": name, "received": int(match.group(2)), "dropped": int(match.group(3))}
            )
        captured = None if captured_match is None else int(captured_match.group(1))
        return {
            "available": captured is not None and bool(interfaces),
            "captured": captured,
            "interfaces": interfaces,
            "lines": lines,
        }

    def _force_owned_process(self):
        """@brief Stop only this owned child, escalating with bounded waits.

        @return Errors encountered while requesting or waiting for termination.
        """
        errors = []
        if self.process is None:
            return errors
        try:
            if self.process.poll() is not None:
                return errors
        except OSError as error:
            errors.append(f"poll-before-terminate:{error}")
        try:
            self.process.terminate()
        except OSError as error:
            errors.append(f"terminate:{error}")
        try:
            self.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                self.process.kill()
            except OSError as error:
                errors.append(f"kill:{error}")
            try:
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                errors.append("wait:owned dumpcap did not exit after kill")
            except OSError as error:
                errors.append(f"wait-after-kill:{error}")
        except OSError as error:
            errors.append(f"wait:{error}")
        return errors

    def _poll_exit_code(self, errors, label):
        """@brief Read the owned child's native exit status without losing cleanup."""
        try:
            return self.process.poll()
        except OSError as error:
            errors.append(f"{label}:{error}")
            return None

    def _close_stderr(self):
        """@brief Flush and close the owner-held diagnostics handle once."""
        if self.stderr is not None and not self.stderr.closed:
            failure = None
            try:
                self.stderr.flush()
            except (OSError, ValueError) as error:
                failure = error
            try:
                self.stderr.close()
            except (OSError, ValueError) as error:
                if failure is None:
                    failure = error
            if failure is not None:
                raise failure
