"""@brief Explicit process timer-period experiment with version gating and balanced cleanup.

The default is disabled. Nothing is requested merely by importing this module
or constructing an object. With explicit enablement, start/context entry allows
one 1 ms request only on verified Windows NT 10.0 build 19041 or newer.

Microsoft documents process-scoped behavior from Windows 10 version 2004, not
older releases. This is process-wide within the selected experiment, not a
thread-local change. Windows 11 may not retain the higher resolution for fully
occluded, minimized, invisible or inaudible window-owning processes. Timer
resolution is not a wake-deadline or performance guarantee and can affect power.
No NtSetTimerResolution call or system-wide setting is used.

https://learn.microsoft.com/windows/win32/api/timeapi/nf-timeapi-timebeginperiod
https://learn.microsoft.com/windows/win32/api/timeapi/nf-timeapi-timeendperiod
"""

import ctypes
import sys


class _WinmmPeriod:
    """@brief Bind the documented multimedia API without making a period request."""

    def __init__(self, api=None):
        """@brief Configure explicit signatures for injected or actual Winmm exports.

        @param api Optional injected Winmm export object for tests.
        """
        self.api = api if api is not None else ctypes.WinDLL("winmm")
        self.api.timeBeginPeriod.argtypes = [ctypes.c_uint]
        self.api.timeBeginPeriod.restype = ctypes.c_uint
        self.api.timeEndPeriod.argtypes = [ctypes.c_uint]
        self.api.timeEndPeriod.restype = ctypes.c_uint

    def begin(self, period_ms):
        """@brief Return the API result for one caller-selected period request."""
        return self.api.timeBeginPeriod(period_ms)

    def end(self, period_ms):
        """@brief Return the matching period-release result without hiding failure."""
        return self.api.timeEndPeriod(period_ms)


class ProcessTimerPeriod:
    """@brief Own at most one explicitly enabled process-scoped 1 ms period request.

    This object has a single lifecycle owner; start and close must not race.
    Unsupported/failed starts are visible fallbacks, never automatic requests on
    older Windows releases. Failed cleanup remains active and can be retried.
    """

    def __init__(
        self, *, enabled=False, period_ms=1, platform=None, version_getter=None, api_factory=None
    ):
        """@brief Retain selection and dependencies without changing timer state.

        @param enabled Explicit opt-in; disabled by default.
        @param period_ms Only integer 1 is accepted for this narrow experiment.
        @param platform Optional platform identifier; defaults to sys.platform.
        @param version_getter Optional Windows major/minor/build reader.
        @param api_factory Optional constructor returning begin()/end() methods.
        @throws ValueError If the selection is not boolean or period is not 1 ms.
        """
        if type(enabled) is not bool or type(period_ms) is not int or period_ms != 1:
            raise ValueError("Select a boolean enablement and exactly 1 ms")
        self.enabled = enabled
        self.period_ms = period_ms
        self.platform = sys.platform if platform is None else platform
        self.version_getter = version_getter
        self.api_factory = api_factory
        self.api = None
        self.version = None
        self.eligible = False
        self.attempted = False
        self.active = False
        self.closed = False
        self.begin_calls = self.begin_successes = self.end_calls = self.end_successes = 0
        self.begin_errors = self.end_errors = self.initialization_errors = 0
        self.reason = "not requested" if not enabled else "not started"
        self.last_error = None

    def start(self):
        """@brief Request one period after an explicit opt-in and verified OS check.

        @return True while the request is active, False for a visible refusal/fallback.
        @throws RuntimeError If start is attempted after close.
        """
        if self.closed:
            raise RuntimeError("ProcessTimerPeriod is closed")
        if self.active:
            return True
        if self.attempted:
            return False
        self.attempted = True
        if not self.enabled:
            return False
        if self.platform != "win32":
            self.reason = "non-Windows platform"
            return False
        try:
            version = (
                sys.getwindowsversion if self.version_getter is None else self.version_getter
            )()
            values = (version.major, version.minor, version.build)
        except (AttributeError, OSError, ValueError) as error:
            self.reason = "Windows version could not be verified"
            self.last_error = str(error)
            return False
        if any(type(value) is not int for value in values):
            self.reason = "Windows version fields are invalid"
            return False
        self.version = dict(zip(("major", "minor", "build"), values))
        if version.major != 10 or version.minor != 0 or version.build < 19041:
            self.reason = "Requires verified Windows NT 10.0 build 19041 or newer"
            return False
        self.eligible = True
        try:
            self.api = (_WinmmPeriod if self.api_factory is None else self.api_factory)()
        except (OSError, AttributeError) as error:
            self.initialization_errors += 1
            self.reason = "Winmm initialization failed"
            self.last_error = str(error)
            return False
        self.begin_calls += 1
        try:
            result = self.api.begin(self.period_ms)
        except OSError as error:
            self.begin_errors += 1
            self.reason = "timeBeginPeriod failed"
            self.last_error = str(error)
            return False
        if result != 0:
            self.begin_errors += 1
            self.reason = "timeBeginPeriod refused the request"
            self.last_error = f"MMRESULT {result}"
            return False
        self.begin_successes += 1
        self.active = True
        self.reason = None
        return True

    def close(self):
        """@brief Balance a successful Begin with the same End period exactly once.

        @throws OSError If cleanup fails; active state is retained for explicit retry.
        """
        self.closed = True
        if not self.active:
            return
        self.end_calls += 1
        try:
            result = self.api.end(self.period_ms)
        except OSError as error:
            self.end_errors += 1
            self.last_error = str(error)
            raise
        if result != 0:
            self.end_errors += 1
            self.last_error = f"MMRESULT {result}"
            raise OSError(result, "timeEndPeriod failed")
        self.end_successes += 1
        self.active = False

    def snapshot(self):
        """@brief Return owned-lifecycle accounting, version gate and cleanup status."""
        return {
            "requested": self.enabled,
            "period_ms": self.period_ms,
            "platform": self.platform,
            "verified_version": None if self.version is None else dict(self.version),
            "eligible": self.eligible,
            "attempted": self.attempted,
            "active": self.active,
            "closed": self.closed,
            "begin_calls": self.begin_calls,
            "begin_successes": self.begin_successes,
            "end_calls": self.end_calls,
            "end_successes": self.end_successes,
            "begin_errors": self.begin_errors,
            "end_errors": self.end_errors,
            "initialization_errors": self.initialization_errors,
            "balanced": self.begin_successes == self.end_successes,
            "refusal_reason": self.reason,
            "last_error": self.last_error,
        }

    def __enter__(self):
        """@brief Start only the explicitly selected request on context entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """@brief Release an active request on normal or exceptional context exit."""
        self.close()
