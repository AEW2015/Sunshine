"""@brief Real localhost AV sockets with synthetic product audio and fake virtual input."""

import itertools
import queue
import socket
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from audio_codec import BLOCK_SAMPLES, RATE, decode_block, encode_block
from av_protocol import INPUT, NONCE, Packet, decode
from gamepad_backend import GamepadDispatcher
from live_session import run_av
from reference_loopback import ReferencePeer, load_reference
from stream_sender import run as run_video
from windows_audio import test_tone


class LoopbackPeer:
    """@brief Model one fixed-cookie receiver on an ephemeral127.0.0.1 UDP port."""

    def __init__(self):
        """@brief Bind only localhost; retain every independently decoded host packet."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.settimeout(0.003)
        self.address = self.socket.getsockname()
        self.stopped = threading.Event()
        self.done = threading.Event()
        self.packets = []
        self.errors = []
        self.peer = self.nonce = self.flags = None
        self.active = False
        self.sequence = 0
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        """@brief Reply to handshake, emit ordered snapshots and verify STOP at the pinned peer."""
        next_input = 0
        try:
            while not self.done.is_set():
                try:
                    raw, source = self.socket.recvfrom(561)
                except TimeoutError:
                    pass
                else:
                    packet = decode(raw)
                    self.packets.append(packet)
                    if packet.magic == b"MSC1" and packet.kind == 1:
                        self.peer, self.nonce, self.flags = source, packet.session, packet.flags
                        self.socket.sendto(
                            Packet(
                                b"MSR1",
                                1,
                                0x102030405,
                                flags=self.flags,
                                payload=NONCE.pack(self.nonce),
                            ).encode(),
                            source,
                        )
                    elif packet.magic == b"MSC1" and packet.kind == 2:
                        if (
                            source != self.peer
                            or packet.session != 0x102030405
                            or packet.payload != NONCE.pack(self.nonce)
                            or packet.flags != self.flags
                        ):
                            raise AssertionError("START endpoint/nonce/cookie/flags mismatch")
                        self.active = True
                    elif packet.magic == b"MSC1" and packet.kind == 4:
                        if source != self.peer or packet.session != 0x102030405:
                            raise AssertionError("STOP endpoint/cookie mismatch")
                        self.stopped.set()
                        return
                    elif packet.magic == b"MSA1":
                        if packet.session != 0x102030405 or source != self.peer or not self.flags:
                            raise AssertionError("Audio outside negotiated session")
                        decode_block(packet.payload)
                now = time.perf_counter()
                if self.active and now >= next_input:
                    # WoW Up+X, then complete release snapshots, independently sequenced.
                    buttons = 0x280 if self.sequence % 2 else 0
                    self.socket.sendto(
                        Packet(
                            b"MSI1",
                            1,
                            0x102030405,
                            sequence=self.sequence,
                            payload=INPUT.pack(buttons, 0, 0, 0, 0, 0, 5 | self.flags * 2, 99),
                        ).encode(),
                        self.peer,
                    )
                    self.sequence += 1
                    next_input = now + 0.02
        except Exception as error:  # noqa: BLE001 - retained and asserted in the test owner
            self.errors.append(repr(error))

    def __enter__(self):
        """@brief Start the isolated peer thread."""
        self.thread.start()
        return self

    def __exit__(self, *errors):
        """@brief Bound shutdown and close the ephemeral localhost socket."""
        self.done.set()
        self.thread.join(1)
        self.socket.close()


class SyntheticAudio:
    """@brief Pace independently decodable product-rounded blocks without WASAPI."""

    def __init__(self, gain, clock):
        """@brief Encode deterministic stereo PCM using the actual selected IMA encoder."""
        self.clock = clock
        self.block = encode_block(test_tone(BLOCK_SAMPLES, RATE))[0]
        self.blocks = queue.Queue(4)
        self.last_capture_ns = None
        self.error = None
        self.stop = threading.Event()
        self.sequence = self.dropped = 0
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        """@brief Generate a sample-clock stream; every produced block owns a sequence ID."""
        while not self.stop.is_set():
            self.last_capture_ns = self.clock()
            item = (self.sequence, self.last_capture_ns, self.block)
            self.sequence += 1
            try:
                self.blocks.put_nowait(item)
            except queue.Full:
                self.dropped += 1
            self.stop.wait(BLOCK_SAMPLES / RATE)

    def start(self):
        """@brief Start the finite-session-owned synthetic producer."""
        self.thread.start()

    def close(self):
        """@brief Stop synthetic generation and expose its accounting."""
        self.stop.set()
        self.thread.join(1)
        return {
            "shutdown_complete": not self.thread.is_alive(),
            "encoded": self.sequence,
            "queue_drops": self.dropped,
            "queued_unsent": self.blocks.qsize(),
        }


class LoopbackTests(unittest.TestCase):
    """@brief Verify real datagrams, negotiated audio modes, selected profile and release."""

    def test_input_only_survives_concurrent_video_and_silent_video_feedback(self):
        """@brief Real input lease/STOP remains independent of video feedback liveness."""
        repository = Path(__file__).parent / "artifacts/moonbub-30fps-study"
        if not repository.exists():
            self.skipTest("Pinned MoonBub reference repository is not available")
        import tempfile

        reference = load_reference(repository)
        for silence in (False, True):
            with self.subTest(silent_video=silence), tempfile.TemporaryDirectory() as folder:
                peer = ReferencePeer(reference)
                original_socket = peer.socket
                if silence:

                    class QuietReplies:
                        """@brief Drop only video feedback without suppressing AV snapshots."""

                        def __getattr__(self, name, original_socket=original_socket):
                            """@brief Delegate the real localhost receive socket lifecycle."""
                            return getattr(original_socket, name)

                        def sendto(self, raw, endpoint):
                            """@brief Model missing video ACKs after successful ingress."""
                            return len(raw)

                    peer.socket = QuietReplies()
                result, failures = {}, []
                finished = threading.Event()
                options = SimpleNamespace(
                    target="127.0.0.1",
                    port=peer.port,
                    source_port=0,
                    start_frame_id=100,
                    log=Path(folder) / "video.jsonl",
                    clip=None,
                    fps=20,
                    mbps=4,
                    max_age_ms=200,
                    quality=25,
                    min_quality=25,
                    frames=20,
                    packet_timing=True,
                )

                def send_video(
                    options=options, result=result, failures=failures, finished=finished
                ):
                    """@brief Run an actual finite sender in an owned local worker."""
                    try:
                        result["video"] = run_video(
                            options, (Image.new("RGB", (720, 480), (n, 80, 160)) for n in range(20))
                        )
                    except Exception as error:  # noqa: BLE001 - retain worker failures in test owner
                        failures.append(error)
                    finally:
                        finished.set()

                worker = threading.Thread(target=send_video)
                try:
                    with LoopbackPeer() as av_peer:
                        av_options = SimpleNamespace(
                            receiver="127.0.0.1",
                            bind="127.0.0.1",
                            av_port=av_peer.address[1],
                            av_source_port=0,
                            gamepad=False,
                            audio=False,
                            profile="standard",
                            gain=0.75,
                            seconds=3,
                            source_timeout=2,
                        )
                        with patch("live_session.VigemXbox360Backend.create") as gamepad:
                            av_result = run_av(
                                av_options,
                                lambda *a, **kw: None,
                                ready=worker.start,
                                stop_when=finished.is_set,
                            )
                        worker.join(1)
                        self.assertFalse(worker.is_alive())
                        self.assertFalse(failures)
                        self.assertTrue(av_peer.stopped.wait(1))
                        self.assertFalse(av_peer.errors)
                        self.assertGreater(av_result["input_packets"], 20)
                        self.assertEqual(av_result["input_timeouts"], 0)
                        self.assertEqual(av_result["audio_sent"], 0)
                        gamepad.assert_not_called()
                        if silence:
                            self.assertEqual(
                                result["video"]["counts"].get("feedback_accepted", 0), 0
                            )
                        else:
                            self.assertGreater(result["video"]["counts"]["feedback_accepted"], 0)
                finally:
                    worker.join(3) if worker.ident is not None else None
                    peer.close()

    def test_real_localhost_audio_input_and_audio_disabled(self):
        """@brief Both modes complete a1s session; no hardware or physical input is touched."""
        for enabled in (False, True):
            with self.subTest(audio=enabled), LoopbackPeer() as peer:
                args = SimpleNamespace(
                    receiver="127.0.0.1",
                    bind="127.0.0.1",
                    av_port=peer.address[1],
                    av_source_port=0,
                    gamepad=True,
                    profile="wow",
                    audio=enabled,
                    gain=0.75,
                    seconds=1,
                    source_timeout=2,
                )
                backend = MagicMock()
                backend.close.return_value = ()
                dispatcher = GamepadDispatcher(backend, profile="wow")
                with (
                    patch("live_session.VigemXbox360Backend.create"),
                    patch("live_session.GamepadDispatcher", return_value=dispatcher),
                ):
                    result = run_av(args, lambda *a, **kw: None, audio_factory=SyntheticAudio)
                self.assertTrue(peer.stopped.wait(1))
                self.assertFalse(peer.errors)
                self.assertEqual(result["input_timeouts"], 0)
                self.assertEqual(result["invalid_packets"], 0)
                self.assertGreaterEqual(result["input_packets"], 10)
                self.assertTrue(
                    any(
                        call.args == (0, 0, 32767, 0, 0, 10000, 0)
                        for call in backend.set_state.call_args_list
                    )
                )
                self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0, 0, 0, 0))
                backend.close.assert_called_once()
                audio = [packet for packet in peer.packets if packet.magic == b"MSA1"]
                self.assertEqual(len(audio), result["audio_sent"])
                if enabled:
                    self.assertGreater(len(audio), 20)
                    self.assertTrue(
                        all(b.sequence > a.sequence for a, b in itertools.pairwise(audio))
                    )
                    self.assertTrue(result["audio_worker"]["shutdown_complete"])
                else:
                    self.assertEqual(audio, [])
                controls = [
                    p.sequence for p in peer.packets if p.magic == b"MSC1" and p.kind in (3, 4)
                ]
                self.assertTrue(all(b > a for a, b in itertools.pairwise(controls)))


if __name__ == "__main__":
    unittest.main()
