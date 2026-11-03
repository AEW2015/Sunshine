"""@brief Deterministic tests for bounded JPEG quality adaptation."""

import unittest

from quality import QualityController


class QualityControllerTests(unittest.TestCase):
    """@brief Exercise congestion, hysteresis, feedback loss, and bounds."""

    def test_fast_backoff_and_slow_recovery(self):
        """@brief Congestion lowers quality immediately, headroom recovers gradually."""
        q = QualityController(75, 20, recovery_frames=3)
        self.assertEqual(q.observe(91, 100, True), 70)
        self.assertEqual(q.observe(69, 100, True), 70)
        self.assertEqual(q.observe(69, 100, True), 70)
        self.assertEqual(q.observe(69, 100, True), 71)
        self.assertEqual(q.observe(70, 100, True), 71)
        self.assertEqual(q.observe(90, 100, True), 71)
        for _ in range(20):
            q.congested()
        self.assertEqual(q.value, 20)
        for _ in range(300):
            q.observe(1, 100, True)
        self.assertEqual(q.value, 75)

    def test_intermittent_pressure_and_silence_reset_headroom(self):
        """@brief Unconfirmed or marginal frames cannot build up recovery credit."""
        q = QualityController(75, 20, recovery_frames=3)
        q.congested()
        q.observe(1, 100, True)
        q.observe(1, 100, True)
        q.observe(1, 100, False)
        self.assertEqual(q.observe(1, 100, True), 70)
        q.observe(70, 100, True)
        self.assertEqual(q.observe(1, 100, True), 70)
        self.assertEqual(q.congested(), 65)

    def test_invalid_parameters(self):
        """@brief Reject invalid limits, frame size, budget and feedback flags."""
        for args in ((0, 1, 1), (75, 76, 1), (96, 1, 1), (75, 20, 0), (True, 1, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                QualityController(*args)
        q = QualityController(75, 20)
        for args in (
            (0, 1, True),
            (1, 0, True),
            (1, 1, 1),
            (True, 1, True),
            (1, float("nan"), True),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                q.observe(*args)


if __name__ == "__main__":
    unittest.main()
