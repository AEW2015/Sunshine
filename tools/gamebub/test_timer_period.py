"""@brief Fake-only period ownership tests; no timer-resolution request is made."""

import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from timer_period import ProcessTimerPeriod, _WinmmPeriod


def version(major=10, minor=0, build=19045):
    """@brief Construct a synthetic Windows version with explicit major/minor/build."""
    return SimpleNamespace(major=major, minor=minor, build=build)


class ProcessTimerPeriodTests(unittest.TestCase):
    """@brief Verify explicit selection, supported version gate and exact request accounting."""

    def setUp(self):
        """@brief Build fake version/API dependencies without loading Winmm."""
        self.api = SimpleNamespace(begin=Mock(return_value=0), end=Mock(return_value=0))
        self.factory = Mock(return_value=self.api)
        self.get_version = Mock(return_value=version())

    def request(self, **kwargs):
        """@brief Construct the enabled path with all native dependencies injected."""
        defaults = {
            "enabled": True,
            "platform": "win32",
            "version_getter": self.get_version,
            "api_factory": self.factory,
        }
        defaults.update(kwargs)
        return ProcessTimerPeriod(**defaults)

    def test_default_is_disabled_and_never_loads_native_api(self):
        """@brief Default construction and context entry make no request or version query."""
        with self.request(enabled=False) as period:
            self.assertFalse(period.snapshot()["active"])
            self.assertEqual(period.snapshot()["refusal_reason"], "not requested")
        self.get_version.assert_not_called()
        self.factory.assert_not_called()
        self.assertTrue(period.snapshot()["balanced"])

    def test_construction_alone_does_not_start_request(self):
        """@brief Even enabled construction only stores intent until explicit start."""
        period = self.request()
        self.assertFalse(period.snapshot()["attempted"])
        self.get_version.assert_not_called()
        self.factory.assert_not_called()

    def test_supported_request_is_balanced_and_idempotent(self):
        """@brief Multiple start/close calls still make exactly one successful Begin/End pair."""
        with self.request() as period:
            self.assertTrue(period.start())
            self.assertTrue(period.snapshot()["active"])
            self.assertFalse(period.snapshot()["balanced"])
            self.assertEqual(
                period.snapshot()["verified_version"], {"major": 10, "minor": 0, "build": 19045}
            )
        period.close()
        self.api.begin.assert_called_once_with(1)
        self.api.end.assert_called_once_with(1)
        self.assertTrue(period.snapshot()["balanced"])
        self.assertEqual(period.snapshot()["begin_successes"], 1)
        self.assertEqual(period.snapshot()["end_successes"], 1)

    def test_boundary_build_and_windows11_kernel_family_are_eligible(self):
        """@brief Accept only the documented NT10.0 family from build19041 onward."""
        for build in (19041, 22000):
            with self.subTest(build=build):
                self.get_version.return_value = version(build=build)
                period = self.request()
                self.assertTrue(period.start())
                period.close()

    def test_non_windows_never_reads_version_or_loads_api(self):
        """@brief Explicit selection on another platform is visible refusal, not a native call."""
        with self.request(platform="linux") as period:
            self.assertEqual(period.snapshot()["refusal_reason"], "non-Windows platform")
        self.get_version.assert_not_called()
        self.factory.assert_not_called()

    def test_old_or_unknown_windows_version_is_refused(self):
        """@brief Versions with global or unknown semantics do not request a timer period."""
        for candidate in (
            version(6, 3, 9600),
            version(10, 1, 22000),
            version(build=19040),
            version(11, 0, 30000),
        ):
            with self.subTest(candidate=candidate):
                self.get_version.return_value = candidate
                period = self.request()
                self.assertFalse(period.start())
                self.assertFalse(period.snapshot()["eligible"])
                self.assertIn("19041", period.snapshot()["refusal_reason"])
                period.close()
        self.factory.assert_not_called()

    def test_unverifiable_version_remains_a_fallback(self):
        """@brief Version errors must not guess that process-scoped behavior is available."""
        for error in (
            AttributeError("not available"),
            OSError("query failed"),
            ValueError("invalid version"),
        ):
            with self.subTest(error=error):
                period = self.request(version_getter=Mock(side_effect=error))
                self.assertFalse(period.start())
                self.assertIn("could not be verified", period.snapshot()["refusal_reason"])
                self.assertEqual(period.snapshot()["last_error"], str(error))
        self.factory.assert_not_called()

    def test_version_with_missing_fields_is_refused(self):
        """@brief Malformed version observations cannot bypass the eligibility gate."""
        self.get_version.return_value = SimpleNamespace(major=10)
        self.assertFalse(self.request().start())
        self.factory.assert_not_called()

    def test_version_fields_must_be_actual_integers(self):
        """@brief Strings and booleans do not count as verified version fields."""
        for candidate in (version(major="10"), version(minor=False), version(build=None)):
            with self.subTest(candidate=candidate):
                self.get_version.return_value = candidate
                period = self.request()
                self.assertFalse(period.start())
                self.assertEqual(
                    period.snapshot()["refusal_reason"], "Windows version fields are invalid"
                )
        self.factory.assert_not_called()

    def test_initialization_failure_is_visible_without_begin(self):
        """@brief Missing Winmm or exports never masquerade as an active period."""
        for error in (OSError("load failed"), AttributeError("missing export")):
            with self.subTest(error=error):
                period = self.request(api_factory=Mock(side_effect=error))
                self.assertFalse(period.start())
                self.assertEqual(period.snapshot()["initialization_errors"], 1)
                self.assertEqual(period.snapshot()["begin_calls"], 0)
                period.close()
        self.api.begin.assert_not_called()
        self.api.end.assert_not_called()

    def test_begin_refusal_is_not_retried_or_released(self):
        """@brief A failed Begin owns no request and causes no matching End call."""
        self.api.begin.return_value = 97
        period = self.request()
        self.assertFalse(period.start())
        self.assertFalse(period.start())
        period.close()
        self.assertEqual(period.snapshot()["begin_errors"], 1)
        self.assertEqual(period.snapshot()["last_error"], "MMRESULT 97")
        self.assertTrue(period.snapshot()["balanced"])
        self.api.begin.assert_called_once_with(1)
        self.api.end.assert_not_called()

    def test_begin_exception_is_visible(self):
        """@brief An API exception before success never produces a cleanup request."""
        self.api.begin.side_effect = OSError("begin failed")
        period = self.request()
        self.assertFalse(period.start())
        self.assertEqual(period.snapshot()["begin_errors"], 1)
        self.assertIn("begin failed", period.snapshot()["last_error"])
        period.close()
        self.api.end.assert_not_called()

    def test_end_refusal_is_reported_and_retryable(self):
        """@brief Failed release does not falsely clear ownership or balanced accounting."""
        self.api.end.side_effect = [97, 0]
        period = self.request()
        period.start()
        with self.assertRaisesRegex(OSError, "timeEndPeriod"):
            period.close()
        self.assertTrue(period.snapshot()["active"])
        self.assertFalse(period.snapshot()["balanced"])
        self.assertEqual(period.snapshot()["end_errors"], 1)
        period.close()
        self.assertFalse(period.snapshot()["active"])
        self.assertTrue(period.snapshot()["balanced"])
        self.assertEqual(period.snapshot()["end_calls"], 2)

    def test_end_exception_is_reported_and_retryable(self):
        """@brief Native release exceptions retain an explicit active request until retried."""
        self.api.end.side_effect = [OSError("end failed"), 0]
        period = self.request()
        period.start()
        with self.assertRaisesRegex(OSError, "end failed"):
            period.close()
        self.assertTrue(period.snapshot()["active"])
        self.assertIn("end failed", period.snapshot()["last_error"])
        period.close()
        self.assertEqual(period.snapshot()["end_successes"], 1)

    def test_exceptional_context_still_balances_period(self):
        """@brief An unrelated failure inside a benchmark context still releases its request."""
        period = self.request()
        with self.assertRaisesRegex(RuntimeError, "benchmark failed"), period:
            raise RuntimeError("benchmark failed")
        self.api.end.assert_called_once_with(1)
        self.assertTrue(period.snapshot()["balanced"])

    def test_close_before_start_and_closed_reentry_are_safe(self):
        """@brief Closed ownership cannot be reopened or silently request another period."""
        period = self.request()
        period.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            period.start()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            period.__enter__()
        self.api.begin.assert_not_called()

    def test_nested_owners_balance_their_own_requests(self):
        """@brief Two explicit owners make two matching pairs, not one shared hidden request."""
        with self.request():
            with self.request():
                self.assertEqual(self.api.begin.call_count, 2)
            self.assertEqual(self.api.end.call_count, 1)
        self.assertEqual(self.api.end.call_count, 2)

    def test_invalid_selection_and_period_are_rejected(self):
        """@brief The helper cannot accidentally widen the experiment beyond explicit 1 ms."""
        for fields in (
            {"enabled": 1},
            {"enabled": "yes"},
            {"period_ms": True},
            {"period_ms": 0},
            {"period_ms": 2},
            {"period_ms": 1.0},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                ProcessTimerPeriod(**fields)

    def test_snapshot_cannot_mutate_owned_version(self):
        """@brief Diagnostics are copies of both counters and the verified version."""
        period = self.request()
        period.start()
        saved = period.snapshot()
        saved["verified_version"]["build"] = 1
        saved["begin_calls"] = 99
        self.assertEqual(period.snapshot()["verified_version"]["build"], 19045)
        self.assertEqual(period.snapshot()["begin_calls"], 1)
        period.close()

    def test_default_platform_and_version_reader_use_injected_native_api(self):
        """@brief Exercise default platform/version selection using fake Windows observations."""
        with (
            patch("timer_period.sys.platform", "win32"),
            patch("timer_period.sys.getwindowsversion", return_value=version(), create=True),
        ):
            period = ProcessTimerPeriod(enabled=True, api_factory=self.factory)
            self.assertTrue(period.start())
            period.close()

    def test_default_factory_binds_fake_winmm_without_an_actual_period_change(self):
        """@brief Test the production construction path with a fake WinDLL object only."""
        api = SimpleNamespace(
            timeBeginPeriod=Mock(return_value=0), timeEndPeriod=Mock(return_value=0)
        )
        with patch("timer_period.ctypes.WinDLL", return_value=api, create=True) as loader:
            period = ProcessTimerPeriod(
                enabled=True, platform="win32", version_getter=lambda: version()
            )
            self.assertTrue(period.start())
            period.close()
        loader.assert_called_once_with("winmm")
        api.timeBeginPeriod.assert_called_once_with(1)
        api.timeEndPeriod.assert_called_once_with(1)
        self.assertEqual(api.timeBeginPeriod.argtypes, [ctypes.c_uint])
        self.assertIs(api.timeEndPeriod.restype, ctypes.c_uint)

    def test_winmm_adapter_returns_native_result_codes(self):
        """@brief Native MMRESULT failures reach the owner without BOOL conversion."""
        api = SimpleNamespace(
            timeBeginPeriod=Mock(return_value=97), timeEndPeriod=Mock(return_value=96)
        )
        adapter = _WinmmPeriod(api)
        self.assertEqual(adapter.begin(1), 97)
        self.assertEqual(adapter.end(1), 96)


if __name__ == "__main__":
    unittest.main()
