"""@brief Callback queue, product encoder and shutdown tests without audio devices."""

import queue
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import live_audio


class AudioTests(unittest.TestCase):
    """@brief Exercise queue ownership, late callbacks and explicit native cleanup limits."""

    def audio(self):
        """@brief Return a prepared worker with fake native constants only."""
        backend = SimpleNamespace(paContinue=1, paAbort=2, paComplete=3, paInt16=8)
        audio = live_audio.LoopbackAudio(backend=backend, clock=lambda: 100)
        audio.channels = 2
        return audio

    def test_callback_bounds_error_and_late_callback(self):
        """@brief A full PCM queue or bad capture fails visibly; shutdown rejects late PCM."""
        audio = self.audio()
        raw = bytes(40)
        for _ in range(8):
            self.assertEqual(audio.callback(raw, 10, None, 0), (None, 1))
        self.assertEqual(audio.last_capture_ns, 100)
        self.assertEqual(audio.counts["captured_frames"], 80)
        self.assertEqual(audio.callback(raw, 10, None, 0), (None, 2))
        self.assertEqual(audio.counts["pcm_drops"], 1)
        self.assertEqual(audio.counts["pcm_dropped_frames"], 10)
        final = audio.close()
        self.assertEqual(final["queued_pcm_blocks"], 8)
        self.assertEqual(final["queued_pcm_bytes"], 320)
        self.assertEqual(final["queued_pcm_frames"], 80)
        audio = self.audio()
        self.assertEqual(audio.callback(raw, 10, None, 4), (None, 2))
        self.assertEqual(audio.counts["capture_errors"], 1)
        audio = self.audio()
        self.assertEqual(audio.callback(b"x", 10, None, 0), (None, 2))
        audio.stop.set()
        self.assertEqual(audio.callback(raw, 10, None, 0), (None, 3))
        self.assertEqual(audio.counts["late_callbacks"], 1)

    def test_sequences_eviction_and_shutdown(self):
        """@brief Sequence IDs advance before queue eviction and never reset on drop."""
        audio = self.audio()
        with patch.object(live_audio, "validate_block"):
            for sequence in range(6):
                audio.publish(b"block", sequence)
        self.assertEqual(audio.counts["encoded"], 6)
        self.assertEqual(audio.counts["queue_drops"], 2)
        self.assertEqual([audio.blocks.get_nowait()[0] for _ in range(4)], [2, 3, 4, 5])
        self.assertTrue(audio.close()["shutdown_complete"])
        audio.thread = MagicMock()
        audio.thread.is_alive.return_value = True
        self.assertFalse(audio.close(timeout=0.1)["shutdown_complete"])
        audio.thread.join.assert_called_once_with(0.1)
        with self.assertRaises(RuntimeError):
            audio.start()
        with self.assertRaises(ValueError):
            live_audio.LoopbackAudio(2)
        with patch.object(live_audio.threading, "Thread") as thread:
            self.audio().start()
            thread.return_value.start.assert_called_once()

    def test_worker_product_encoding_and_tail(self):
        """@brief The worker uses AudioEncoder rather than FFmpeg ADPCM and reports its tail."""
        audio = self.audio()
        manager = MagicMock()
        manager.get_default_wasapi_loopback.return_value = {
            "maxInputChannels": 8,
            "defaultSampleRate": 48000,
            "isLoopbackDevice": True,
            "name": "fake",
            "index": 1,
        }
        audio.backend.PyAudio = MagicMock()
        audio.backend.PyAudio.return_value.__enter__.return_value = manager
        raw = (100).to_bytes(2, "little", signed=True) * 960

        def consume(timeout):
            audio.stop.set()
            return raw, 10

        audio.pcm.get = consume
        encoder = MagicMock()
        encoder.push.return_value = [b"encoded"]
        encoder.finish.return_value = ([b"tail"], 7)
        with (
            patch.object(live_audio, "AudioEncoder", return_value=encoder),
            patch.object(live_audio, "validate_block"),
        ):
            audio._run()
        self.assertIsNone(audio.error)
        self.assertEqual(audio.counts["encoded"], 1)
        self.assertEqual(audio.counts["unsent_tail_blocks"], 1)
        self.assertEqual(audio.counts["tail_frames"], 7)
        self.assertEqual(audio.counts["encoded_source_frames"], 480)
        self.assertEqual(int.from_bytes(encoder.push.call_args.args[0][:2], "little"), 75)
        self.assertEqual(audio.info["channels"], 2)

    def test_worker_error_is_propagated(self):
        """@brief Unsupported devices and unexpected native exceptions are explicit errors."""
        audio = self.audio()
        audio.backend.PyAudio = MagicMock(side_effect=OSError("unavailable"))
        audio._run()
        self.assertIn("unavailable", audio.error)
        self.assertTrue(audio.stop.is_set())

    def test_empty_queue_races_missing_backend_and_bad_device(self):
        """@brief Consumer races and inactive callbacks do not block shutdown."""
        audio = self.audio()
        audio.blocks = MagicMock()
        audio.blocks.full.return_value = True
        audio.blocks.get_nowait.side_effect = queue.Empty
        with patch.object(live_audio, "validate_block"):
            audio.publish(b"block", 1)
        self.assertEqual(audio.counts["queue_drops"], 0)
        backend = self.audio().backend
        backend.PyAudio = MagicMock(side_effect=OSError("absent"))
        audio = live_audio.LoopbackAudio()
        with patch.dict(sys.modules, {"pyaudiowpatch": backend}):
            audio._run()
        self.assertIn("absent", audio.error)
        audio = self.audio()
        manager = MagicMock()
        manager.get_default_wasapi_loopback.return_value = {
            "maxInputChannels": 0,
            "defaultSampleRate": 48000,
            "isLoopbackDevice": False,
        }
        audio.backend.PyAudio = MagicMock()
        audio.backend.PyAudio.return_value.__enter__.return_value = manager
        audio._run()
        self.assertIn("Expected default", audio.error)
        audio = self.audio()
        manager.get_default_wasapi_loopback.return_value = {
            "maxInputChannels": 2,
            "defaultSampleRate": 48000,
            "isLoopbackDevice": True,
            "name": "fake",
            "index": 0,
        }
        audio.backend.PyAudio = MagicMock()
        audio.backend.PyAudio.return_value.__enter__.return_value = manager

        def inactive(timeout):
            audio.stop.set()
            raise queue.Empty

        audio.pcm.get = inactive
        encoder = MagicMock()
        encoder.finish.return_value = ([], 0)
        with patch.object(live_audio, "AudioEncoder", return_value=encoder):
            audio._run()
        self.assertIsNone(audio.error)


if __name__ == "__main__":
    unittest.main()
