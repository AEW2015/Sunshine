"""@brief Optional blocking Windows pacing wait with explicit fallback and lifecycle.

This helper changes no timer resolution and defaults to no busy spin. An
explicit native-only tail can busy-wait for at most the requested final 1 ms.
It is a
single-owner sleeper: make all wait calls in one worker, then close after that
worker has stopped. Construction may precede worker startup. Cancellation is checked between bounded
wait chunks. The sender still owns deadlines, rate accounting and liveness.

Native contract: Microsoft CreateWaitableTimerExW, SetWaitableTimerEx and
WaitForSingleObject documentation. A high-resolution timer is requested; an
unsupported or failed backend falls back visibly to the injected ordinary sleep.
https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-createwaitabletimerexw
https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-setwaitabletimerex
https://learn.microsoft.com/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject
"""

import ctypes
import math
import sys
import time


class _WindowsTimer:
    """@brief Own one unnamed auto-reset Windows high-resolution waitable timer."""

    def __init__(self, kernel32=None, last_error=None):
        """@brief Configure explicit ABI signatures before creating a non-inheritable handle.

        @param kernel32 Optional injected API object for deterministic tests.
        @param last_error Optional injected Windows error-code reader.
        """
        self.api = (
            kernel32 if kernel32 is not None else ctypes.WinDLL("kernel32", use_last_error=True)
        )
        self.last_error = last_error if last_error is not None else ctypes.get_last_error
        self.handle = None
        self.api.CreateWaitableTimerExW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.api.CreateWaitableTimerExW.restype = ctypes.c_void_p
        self.api.SetWaitableTimerEx.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_longlong),
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self.api.SetWaitableTimerEx.restype = ctypes.c_int
        self.api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.api.WaitForSingleObject.restype = ctypes.c_ulong
        self.api.CloseHandle.argtypes = [ctypes.c_void_p]
        self.api.CloseHandle.restype = ctypes.c_int
        # TIMER_MODIFY_STATE | SYNCHRONIZE; no named or inheritable handle.
        self.handle = self.api.CreateWaitableTimerExW(None, None, 0x2, 0x00100002)
        if not self.handle:
            raise OSError(self.last_error(), "CreateWaitableTimerExW failed")

    def wait(self, seconds):
        """@brief Arm a one-shot relative timer, then block with a finite safety timeout.

        @param seconds Positive duration, bounded to at most 50 ms by PreciseWait.
        @throws OSError If arm/wait fails or the finite timer wait times out.
        """
        if self.handle is None:
            raise OSError("Waitable timer is closed")
        due = ctypes.c_longlong(-max(1, math.ceil(seconds * 10_000_000)))
        if not self.api.SetWaitableTimerEx(self.handle, ctypes.byref(due), 0, None, None, None, 0):
            raise OSError(self.last_error(), "SetWaitableTimerEx failed")
        result = self.api.WaitForSingleObject(self.handle, math.ceil(seconds * 1000) + 50)
        if result == 0x102:
            raise OSError("Waitable timer safety timeout")
        if result != 0:
            raise OSError(self.last_error(), f"WaitForSingleObject failed: {result}")

    def close(self):
        """@brief Close the handle once; retain it for a retry if CloseHandle fails."""
        if self.handle is not None:
            if not self.api.CloseHandle(self.handle):
                raise OSError(self.last_error(), "CloseHandle failed")
            self.handle = None


class PreciseWait:
    """@brief Callable precise sleeper with QPC deadline rechecks and visible fallback.

    Native waits are capped at 50 ms plus a finite safety margin. Cancellation
    is cooperative, not an asynchronous close of a pending Windows wait. Do not
    close concurrently: Windows documents that as undefined behavior.
    """

    def __init__(
        self,
        *,
        clock=time.perf_counter,
        fallback=time.sleep,
        timer_factory=None,
        platform=None,
        cancelled=lambda: False,
        spin_tail_seconds=0,
        cpu_clock=time.thread_time,
    ):
        """@brief Select a native high-resolution backend only on Windows.

        @param clock Monotonic seconds clock, injectable for tests.
        @param fallback Ordinary blocking sleeper, injectable for tests.
        @param timer_factory Optional constructor returning wait()/close() backend.
        @param platform Optional platform name; defaults to sys.platform.
        @param cancelled Predicate checked before and after each bounded wait.
        @param spin_tail_seconds Explicit native-only final tail, between zero and 1 ms.
        @param cpu_clock Sender-thread CPU seconds clock, injectable for accounting tests.
        """
        if (
            isinstance(spin_tail_seconds, bool)
            or not isinstance(spin_tail_seconds, (int, float))
            or not 0 <= spin_tail_seconds <= 0.001
        ):
            raise ValueError("Spin tail must be between zero and 1 ms")
        self.clock, self.fallback, self.cancelled = clock, fallback, cancelled
        self.cpu_clock = cpu_clock
        self.spin_tail_requested = float(spin_tail_seconds)
        self.spin_tail_effective = 0.0
        self.timer = None
        self.backend_name = "sleep"
        self.pending_close = []
        self.closed = False
        self.counts = {
            "calls": 0,
            "native_calls": 0,
            "fallback_calls": 0,
            "runtime_failures": 0,
            "close_failures": 0,
            "cancelled": 0,
            "early_wakes": 0,
            "requested_seconds": 0.0,
            "elapsed_seconds": 0.0,
            "max_overshoot_ms": 0.0,
            "thread_cpu_seconds": 0.0,
            "spin_calls": 0,
            "spin_wall_seconds": 0.0,
            "spin_thread_cpu_seconds": 0.0,
        }
        self.fallback_reason = "non-Windows platform"
        if (sys.platform if platform is None else platform) == "win32":
            try:
                self.timer = (_WindowsTimer if timer_factory is None else timer_factory)()
            except (OSError, AttributeError) as error:
                self.fallback_reason = f"native initialization: {error}"
            else:
                self.fallback_reason = None
                self.backend_name = "windows-high-resolution"
                self.spin_tail_effective = self.spin_tail_requested

    def _retire_native(self, reason):
        """@brief Disable a failed backend and retain any failed close for final cleanup."""
        self.fallback_reason = reason
        self.backend_name = "sleep"
        self.spin_tail_effective = 0.0
        timer, self.timer = self.timer, None
        try:
            timer.close()
        except OSError:
            self.counts["close_failures"] += 1
            self.pending_close.append(timer)

    def _check_cancelled(self):
        """@brief Raise once when cooperative cancellation is observed, including in a tail."""
        if self.cancelled():
            self.counts["cancelled"] += 1
            raise InterruptedError("PreciseWait cancelled")

    def _spin_until(self, deadline):
        """@brief Finish only the explicit bounded native tail and account its actual cost."""
        started = self.clock()
        if started >= deadline:
            return
        cpu_started = self.cpu_clock()
        self.counts["spin_calls"] += 1
        try:
            while self.clock() < deadline:
                self._check_cancelled()
        finally:
            self.counts["spin_wall_seconds"] += max(0, self.clock() - started)
            self.counts["spin_thread_cpu_seconds"] += max(0, self.cpu_clock() - cpu_started)

    def __call__(self, seconds):
        """@brief Block until the requested local deadline, cancellation or failure.

        @param seconds Finite nonnegative duration; booleans are rejected.
        @throws ValueError If duration or computed deadline is invalid.
        @throws RuntimeError If called after close.
        @throws InterruptedError If the cancellation predicate becomes true.
        """
        if self.closed:
            raise RuntimeError("PreciseWait is closed")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
            raise ValueError("Wait duration must be finite and nonnegative")
        try:
            seconds = float(seconds)
        except OverflowError as error:
            raise ValueError("Wait duration must be finite and nonnegative") from error
        if not math.isfinite(seconds):
            raise ValueError("Wait duration must be finite and nonnegative")
        started = self.clock()
        deadline = started + seconds
        if not math.isfinite(deadline):
            raise ValueError("Wait deadline must be finite")
        self.counts["calls"] += 1
        self.counts["requested_seconds"] += seconds
        cpu_started = self.cpu_clock()
        try:
            while True:
                self._check_cancelled()
                now = self.clock()
                remaining = deadline - now
                if remaining <= 0:
                    return
                chunk = min(remaining, 0.05)
                if self.timer is None:
                    self.counts["fallback_calls"] += 1
                    self.fallback(chunk)
                else:
                    tail = min(chunk, self.spin_tail_effective) if remaining <= 0.05 else 0
                    blocking = chunk - tail
                    blocking_deadline = now + blocking
                    if blocking > 0:
                        self.counts["native_calls"] += 1
                        try:
                            self.timer.wait(blocking)
                        except OSError as error:
                            self.counts["runtime_failures"] += 1
                            self._retire_native(f"native wait: {error}")
                            continue
                        if self.clock() < blocking_deadline:
                            self.counts["early_wakes"] += 1
                            continue
                    if tail > 0:
                        self._check_cancelled()
                        self._spin_until(deadline)
        finally:
            elapsed = max(0, self.clock() - started)
            self.counts["elapsed_seconds"] += elapsed
            self.counts["thread_cpu_seconds"] += max(0, self.cpu_clock() - cpu_started)
            self.counts["max_overshoot_ms"] = max(
                self.counts["max_overshoot_ms"], (elapsed - seconds) * 1000
            )

    def snapshot(self):
        """@brief Return copyable counters without performing I/O or resetting totals."""
        return {
            **self.counts,
            "backend": self.backend_name,
            "fallback_reason": self.fallback_reason,
            "closed": self.closed,
            "pending_close": len(self.pending_close),
            "spin_tail_requested_seconds": self.spin_tail_requested,
            "spin_tail_effective_seconds": self.spin_tail_effective,
            "spin_disabled_reason": (
                self.fallback_reason
                if self.spin_tail_requested and not self.spin_tail_effective
                else None
            ),
        }

    def close(self):
        """@brief Close owned timers after the worker stops; retry failed closes explicitly."""
        self.closed = True
        timers = self.pending_close
        self.pending_close = []
        if self.timer is not None:
            timers.append(self.timer)
            self.timer = None
        last_error = None
        for timer in timers:
            try:
                timer.close()
            except OSError as error:
                self.counts["close_failures"] += 1
                self.pending_close.append(timer)
                last_error = error
        if last_error is not None:
            raise last_error

    def __enter__(self):
        """@brief Return the open owned waiter for a context-managed lifetime."""
        if self.closed:
            raise RuntimeError("PreciseWait is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """@brief Close owned timers on normal or exceptional context exit."""
        self.close()
