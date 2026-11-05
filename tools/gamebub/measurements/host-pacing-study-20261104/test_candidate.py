"""@brief Test laboratory wait boundaries without sleeping or contacting hardware."""
import unittest
from candidate import bounded_wait

class WaitTests(unittest.TestCase):
    """@brief Preserve deadlines and long-wait liveness delegation."""
    def test_short_wait_never_calls_blocking_sleep(self):
        """@brief Short waits advance to the deadline through the bounded tail."""
        times=iter((0,.0001,.0003,.0005))
        bounded_wait(.0005,lambda seconds:self.fail('Unexpected sleep'),lambda:next(times))

    def test_long_packet_wait_sleeps_then_finishes_tail(self):
        """@brief Leave at most one millisecond of requested busy wait."""
        calls=[]
        times=iter((0,.0015,.002,.002128))
        bounded_wait(.002128,calls.append,lambda:next(times))
        self.assertAlmostEqual(calls[0],.001128)

    def test_oversleep_does_not_add_spin_delay(self):
        """@brief Already expired deadlines return after the blocking sleep."""
        times=iter((0,.004))
        bounded_wait(.002,lambda seconds:None,lambda:next(times))

    def test_long_guarded_wait_keeps_original_liveness_check(self):
        """@brief Delegate long pacing waits unchanged to the existing guarded sleeper."""
        calls=[]
        bounded_wait(.051,calls.append,lambda:self.fail('Unexpected spin clock'))
        self.assertEqual(calls,[.051])

    def test_guarded_sleeper_exception_propagates(self):
        """@brief Feedback-liveness errors must still abort the wait."""
        def failure(seconds):
            """@brief Simulate the existing feedback guard's timeout."""
            raise TimeoutError('Feedback expired')
        with self.assertRaisesRegex(TimeoutError,'Feedback expired'):
            bounded_wait(.002,failure,lambda:0)

    def test_zero_wait_returns_without_sleep(self):
        """@brief Zero wait does not require a deadline extension."""
        bounded_wait(0,lambda seconds:self.fail('Unexpected sleep'),lambda:1)

if __name__=='__main__':
    unittest.main()
