"""@brief Test dumpcap ownership without starting a capture or network traffic."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capture_owner import CaptureOwner


class FakeClock:
    """@brief Advance monotonic time only when an injected sleep occurs."""

    def __init__(self):
        """@brief Start deterministic time at zero."""
        self.now = 0.0

    def clock(self):
        """@brief Return deterministic monotonic seconds."""
        return self.now

    def sleep(self, seconds):
        """@brief Advance deterministic time without blocking."""
        self.now += seconds


class FakeProcess:
    """@brief Model an owned child process and its finite natural autostop."""

    def __init__(self, pid=41, exit_code=None, wait_error=None, terminate_error=None, kill_error=None):
        """@brief Configure readiness, completion and optional wait failure."""
        self.pid = pid
        self.exit_code = exit_code
        self.wait_errors = [] if wait_error is None else [wait_error]
        self.terminate_error = terminate_error
        self.kill_error = kill_error
        self.wait_timeouts = []
        self.terminated = False
        self.killed = False

    def poll(self):
        """@brief Return the child exit code without changing lifecycle state."""
        return self.exit_code

    def wait(self, timeout=None):
        """@brief Complete naturally unless the test requests a stuck child."""
        self.wait_timeouts.append(timeout)
        if self.wait_errors:
            error = self.wait_errors.pop(0)
            raise error
        if self.exit_code is None:
            self.exit_code = 0
        return self.exit_code

    def terminate(self):
        """@brief Mark only this fake owned process terminated."""
        if self.terminate_error is not None:
            raise self.terminate_error
        self.terminated = True
        self.exit_code = 143

    def kill(self):
        """@brief Mark only this fake owned process killed."""
        if self.kill_error is not None:
            raise self.kill_error
        self.killed = True
        self.exit_code = -9


class FailingFlush:
    """@brief Inject a stderr flush failure while preserving real handle cleanup."""

    def __init__(self, wrapped):
        """@brief Retain the real diagnostics file behind a controllable wrapper."""
        self.wrapped = wrapped

    @property
    def closed(self):
        """@brief Expose the wrapped stream's close state."""
        return self.wrapped.closed

    def flush(self):
        """@brief Fail flush so close handling must still close the underlying file."""
        raise OSError("flush failed")

    def close(self):
        """@brief Close the actual file despite its simulated flush failure."""
        self.wrapped.close()


class FailingFlushAndClose(FailingFlush):
    """@brief Inject both diagnostics errors while releasing the real handle."""

    def close(self):
        """@brief Release the real file and then raise a second cleanup error."""
        self.wrapped.close()
        raise OSError("close failed after flush")


class FailingClose:
    """@brief Inject a close error after releasing the real file handle."""

    def __init__(self, wrapped):
        """@brief Retain the real diagnostics file behind a controllable wrapper."""
        self.wrapped = wrapped

    @property
    def closed(self):
        """@brief Expose the wrapped stream's close state."""
        return self.wrapped.closed

    def flush(self):
        """@brief Preserve normal flush behavior before the injected close failure."""
        self.wrapped.flush()

    def close(self):
        """@brief Release the file, then surface the simulated close error."""
        self.wrapped.close()
        raise OSError("close failed")


class CaptureOwnerTests(unittest.TestCase):
    """@brief Verify readiness, STOP ownership and honest final status."""

    def make_owner(self, directory, process=None, ready=True, **kwargs):
        """@brief Create an owner whose fake child touches only its temp artifacts."""
        root = Path(directory)
        clock = FakeClock()
        factory_delay = kwargs.pop("factory_delay", 0)

        def process_factory(command, **options):
            """@brief Materialize fake dumpcap startup evidence, never launch a child."""
            clock.sleep(factory_delay)
            self.assertFalse(options["shell"])
            self.assertEqual(
                options["creationflags"],
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            self.assertEqual(command[1:6], ["-i", "if-test", "-f", "udp", "-s"])
            stderr = options["stderr"]
            if ready:
                stderr.write("Capturing on 'if-test'\n")
                stderr.flush()
                Path(command[-1]).write_bytes(b"test pcapng content")
            return process or FakeProcess()

        owner = CaptureOwner(
            root,
            "if-test",
            "udp",
            60,
            process_factory=process_factory,
            clock=clock.clock,
            sleep=clock.sleep,
            readiness_timeout=kwargs.pop("readiness_timeout", 1),
            poll_interval=0.25,
            close_grace=kwargs.pop("close_grace", 0.5),
            **kwargs,
        )
        return owner, clock

    def test_start_waits_for_process_message_and_capture_file(self):
        """@brief Only report ready while child is alive and both artifacts exist."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            try:
                ready = owner.start()
                self.assertTrue(ready["active"])
                self.assertEqual(ready["pid"], 41)
                self.assertTrue(Path(ready["capture_path"]).is_file())
                self.assertTrue(Path(ready["stderr_path"]).is_file())
                self.assertIn("duration:60", owner.command())
                self.assertEqual(owner.command()[1:6], ["-i", "if-test", "-f", "udp", "-s"])
                owner.process.exit_code = 0
                with self.assertRaisesRegex(RuntimeError, "before owner recorded STOP"):
                    owner.health()
            finally:
                owner._close_stderr()

    def test_owner_rejects_missing_paths_restarts_and_prestart_lifecycle_calls(self):
        """@brief Enforce a single capture lifecycle before creating a child."""
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with self.assertRaisesRegex(ValueError, "must already exist"):
                CaptureOwner(missing, "if-test", "udp", 10)
            owner, _ = self.make_owner(directory)
            with (
                self.assertRaisesRegex(RuntimeError, "has not started"),
            ):
                owner.health()
            with self.assertRaisesRegex(RuntimeError, "has not started"):
                owner.record_stop()
            with self.assertRaisesRegex(RuntimeError, "has not started"):
                owner.close()
            owner._close_stderr()
            self.assertEqual(owner._read_stderr(), "")
            owner.start()
            with self.assertRaisesRegex(RuntimeError, "already started"):
                owner.start()
            first = owner.record_stop()
            owner.clock = lambda: first + 5
            self.assertEqual(owner.record_stop(), first)
            owner.stderr.write(
                "Packets captured: 1\n"
                "Packets received/dropped on interface 'if-test': 1/0\n"
            )
            owner.stderr.flush()
            result = owner.close()
            self.assertTrue(result["lifecycle_complete"])

    def test_start_rechecks_output_collision_and_factory_failure(self):
        """@brief Fail safely if evidence appears after construction or spawn fails."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.capture_path.touch()
            with self.assertRaises(FileExistsError):
                owner.start()
            self.assertIsNone(owner.process)
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.process_factory = lambda *args, **kwargs: (_ for _ in ()).throw(
                OSError("spawn failed")
            )
            with self.assertRaisesRegex(OSError, "spawn failed"):
                owner.start()
            self.assertIsNone(owner.process)
            self.assertTrue(owner.stderr.closed)

    def test_start_preserves_spawn_error_when_stderr_cleanup_also_fails(self):
        """@brief Keep the original spawn failure when close of its diagnostic file fails."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            original_open = Path.open

            def failing_open(path, *args, **kwargs):
                """@brief Wrap only the owner's output handle with a failing flush."""
                stream = original_open(path, *args, **kwargs)
                return FailingFlush(stream) if path == owner.stderr_path else stream

            owner.process_factory = lambda *args, **kwargs: (_ for _ in ()).throw(
                OSError("spawn failed")
            )
            with (
                patch("pathlib.Path.open", autospec=True, side_effect=failing_open),
                self.assertRaisesRegex(OSError, "spawn failed"),
            ):
                owner.start()
            self.assertTrue(owner.stderr.closed)

    def test_start_requires_both_readiness_signals_before_timeout(self):
        """@brief Missing capture indication or output file cleans up owned child."""
        with tempfile.TemporaryDirectory() as directory:
            owner, clock = self.make_owner(directory, ready=False)
            with self.assertRaisesRegex(TimeoutError, "did not become ready"):
                owner.start()
            self.assertEqual(clock.now, 1)
            self.assertTrue(owner.process.terminated)
            self.assertFalse(owner.process.killed)
            self.assertTrue(owner.stderr.closed)

    def test_early_native_exit_fails_startup(self):
        """@brief A child exit is surfaced before accepting its artifacts as active."""
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess(exit_code=5)
            owner, _ = self.make_owner(directory, process=process, ready=False)
            with self.assertRaisesRegex(RuntimeError, "before capture readiness with 5"):
                owner.start()
            self.assertFalse(process.terminated)

    def test_stop_then_natural_autostop_requires_native_statistics(self):
        """@brief Successful completion retains process code, stderr stats and post-STOP time."""
        with tempfile.TemporaryDirectory() as directory:
            owner, clock = self.make_owner(directory)
            owner.start()
            stop_at = owner.record_stop()
            self.assertTrue(owner.health())
            owner.stderr.write(
                "Packets captured: 12\n"
                "Packets received/dropped on interface 'if-test': 12/0 "
                "(capture drops: pcap:0/dumpcap:0/flushed:0/ps_ifdrop:0)\n"
            )
            owner.stderr.flush()
            clock.sleep(2)
            result = owner.close()
            self.assertTrue(result["complete"])
            self.assertFalse(result["forced_stop"])
            self.assertEqual(result["exit_code"], 0)
            self.assertTrue(result["statistics_available"])
            self.assertTrue(result["lifecycle_complete"])
            self.assertTrue(result["complete"])
            self.assertIsNone(result["stop_packet_verified"])
            self.assertIn("unverified", result["completion_scope"])
            self.assertEqual(result["statistics"]["captured"], 12)
            self.assertEqual(
                result["statistics"]["interfaces"],
                [{"interface": "if-test", "received": 12, "dropped": 0}],
            )
            self.assertTrue(any("Packets captured: 12" in line for line in result["statistics"]["lines"]))
            self.assertGreaterEqual(result["post_stop_capture_seconds"], 2)
            self.assertGreaterEqual(owner.process.wait_timeouts[0], 58)
            self.assertEqual(result["stop_at"], stop_at)
            self.assertEqual(owner.close(), result)

    def test_safety_wait_is_measured_from_capture_readiness(self):
        """@brief Slow initialization cannot make close terminate before native autostop."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, factory_delay=7, close_grace=0.25)
            owner.start()
            owner.record_stop()
            owner.close()
            self.assertEqual(owner.ready_at, 7)
            self.assertGreaterEqual(owner.process.wait_timeouts[0], 60.25)

    def test_missing_stop_forces_owned_child_and_is_incomplete(self):
        """@brief Never classify a forced close without owner-recorded STOP as success."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.start()
            result = owner.close()
            self.assertTrue(owner.process.terminated)
            self.assertTrue(result["forced_stop"])
            self.assertFalse(result["stop_recorded"])
            self.assertFalse(result["complete"])
            self.assertFalse(result["statistics_available"])

    def test_natural_exit_without_stop_is_incomplete_not_forced(self):
        """@brief Preserve finalized stats when safety autostop ended capture before STOP."""
        process = FakeProcess()
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            owner.stderr.write(
                "Packets captured: 7\n"
                "Packets received/dropped on interface 'if-test': 7/0\n"
            )
            owner.stderr.flush()
            process.exit_code = 0
            result = owner.close()
            self.assertFalse(result["stop_recorded"])
            self.assertFalse(result["forced_stop"])
            self.assertEqual(result["exit_code"], 0)
            self.assertTrue(result["statistics_available"])
            self.assertEqual(result["statistics"]["captured"], 7)
            self.assertFalse(result["lifecycle_complete"])

    def test_wait_timeout_terminates_then_kills_only_owned_child(self):
        """@brief Escalation is bounded and never makes forced output complete."""
        process = FakeProcess(
            wait_error=subprocess.TimeoutExpired("dumpcap", 2),
        )
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            owner.record_stop()
            process.wait_errors.append(subprocess.TimeoutExpired("dumpcap", 1))
            result = owner.close()
            self.assertTrue(process.terminated)
            self.assertTrue(process.killed)
            self.assertTrue(result["forced_stop"])
            self.assertFalse(result["complete"])
            self.assertEqual(result["exit_code"], -9)

    def test_terminate_error_is_retained_and_cleanup_stays_incomplete(self):
        """@brief Continue bounded cleanup after terminate fails and retain that failure."""
        process = FakeProcess(terminate_error=OSError("terminate denied"))
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            process.wait_errors.append(subprocess.TimeoutExpired("dumpcap", 1))
            process.wait_errors.append(subprocess.TimeoutExpired("dumpcap", 1))
            result = owner.close()
            self.assertTrue(process.killed)
            self.assertTrue(any("terminate denied" in error for error in result["cleanup_errors"]))
            self.assertFalse(result["lifecycle_complete"])
            self.assertTrue(result["statistics_unknown"])

    def test_kill_and_final_wait_errors_are_retained_without_raising(self):
        """@brief Report failed escalation and return incomplete instead of leaking errors."""
        process = FakeProcess(
            terminate_error=OSError("terminate denied"),
            kill_error=OSError("kill denied"),
        )
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            process.wait_errors.extend(
                (
                    subprocess.TimeoutExpired("dumpcap", 1),
                    subprocess.TimeoutExpired("dumpcap", 1),
                )
            )
            result = owner.close()
            self.assertIsNone(result["exit_code"])
            self.assertTrue(any("kill denied" in error for error in result["cleanup_errors"]))
            self.assertTrue(
                any("did not exit after kill" in error for error in result["cleanup_errors"])
            )
            self.assertFalse(result["lifecycle_complete"])

    def test_final_wait_oserror_is_captured_before_escalation(self):
        """@brief Wait API failure is retained and child escalation remains owned."""
        process = FakeProcess(wait_error=OSError("wait failed"))
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            owner.record_stop()
            result = owner.close()
            self.assertTrue(process.terminated)
            self.assertTrue(any("wait failed" in error for error in result["cleanup_errors"]))
            self.assertFalse(result["lifecycle_complete"])
            self.assertTrue(result["statistics_unknown"])

    def test_owned_process_wait_oserror_is_reported_during_forced_cleanup(self):
        """@brief Catch wait API errors during termination and preserve incomplete status."""
        process = FakeProcess(terminate_error=OSError("terminate denied"))
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            process.wait_errors.append(OSError("cleanup wait failed"))
            result = owner.close()
            self.assertIsNone(result["exit_code"])
            self.assertTrue(
                any("cleanup wait failed" in error for error in result["cleanup_errors"])
            )
            self.assertFalse(result["lifecycle_complete"])
            self.assertTrue(result["statistics_unknown"])

    def test_second_wait_oserror_after_kill_is_retained_without_escaping(self):
        """@brief Catch the final wait error after kill and still close diagnostics."""
        process = FakeProcess()
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            process.wait_errors.extend(
                (
                    subprocess.TimeoutExpired("dumpcap", 1),
                    OSError("wait after kill failed"),
                )
            )
            result = owner.close()
            self.assertTrue(process.killed)
            self.assertEqual(result["exit_code"], -9)
            self.assertTrue(
                any("wait after kill failed" in error for error in result["cleanup_errors"])
            )
            self.assertFalse(result["lifecycle_complete"])
            self.assertTrue(owner.stderr.closed)

    def test_poll_oserror_during_forced_cleanup_is_retained(self):
        """@brief A close-time poll error does not prevent owned termination or file close."""
        process = FakeProcess()
        original_poll = process.poll
        calls = 0
        armed = False

        def flaky_poll():
            """@brief Raise once during cleanup's pre-terminate liveness check."""
            nonlocal calls, armed
            calls += 1
            if armed and calls == 1:
                raise OSError("poll failed")
            return original_poll()

        process.poll = flaky_poll
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            calls = 0
            armed = True
            result = owner.close()
            self.assertTrue(process.terminated)
            self.assertTrue(any("poll failed" in error for error in result["cleanup_errors"]))
            self.assertTrue(owner.stderr.closed)
            self.assertFalse(result["lifecycle_complete"])

    def test_force_cleanup_poll_oserror_is_retained(self):
        """@brief Continue termination if the child's initial cleanup poll fails."""
        process = FakeProcess()
        original_poll = process.poll
        calls = 0

        def flaky_poll():
            """@brief Raise on the forced cleanup helper's liveness check."""
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("cleanup poll failed")
            return original_poll()

        process.poll = flaky_poll
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            calls = 0
            result = owner.close()
            self.assertTrue(process.terminated)
            self.assertTrue(
                any("cleanup poll failed" in error for error in result["cleanup_errors"])
            )
            self.assertTrue(owner.stderr.closed)
            self.assertFalse(result["lifecycle_complete"])

    def test_stderr_read_oserror_is_recorded_and_does_not_leak_handle(self):
        """@brief Final diagnostic read errors become incomplete results with closed stderr."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.start()
            owner.record_stop()
            with patch.object(Path, "read_text", side_effect=OSError("stderr unreadable")):
                result = owner.close()
            self.assertTrue(any("stderr unreadable" in error for error in result["cleanup_errors"]))
            self.assertTrue(owner.stderr.closed)
            self.assertFalse(result["lifecycle_complete"])

    def test_capture_stat_oserror_is_recorded_and_does_not_leak_handle(self):
        """@brief Filesystem inspection errors become incomplete results, not exceptions."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.start()
            owner.record_stop()
            original_is_file = Path.is_file

            def failing_is_file(path):
                """@brief Fail only the capture path stat during finalization."""
                if path == owner.capture_path:
                    raise OSError("capture stat failed")
                return original_is_file(path)

            with patch.object(Path, "is_file", autospec=True, side_effect=failing_is_file):
                result = owner.close()
            self.assertFalse(result["capture_exists"])
            self.assertEqual(result["capture_bytes"], 0)
            self.assertTrue(any("capture stat failed" in error for error in result["cleanup_errors"]))
            self.assertTrue(owner.stderr.closed)
            self.assertFalse(result["lifecycle_complete"])

    def test_stderr_flush_failure_closes_handle_and_denies_completion(self):
        """@brief Retain flush failure, close the file and refuse lifecycle success."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.start()
            owner.record_stop()
            owner.stderr.write(
                "Packets captured: 1\n"
                "Packets received/dropped on interface 'if-test': 1/0\n"
            )
            owner.stderr.flush()
            broken = FailingFlush(owner.stderr)
            owner.stderr = broken
            result = owner.close()
            self.assertTrue(broken.closed)
            self.assertTrue(any("flush failed" in error for error in result["cleanup_errors"]))
            self.assertFalse(result["lifecycle_complete"])
            self.assertFalse(result["complete"])

    def test_stderr_close_failure_is_retained_after_handle_release(self):
        """@brief A close error is retained and blocks success without leaking the handle."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.start()
            owner.record_stop()
            owner.stderr.write(
                "Packets captured: 1\n"
                "Packets received/dropped on interface 'if-test': 1/0\n"
            )
            owner.stderr.flush()
            broken = FailingClose(owner.stderr)
            owner.stderr = broken
            result = owner.close()
            self.assertTrue(broken.closed)
            self.assertTrue(any("close failed" in error for error in result["cleanup_errors"]))
            self.assertFalse(result["lifecycle_complete"])

    def test_stderr_close_error_does_not_replace_prior_flush_error(self):
        """@brief Preserve the first cleanup error while still attempting close."""
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory)
            owner.start()
            owner.record_stop()
            owner.stderr.write(
                "Packets captured: 1\n"
                "Packets received/dropped on interface 'if-test': 1/0\n"
            )
            owner.stderr.flush()
            broken = FailingFlushAndClose(owner.stderr)
            owner.stderr = broken
            result = owner.close()
            self.assertTrue(broken.closed)
            self.assertEqual(result["cleanup_errors"], ["stderr:flush failed"])
            self.assertFalse(result["lifecycle_complete"])

    def test_wait_error_after_natural_exit_keeps_final_stats_but_denies_completion(self):
        """@brief Preserve known stats when the child exited before a wait API error."""
        process = FakeProcess()
        with tempfile.TemporaryDirectory() as directory:
            owner, _ = self.make_owner(directory, process=process)
            owner.start()
            owner.record_stop()
            owner.stderr.write(
                "Packets captured: 3\n"
                "Packets received/dropped on interface 'if-test': 3/0\n"
            )
            owner.stderr.flush()
            process.exit_code = 0
            process.wait_errors.append(OSError("wait handle failed"))
            result = owner.close()
            self.assertEqual(result["exit_code"], 0)
            self.assertFalse(result["forced_stop"])
            self.assertTrue(result["cleanup_errors"])
            self.assertFalse(result["lifecycle_complete"])
            self.assertFalse(result["complete"])
            self.assertTrue(result["statistics_available"])
            self.assertFalse(result["statistics_unknown"])

    def test_parser_counts_multiple_interfaces(self):
        """@brief Expose numeric received/drop values without discarding raw stats."""
        stats = CaptureOwner._capture_stats(
            "Packets captured: 14\n"
            "Packets received/dropped on interface 'Ethernet': 8/1\n"
            'Packets received/dropped on interface "Wi-Fi": 6/2\n'
        )
        self.assertTrue(stats["available"])
        self.assertEqual(stats["captured"], 14)
        self.assertEqual(
            stats["interfaces"],
            [
                {"interface": "Ethernet", "received": 8, "dropped": 1},
                {"interface": "Wi-Fi", "received": 6, "dropped": 2},
            ],
        )
        self.assertEqual(len(stats["lines"]), 3)

    def test_constructor_rejects_missing_filter_bad_time_and_reused_paths(self):
        """@brief Reject unsafe configuration before a process can be created."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for interface, capture_filter, duration in (
                ("", "udp", 1),
                ("if-test", "", 1),
                ("if-test", "udp", float("inf")),
                ("if-test", "udp", 0),
            ):
                with (
                    self.subTest(
                        interface=interface,
                        capture_filter=capture_filter,
                        duration=duration,
                    ),
                    self.assertRaises(ValueError),
                ):
                    CaptureOwner(root, interface, capture_filter, duration)
            (root / "link.pcapng").touch()
            with self.assertRaises(FileExistsError):
                CaptureOwner(root, "if-test", "udp", 60)


if __name__ == "__main__":
    unittest.main()
