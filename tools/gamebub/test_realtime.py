"""@brief Regression tests for bounded media and safe logical button state."""

import concurrent.futures
import unittest

from realtime import AudioBlock, ButtonState, MediaBuffers, VideoFrame, gamepad_buttons


class MediaBufferTests(unittest.TestCase):
    """@brief Exercise bounded queues, stale drops, discontinuities, and locking."""

    def setUp(self):
        """@brief Use a controllable monotonic clock and deliberately small limits."""
        self.now = 100
        self.media = MediaBuffers(8, 8, 2, 10, 20, clock=lambda: self.now)

    def test_limits_and_payloads_are_validated(self):
        """@brief Reject invalid bounds, malformed payloads, and impossible timestamps."""
        for limits in ((0, 8, 2, 10, 20), (8, True, 2, 10, 20), (8, 8, -1, 10, 20)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                MediaBuffers(*limits)
        for payload, captured in (
            (b"", 100),
            (b"123456789", 100),
            (bytearray(b"x"), 100),
            (b"x", -1),
            (b"x", 101),
            (b"x", True),
        ):
            with self.subTest(payload=payload, captured=captured), self.assertRaises(ValueError):
                self.media.put_video(VideoFrame(payload, captured))
        with self.assertRaises(ValueError):
            self.media.put_audio(AudioBlock(b"x", 100, 0))

    def test_video_replaces_oldest_and_never_rewinds(self):
        """@brief Keep one latest frame and reject older captures even after a take."""
        self.assertTrue(self.media.put_video(VideoFrame(b"first", 90)))
        self.assertTrue(self.media.put_video(VideoFrame(b"new", 100)))
        self.assertFalse(self.media.put_video(VideoFrame(b"older", 99)))
        self.assertEqual(self.media.snapshot()["video_frames"], 1)
        self.assertEqual(self.media.take_video().payload, b"new")
        self.assertFalse(self.media.put_video(VideoFrame(b"old", 99)))
        self.assertIsNone(self.media.take_video())
        self.assertEqual(
            self.media.snapshot()["drops"], {"video_replaced": 1, "video_out_of_order": 2}
        )

    def test_stale_video_is_discarded_at_dequeue(self):
        """@brief A frame at the age limit is usable; older frames cannot accumulate."""
        self.media.put_video(VideoFrame(b"x", 90))
        self.assertIsNotNone(self.media.take_video())
        self.media.put_video(VideoFrame(b"y", 90))
        self.now = 101
        self.assertIsNone(self.media.take_video())
        self.assertEqual(self.media.snapshot()["drops"]["video_stale"], 1)

    def test_audio_block_count_overflow_signals_one_discontinuity(self):
        """@brief Drop the oldest audio on overflow and mark the next returned block."""
        for value in (b"a", b"b", b"c"):
            self.media.put_audio(AudioBlock(value, 100, 1))
        self.assertEqual(self.media.snapshot()["audio_blocks"], 2)
        first = self.media.take_audio()
        self.assertEqual((first.payload, first.discontinuity), (b"b", True))
        second = self.media.take_audio()
        self.assertEqual((second.payload, second.discontinuity), (b"c", False))
        self.assertIsNone(self.media.take_audio())
        self.assertEqual(self.media.snapshot()["drops"]["audio_overflow"], 1)

    def test_audio_byte_overflow_and_order_validation(self):
        """@brief Enforce total bytes independently and reject reordered audio."""
        self.media.put_audio(AudioBlock(b"12345", 99, 1))
        self.media.put_audio(AudioBlock(b"abcdef", 100, 1))
        with self.assertRaises(ValueError):
            self.media.put_audio(AudioBlock(b"x", 99, 1))
        self.assertEqual(self.media.snapshot()["audio_bytes"], 6)
        self.assertTrue(self.media.take_audio().discontinuity)

    def test_stale_audio_drop_latches_until_a_new_block_arrives(self):
        """@brief A gap remains visible even when every queued block has expired."""
        self.media.put_audio(AudioBlock(b"a", 80, 1))
        self.now = 101
        self.assertIsNone(self.media.take_audio())
        self.media.put_audio(AudioBlock(b"b", 101, 1))
        self.assertTrue(self.media.take_audio().discontinuity)
        self.assertEqual(self.media.snapshot()["drops"]["audio_stale"], 1)

    def test_existing_discontinuity_and_reset(self):
        """@brief Reset clears bounded data, resets ordering, and marks the next audio gap."""
        self.media.put_video(VideoFrame(b"v", 100))
        self.media.put_audio(AudioBlock(b"a", 100, 1))
        self.media.reset()
        self.assertEqual(self.media.snapshot()["video_frames"], 0)
        self.assertEqual(self.media.snapshot()["audio_bytes"], 0)
        self.media.put_video(VideoFrame(b"v", 90))
        self.media.put_audio(AudioBlock(b"b", 90, 1, discontinuity=True))
        self.assertTrue(self.media.take_audio().discontinuity)
        self.media.put_audio(AudioBlock(b"c", 90, 1, discontinuity=True))
        self.assertTrue(self.media.take_audio().discontinuity)

    def test_concurrent_producers_keep_memory_bounded(self):
        """@brief Concurrent producers cannot exceed a frame or audio queue limits."""

        def producer(index):
            """@brief Submit same-timestamp blocks from independent worker threads."""
            for _ in range(200):
                self.media.put_video(VideoFrame(bytes([index]), 100))
                self.media.put_audio(AudioBlock(bytes([index]), 100, 1))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(producer, range(4)))
        snapshot = self.media.snapshot()
        self.assertEqual(snapshot["video_frames"], 1)
        self.assertEqual(snapshot["audio_blocks"], 2)
        self.assertEqual(snapshot["audio_bytes"], 2)
        self.assertEqual(snapshot["drops"]["video_replaced"], 799)
        self.assertEqual(snapshot["drops"]["audio_overflow"], 798)


class ButtonStateTests(unittest.TestCase):
    """@brief Verify input deltas and fail-safe release without injecting OS input."""

    def test_configuration_and_input_validation(self):
        """@brief Reject missing or unknown button names and invalid local sequences."""
        for allowed in ([], [""], [1]):
            with self.assertRaises(ValueError):
                ButtonState(allowed)
        buttons = ButtonState(["A", "B"])
        for sequence in (-1, True):
            with self.assertRaises(ValueError):
                buttons.apply(sequence, [])
        with self.assertRaises(ValueError):
            buttons.apply(0, ["unknown"])

    def test_gamebub_gameplay_buttons_map_to_sunshine_flags(self):
        """@brief Each physical button maps to the intended digital gamepad flag."""
        cases = {
            "up": 0x0001,
            "down": 0x0002,
            "left": 0x0004,
            "right": 0x0008,
            "start": 0x0010,
            "select": 0x0020,
            "l": 0x0100,
            "r": 0x0200,
            "a": 0x1000,
            "b": 0x2000,
            "x": 0x4000,
            "y": 0x8000,
        }
        for name, flag in cases.items():
            with self.subTest(name=name):
                self.assertEqual(gamepad_buttons([name]), flag)
        self.assertEqual(gamepad_buttons(cases), 0xF33F)
        self.assertEqual(gamepad_buttons(["a", "a"]), 0x1000)
        self.assertEqual(gamepad_buttons([]), 0)
        for name in ("home", "power", "volume_up", "A"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                gamepad_buttons([name])

    def test_snapshots_reordering_and_disconnect_release(self):
        """@brief Ignore old states, emit deltas, and release all held buttons on disconnect."""
        buttons = ButtonState(["a", "b"])
        self.assertEqual(buttons.apply(0, ["a"]), (frozenset(["a"]), frozenset()))
        self.assertEqual(buttons.apply(2, ["b"]), (frozenset(["b"]), frozenset(["a"])))
        self.assertEqual(gamepad_buttons(buttons.pressed), 0x2000)
        self.assertEqual(buttons.apply(1, ["a"]), (frozenset(), frozenset()))
        self.assertEqual(buttons.apply(2, ["a"]), (frozenset(), frozenset()))
        self.assertEqual(buttons.disconnect(), frozenset(["b"]))
        self.assertEqual(gamepad_buttons(buttons.pressed), 0)
        self.assertEqual(buttons.disconnect(), frozenset())
        self.assertEqual(buttons.apply(0, ["a", "b"]), (frozenset(["a", "b"]), frozenset()))


if __name__ == "__main__":
    unittest.main()
