"""@brief Deterministic optional pacing wait tests, without network or input injection."""

import ctypes
import math
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pacing_wait import PreciseWait, _WindowsTimer


class FakeClock:
    """@brief Advance only when the fake backend or sleeper explicitly waits."""

    def __init__(self):
        """@brief Start at a stable monotonic origin."""
        self.now = 10.0
        self.tick = 0

    def __call__(self):
        """@brief Read the synthetic monotonic seconds clock."""
        self.now += self.tick
        return self.now

    def sleep(self, seconds):
        """@brief Perform an exact fake blocking sleep without real wall time."""
        self.now += seconds


class FakeTimer:
    """@brief Controllable native backend with exact, early, late or failed waits."""

    def __init__(self, clock, waits=(), close_failures=0):
        """@brief Retain scripted wait outcomes and a bounded close-failure count."""
        self.clock = clock
        self.outcomes = list(waits)
        self.waits = []
        self.close_calls = 0
        self.close_failures = close_failures

    def wait(self, seconds):
        """@brief Advance by a multiplier, or raise the scripted native error."""
        self.waits.append(seconds)
        outcome = self.outcomes.pop(0) if self.outcomes else 1.0
        if isinstance(outcome, BaseException):
            raise outcome
        self.clock.sleep(seconds * outcome)

    def close(self):
        """@brief Fail only the explicitly scripted number of close attempts."""
        self.close_calls += 1
        if self.close_calls <= self.close_failures:
            raise OSError("close failed")


class PreciseWaitTests(unittest.TestCase):
    """@brief Verify deadlines, cancellation, fallback accounting and resource ownership."""

    def setUp(self):
        """@brief Create a deterministic timer and guarded fallback for each test."""
        self.clock = FakeClock()
        self.timer = FakeTimer(self.clock)
        self.fallback = Mock(side_effect=self.clock.sleep)

    def waiter(self, timer=None, **kwargs):
        """@brief Construct the Windows path with a fake timer and no OS calls."""
        return PreciseWait(
            clock=self.clock,
            fallback=self.fallback,
            platform="win32",
            timer_factory=lambda: self.timer if timer is None else timer,
            **kwargs,
        )

    def test_exact_native_wait_and_context_cleanup(self):
        """@brief A native wait reaches its deadline and closes once after context exit."""
        with self.waiter() as wait:
            wait(0.002128)
            self.assertAlmostEqual(self.clock.now, 10.002128)
            snapshot = wait.snapshot()
            self.assertEqual(snapshot["native_calls"], 1)
            self.assertEqual(snapshot["backend"], "windows-high-resolution")
            self.assertIsNone(snapshot["fallback_reason"])
        self.assertTrue(wait.snapshot()["closed"])
        self.assertEqual(wait.snapshot()["backend"], "windows-high-resolution")
        wait.close()
        self.assertEqual(self.timer.close_calls, 1)
        self.fallback.assert_not_called()

    def test_zero_duration_does_not_wait(self):
        """@brief Zero is counted without calling either wait backend."""
        wait = self.waiter()
        wait(0)
        self.assertEqual(wait.snapshot()["calls"], 1)
        self.assertEqual(self.timer.waits, [])
        self.fallback.assert_not_called()

    def test_early_wake_rearms_remaining_time(self):
        """@brief A native early wake cannot allow a premature return."""
        wait = self.waiter(FakeTimer(self.clock, waits=[0.5]))
        wait(0.004)
        self.assertAlmostEqual(self.clock.now, 10.004)
        self.assertEqual(wait.snapshot()["native_calls"], 2)
        self.assertEqual(wait.snapshot()["early_wakes"], 1)

    def test_oversleep_does_not_add_a_second_wait(self):
        """@brief An elapsed deadline is returned after one late wake."""
        wait = self.waiter(FakeTimer(self.clock, waits=[2]))
        wait(0.002)
        self.assertEqual(wait.snapshot()["native_calls"], 1)
        self.assertAlmostEqual(wait.snapshot()["max_overshoot_ms"], 2)

    def test_long_wait_is_bounded_into_chunks(self):
        """@brief Native waits remain at most 50 ms, without inventing spin time."""
        wait = self.waiter()
        wait(0.12)
        self.assertEqual(len(self.timer.waits), 3)
        self.assertTrue(all(duration <= 0.05 for duration in self.timer.waits))
        self.assertAlmostEqual(sum(self.timer.waits), 0.12)

    def test_non_windows_uses_visible_fallback(self):
        """@brief Other platforms never instantiate or access a Windows backend."""
        factory = Mock(side_effect=AssertionError("unexpected native constructor"))
        wait = PreciseWait(
            clock=self.clock, fallback=self.fallback, timer_factory=factory, platform="linux"
        )
        wait(0.003)
        self.assertEqual(wait.snapshot()["fallback_reason"], "non-Windows platform")
        self.assertEqual(wait.snapshot()["fallback_calls"], 1)
        factory.assert_not_called()

    def test_default_platform_selection_is_explicit(self):
        """@brief The platform default follows sys.platform, not import-time native state."""
        with patch("pacing_wait.sys.platform", "linux"):
            wait = PreciseWait(clock=self.clock, fallback=self.fallback)
        wait(0.002)
        self.assertEqual(wait.snapshot()["backend"], "sleep")

    def test_missing_or_unsupported_native_api_falls_back(self):
        """@brief Initialization errors are retained without blocking the sender."""
        for error in (OSError("unsupported timer"), AttributeError("missing API")):
            with self.subTest(error=error):
                wait = PreciseWait(
                    clock=self.clock,
                    fallback=self.fallback,
                    platform="win32",
                    timer_factory=Mock(side_effect=error),
                )
                wait(0.002)
                self.assertIn("native initialization", wait.snapshot()["fallback_reason"])
                self.assertEqual(wait.snapshot()["fallback_calls"], 1)

    def test_native_runtime_error_retires_handle_and_falls_back(self):
        """@brief Runtime failure causes one visible fallback for the remaining deadline."""
        timer = FakeTimer(self.clock, waits=[OSError("native wait failed")])
        wait = self.waiter(timer)
        wait(0.004)
        self.assertEqual(timer.close_calls, 1)
        self.assertEqual(wait.snapshot()["runtime_failures"], 1)
        self.assertIn("native wait", wait.snapshot()["fallback_reason"])
        self.assertEqual(wait.snapshot()["fallback_calls"], 1)
        wait(0.002)
        self.assertEqual(wait.snapshot()["native_calls"], 1)
        wait.close()
        self.assertEqual(timer.close_calls, 1)

    def test_runtime_close_failure_is_retained_for_cleanup_retry(self):
        """@brief Failed retirement retains the handle for an explicit final close attempt."""
        timer = FakeTimer(self.clock, waits=[OSError("failed")], close_failures=1)
        wait = self.waiter(timer)
        wait(0.002)
        self.assertEqual(wait.snapshot()["pending_close"], 1)
        self.assertEqual(wait.snapshot()["close_failures"], 1)
        wait.close()
        self.assertEqual(timer.close_calls, 2)
        self.assertEqual(wait.snapshot()["pending_close"], 0)

    def test_normal_close_failure_propagates_and_is_retryable(self):
        """@brief Cleanup does not falsely report success after CloseHandle fails."""
        timer = FakeTimer(self.clock, close_failures=1)
        wait = self.waiter(timer)
        with self.assertRaisesRegex(OSError, "close failed"):
            wait.close()
        self.assertTrue(wait.closed)
        self.assertEqual(wait.snapshot()["pending_close"], 1)
        wait.close()
        self.assertEqual(timer.close_calls, 2)

    def test_cancel_before_wait(self):
        """@brief A preexisting cancellation never arms a timer or sends anything."""
        wait = self.waiter(cancelled=lambda: True)
        with self.assertRaisesRegex(InterruptedError, "cancelled"):
            wait(0.02)
        self.assertEqual(self.timer.waits, [])
        self.assertEqual(wait.snapshot()["cancelled"], 1)

    def test_cancel_during_wait_is_checked_after_bounded_chunk(self):
        """@brief Cooperative cancellation is observed between native wait chunks."""
        wait = self.waiter(cancelled=lambda: self.clock.now >= 10.05)
        with self.assertRaises(InterruptedError):
            wait(0.2)
        self.assertEqual(self.timer.waits, [0.05])

    def test_fallback_guard_exception_propagates(self):
        """@brief Feedback/liveness exceptions from the caller's fallback are not swallowed."""
        wait = PreciseWait(
            clock=self.clock,
            platform="linux",
            fallback=Mock(side_effect=TimeoutError("feedback expired")),
        )
        with self.assertRaisesRegex(TimeoutError, "feedback expired"):
            wait(0.002)

    def test_invalid_duration_rejected_before_backend_calls(self):
        """@brief Invalid durations never reach native conversion or a sleep call."""
        wait = self.waiter()
        for duration in (-1, math.inf, -math.inf, math.nan, True, None, "0.1", 10**1000):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                wait(duration)
        self.assertEqual(wait.snapshot()["calls"], 0)

    def test_overflowed_deadline_rejected(self):
        """@brief Finite duration plus a huge origin cannot create an infinite deadline."""
        wait = PreciseWait(clock=lambda: 1e308, platform="linux")
        with self.assertRaisesRegex(ValueError, "deadline"):
            wait(1e308)

    def test_closed_wait_and_context_reentry_rejected(self):
        """@brief Closed resources cannot silently fall through to ordinary sleep."""
        wait = self.waiter()
        wait.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            wait(0)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            wait.__enter__()

    def test_snapshot_cannot_mutate_internal_counters(self):
        """@brief Returned diagnostics own their keys and values."""
        wait = self.waiter()
        wait.snapshot()["calls"] = 99
        self.assertEqual(wait.snapshot()["calls"], 0)

    def test_native_hybrid_tail_reaches_original_deadline_and_accounts_cpu(self):
        """@brief The explicit tail advances to the original deadline without early return."""
        self.clock.tick = 0.000005
        cpu = Mock(side_effect=(0, 0.001, 0.002, 0.003))
        started = self.clock.now + self.clock.tick
        wait = self.waiter(spin_tail_seconds=0.0006, cpu_clock=cpu)
        wait(0.002128)
        self.assertGreaterEqual(self.clock.now, started + 0.002128)
        self.assertAlmostEqual(self.timer.waits[0], 0.002128 - 0.0006 - self.clock.tick)
        snapshot = wait.snapshot()
        self.assertEqual(snapshot["spin_calls"], 1)
        self.assertGreater(snapshot["spin_wall_seconds"], 0)
        self.assertLess(snapshot["spin_wall_seconds"], 0.00065)
        self.assertAlmostEqual(snapshot["thread_cpu_seconds"], 0.003)
        self.assertAlmostEqual(snapshot["spin_thread_cpu_seconds"], 0.001)
        self.assertEqual(snapshot["early_wakes"], 0)
        self.assertEqual(snapshot["spin_tail_requested_seconds"], 0.0006)
        self.assertEqual(snapshot["spin_tail_effective_seconds"], 0.0006)
        self.assertIsNone(snapshot["spin_disabled_reason"])
        wait.close()
        self.assertEqual(self.timer.close_calls, 1)

    def test_short_native_tail_needs_no_timer_arm(self):
        """@brief Short remaining intervals spin only their actual requested duration."""
        self.clock.tick = 0.000005
        started = self.clock.now + self.clock.tick
        wait = self.waiter(spin_tail_seconds=0.0006)
        wait(0.0002)
        self.assertGreaterEqual(self.clock.now, started + 0.0002)
        self.assertEqual(self.timer.waits, [])
        self.assertEqual(wait.snapshot()["spin_calls"], 1)
        self.assertEqual(wait.snapshot()["native_calls"], 0)

    def test_hybrid_oversleep_does_not_add_spin(self):
        """@brief An expired final deadline cannot acquire an extra busy-wait tail."""
        wait = self.waiter(FakeTimer(self.clock, waits=[2]), spin_tail_seconds=0.0006)
        wait(0.002)
        self.assertEqual(wait.snapshot()["spin_calls"], 0)
        self.assertGreater(wait.snapshot()["max_overshoot_ms"], 0)

    def test_native_early_wake_rearms_before_the_bounded_tail(self):
        """@brief A true early wake does not turn the preceding blocking interval into spin."""
        self.clock.tick = 0.000005
        wait = self.waiter(FakeTimer(self.clock, waits=[0.5]), spin_tail_seconds=0.0006)
        wait(0.004)
        self.assertEqual(wait.snapshot()["early_wakes"], 1)
        self.assertEqual(wait.snapshot()["native_calls"], 2)
        self.assertEqual(wait.snapshot()["spin_calls"], 1)
        self.assertLess(wait.snapshot()["spin_wall_seconds"], 0.00065)

    def test_cancel_during_native_tail(self):
        """@brief Cancellation stays observable inside an explicitly selected busy tail."""
        self.clock.tick = 0.000005
        wait = self.waiter(spin_tail_seconds=0.0006, cancelled=lambda: self.clock.now >= 10.0017)
        with self.assertRaisesRegex(InterruptedError, "cancelled"):
            wait(0.002)
        self.assertEqual(wait.snapshot()["spin_calls"], 1)
        self.assertEqual(wait.snapshot()["cancelled"], 1)
        self.assertGreater(wait.snapshot()["spin_wall_seconds"], 0)
        self.assertLess(self.clock.now, 10.002)

    def test_hybrid_only_spins_the_final_long_wait_chunk(self):
        """@brief Long waits block in bounded chunks and reserve one final requested tail."""
        self.clock.tick = 0.000005
        wait = self.waiter(spin_tail_seconds=0.0006)
        wait(0.12)
        self.assertEqual(len(self.timer.waits), 3)
        self.assertEqual(self.timer.waits[:2], [0.05, 0.05])
        self.assertEqual(wait.snapshot()["spin_calls"], 1)

    def test_non_windows_never_spins_even_when_requested(self):
        """@brief An unsupported platform visibly disables the requested native-only tail."""
        wait = PreciseWait(
            clock=self.clock, fallback=self.fallback, platform="linux", spin_tail_seconds=0.0006
        )
        wait(0.002)
        self.assertEqual(wait.snapshot()["spin_calls"], 0)
        self.assertEqual(wait.snapshot()["spin_tail_requested_seconds"], 0.0006)
        self.assertEqual(wait.snapshot()["spin_tail_effective_seconds"], 0)
        self.assertEqual(wait.snapshot()["spin_disabled_reason"], "non-Windows platform")

    def test_native_initialization_failure_disables_tail(self):
        """@brief Creation fallback never silently substitutes CPU spinning for a timer."""
        wait = PreciseWait(
            clock=self.clock,
            fallback=self.fallback,
            platform="win32",
            timer_factory=Mock(side_effect=OSError("unsupported")),
            spin_tail_seconds=0.0006,
        )
        wait(0.002)
        self.assertEqual(wait.snapshot()["spin_calls"], 0)
        self.assertEqual(wait.snapshot()["spin_tail_effective_seconds"], 0)
        self.assertIn("native initialization", wait.snapshot()["spin_disabled_reason"])

    def test_native_wait_failure_disables_tail_before_fallback(self):
        """@brief A runtime timer failure waits normally rather than spinning its remainder."""
        timer = FakeTimer(self.clock, waits=[OSError("wait failed")])
        wait = self.waiter(timer, spin_tail_seconds=0.0006)
        wait(0.002)
        self.assertEqual(wait.snapshot()["spin_calls"], 0)
        self.assertEqual(wait.snapshot()["fallback_calls"], 1)
        self.assertEqual(wait.snapshot()["spin_tail_effective_seconds"], 0)
        self.assertIn("native wait", wait.snapshot()["spin_disabled_reason"])
        self.assertEqual(timer.close_calls, 1)

    def test_invalid_spin_tail_rejected_before_native_creation(self):
        """@brief No caller can select an unbounded spin tail or nonnumeric spin policy."""
        factory = Mock(side_effect=AssertionError("unexpected native creation"))
        for tail in (-0.0001, 0.0011, math.inf, math.nan, True, None, "0", 10**1000):
            with self.subTest(tail=tail), self.assertRaisesRegex(ValueError, "Spin tail"):
                PreciseWait(spin_tail_seconds=tail, timer_factory=factory)
        factory.assert_not_called()

    def test_maximum_explicit_tail_is_accepted(self):
        """@brief The documented one-millisecond boundary is inclusive and opt-in only."""
        wait = self.waiter(spin_tail_seconds=0.001)
        self.assertEqual(wait.snapshot()["spin_tail_effective_seconds"], 0.001)


class WindowsTimerTests(unittest.TestCase):
    """@brief Check Win32 ABI parameters, error handling and exact handle lifetime."""

    def setUp(self):
        """@brief Use fake callable Win32 exports without accessing a physical OS timer."""
        self.api = SimpleNamespace(
            CreateWaitableTimerExW=Mock(return_value=42),
            SetWaitableTimerEx=Mock(return_value=1),
            WaitForSingleObject=Mock(return_value=0),
            CloseHandle=Mock(return_value=1),
        )

    def timer(self):
        """@brief Construct a native adapter with a stable error-code oracle."""
        return _WindowsTimer(self.api, lambda: 5)

    def test_native_parameters_round_up_and_close_once(self):
        """@brief One-shot relative due times round up to prevent an intentionally early wake."""
        timer = self.timer()
        self.api.CreateWaitableTimerExW.assert_called_once_with(None, None, 2, 0x00100002)
        timer.wait(0.00000001)
        args = self.api.SetWaitableTimerEx.call_args.args
        self.assertEqual(ctypes.cast(args[1], ctypes.POINTER(ctypes.c_longlong)).contents.value, -1)
        self.assertEqual(args[2:], (0, None, None, None, 0))
        self.api.WaitForSingleObject.assert_called_once_with(42, 51)
        timer.close()
        timer.close()
        self.api.CloseHandle.assert_called_once_with(42)
        with self.assertRaisesRegex(OSError, "closed"):
            timer.wait(0.001)

    def test_native_creation_failure(self):
        """@brief A null timer handle never becomes a valid backend."""
        self.api.CreateWaitableTimerExW.return_value = None
        with self.assertRaisesRegex(OSError, "CreateWaitableTimerExW"):
            self.timer()

    def test_native_arm_failure(self):
        """@brief Failed arming never enters an unrelated handle wait."""
        timer = self.timer()
        self.api.SetWaitableTimerEx.return_value = 0
        with self.assertRaisesRegex(OSError, "SetWaitableTimerEx"):
            timer.wait(0.002)
        self.api.WaitForSingleObject.assert_not_called()
        timer.close()

    def test_native_timeout_or_failed_wait(self):
        """@brief Timeout and any unexpected Windows wait result remain failures."""
        timer = self.timer()
        for result, message in (
            (0x102, "safety timeout"),
            (0xFFFFFFFF, "WaitForSingleObject"),
            (0x80, "WaitForSingleObject"),
        ):
            with self.subTest(result=result):
                self.api.WaitForSingleObject.return_value = result
                with self.assertRaisesRegex(OSError, message):
                    timer.wait(0.002)
        timer.close()

    def test_native_close_failure_preserves_handle(self):
        """@brief Failed closes can be retried instead of discarding a live handle."""
        timer = self.timer()
        self.api.CloseHandle.return_value = 0
        with self.assertRaisesRegex(OSError, "CloseHandle"):
            timer.close()
        self.assertEqual(timer.handle, 42)
        self.api.CloseHandle.return_value = 1
        timer.close()
        self.assertIsNone(timer.handle)

    @unittest.skipUnless(sys.platform == "win32", "Windows timer smoke check")
    def test_real_default_backend_closes_without_a_benchmark(self):
        """@brief Exercise actual ABI binding and one zero-duration call without timing claims."""
        with PreciseWait() as wait:
            wait(0)
            self.assertIn(wait.snapshot()["backend"], ("windows-high-resolution", "sleep"))


if __name__ == "__main__":
    unittest.main()
