"""@brief Tests for non-injecting Game Bub controller state tracking."""

import unittest

from controller import ControllerTracker


class ControllerTrackerTests(unittest.TestCase):
    """@brief Verify button changes, video ordering, timeouts, and session reset."""

    def test_button_chords_and_same_frame_heartbeat(self):
        """@brief Complete snapshots map button chords and heartbeat releases."""
        tracker = ControllerTracker(10)
        self.assertEqual(tracker.accept(1, 20, (1 << 11) | (1 << 7), 100), 0x1001)
        self.assertIsNone(tracker.accept(1, 20, (1 << 11) | (1 << 7), 105))
        self.assertEqual(tracker.accept(1, 20, 1 << 7, 106), 0x0001)
        self.assertEqual(tracker.accept(2, 21, 0, 107), 0)
        self.assertIsNone(tracker.disconnect())

    def test_wrap_stale_and_invalid_frame_identity(self):
        """@brief Reject old IDs and wrong same-ID timestamps while accepting wrap."""
        tracker = ControllerTracker(10)
        self.assertEqual(tracker.accept(0xFFFFFFFF, 1, 1 << 11, 100), 0x1000)
        self.assertIsNone(tracker.accept(0xFFFFFFFF, 2, 0, 101))
        self.assertIsNone(tracker.accept(0xFFFFFFFE, 1, 0, 101))
        self.assertIsNone(tracker.accept(0x7FFFFFFF, 1, 0, 101))
        self.assertEqual(tracker.accept(0, 3, 0, 102), 0)

    def test_timeout_requires_new_frame_and_disconnect_is_neutral(self):
        """@brief Release once on silence and refuse a stale heartbeat after timeout."""
        tracker = ControllerTracker(10)
        self.assertIsNone(tracker.expire(90))
        self.assertEqual(tracker.accept(10, 20, 1 << 11, 100), 0x1000)
        self.assertIsNone(tracker.expire(110))
        self.assertEqual(tracker.expire(111), 0)
        self.assertIsNone(tracker.expire(112))
        self.assertIsNone(tracker.accept(10, 20, 1 << 11, 113))
        self.assertEqual(tracker.accept(11, 21, 1 << 11, 114), 0x1000)
        self.assertEqual(tracker.disconnect(), 0)
        self.assertIsNone(tracker.disconnect())
        self.assertEqual(tracker.accept(1, 1, 1 << 11, 1), 0x1000)

    def test_invalid_metadata_and_reserved_mask_are_rejected(self):
        """@brief Malformed feedback cannot alter or refresh the controller state."""
        for timeout in (0, -1, True):
            with self.assertRaises(ValueError):
                ControllerTracker(timeout)
        tracker = ControllerTracker(10)
        tracker.accept(1, 1, 1 << 11, 100)
        for args in (
            (-1, 1, 0, 101),
            (2**32, 1, 0, 101),
            (1, -1, 0, 101),
            (1, 2**64, 0, 101),
            (1, 1, 1 << 12, 101),
            (1, 1, 0, 99),
            (True, 1, 0, 101),
            (1, 1, 0, True),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                tracker.accept(*args)
        for now in (-1, True, 99):
            with self.assertRaises(ValueError):
                tracker.expire(now)
        self.assertEqual(tracker.expire(111), 0)

    def test_neutral_timeout_also_requires_new_frame(self):
        """@brief A neutral timeout cannot be reversed by a delayed same-frame press."""
        tracker = ControllerTracker(10)
        self.assertIsNone(tracker.accept(1, 1, 0, 100))
        self.assertIsNone(tracker.expire(111))
        self.assertIsNone(tracker.accept(1, 1, 1 << 11, 112))
        self.assertEqual(tracker.accept(2, 2, 1 << 11, 113), 0x1000)


if __name__ == "__main__":
    unittest.main()
