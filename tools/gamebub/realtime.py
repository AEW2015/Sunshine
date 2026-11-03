"""@brief Transport-independent bounded media and button state for Game Bub.

This module does not capture, encode, send, receive, or inject input. Callers
must agree codec, wire format and Windows button mapping with the receiver first.
"""

from collections import Counter, deque
from dataclasses import dataclass, replace
from threading import Lock
from time import monotonic_ns

# Logical Game Bub button names mapped to Sunshine's platform gamepad flags.
# This is an internal adapter mapping, not an ESP32 packet format.
GAMEBUB_GAMEPAD_FLAGS = {
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


def gamepad_buttons(pressed):
    """@brief Translate a complete Game Bub snapshot to Sunshine gamepad flags.

    @param pressed Iterable of the twelve lowercase Game Bub gameplay button names.
    @return Sunshine's internal digital gamepad button mask; empty means neutral.
    @throws ValueError If any name is not a Game Bub gameplay button.
    """
    state = frozenset(pressed)
    if not state <= GAMEBUB_GAMEPAD_FLAGS.keys():
        raise ValueError("Unknown Game Bub gameplay button")
    return sum(GAMEBUB_GAMEPAD_FLAGS[name] for name in state)


@dataclass(frozen=True)
class VideoFrame:
    """@brief One complete video frame and its host monotonic capture timestamp."""

    payload: bytes
    captured_ns: int


@dataclass(frozen=True)
class AudioBlock:
    """@brief An encoded audio block with host timing and a local discontinuity flag."""

    payload: bytes
    captured_ns: int
    duration_ns: int
    discontinuity: bool = False


class MediaBuffers:
    """@brief Thread-safe latest-video slot and bounded FIFO for audio blocks.

    All timestamps use the same host monotonic clock. Audio drops are signaled
    on the next returned block so the eventual sender can reset/recover according
    to the receiver agreement. This is not a transport or synchronization protocol.
    """

    def __init__(
        self, video_bytes, audio_bytes, audio_blocks, video_age_ns, audio_age_ns, clock=monotonic_ns
    ):
        """@brief Configure memory and age limits supplied by the eventual caller.

        @param video_bytes Maximum bytes in the one pending video frame.
        @param audio_bytes Maximum total bytes in queued audio blocks.
        @param audio_blocks Maximum number of queued audio blocks.
        @param video_age_ns Maximum capture age when a video frame is taken.
        @param audio_age_ns Maximum capture age when an audio block is taken.
        @param clock Host monotonic nanosecond clock; injectable for tests.
        """
        limits = (video_bytes, audio_bytes, audio_blocks, video_age_ns, audio_age_ns)
        if any(type(value) is not int or value <= 0 for value in limits):
            raise ValueError("Buffer limits must be positive integers")
        self.video_bytes, self.audio_bytes, self.audio_blocks = limits[:3]
        self.video_age_ns, self.audio_age_ns = limits[3:]
        self.clock = clock
        self.lock = Lock()
        self.video = None
        self.last_video_ns = -1
        self.audio = deque()
        self.last_audio_ns = -1
        self.audio_size = 0
        self.audio_discontinuity = False
        self.counts = Counter()

    def _validate(self, payload, captured_ns, maximum):
        """@brief Validate complete payload size and its host monotonic timestamp."""
        if not isinstance(payload, bytes) or not 0 < len(payload) <= maximum:
            raise ValueError("Payload must be nonempty bytes within its configured limit")
        if type(captured_ns) is not int or captured_ns < 0 or captured_ns > self.clock():
            raise ValueError("Capture timestamp must use the host monotonic clock")

    def put_video(self, frame):
        """@brief Replace the waiting video frame with the latest complete frame.

        @param frame Immutable frame with a bounded payload and host timestamp.
        @return False for an older frame, otherwise True after accepting it.
        """
        self._validate(frame.payload, frame.captured_ns, self.video_bytes)
        with self.lock:
            if frame.captured_ns < self.last_video_ns:
                self.counts["video_out_of_order"] += 1
                return False
            if self.video is not None:
                self.counts["video_replaced"] += 1
            self.video = frame
            self.last_video_ns = frame.captured_ns
            return True

    def take_video(self):
        """@brief Take the latest frame, discarding it when its age exceeds the bound.

        @return Latest eligible frame or None when empty or stale.
        """
        with self.lock:
            frame, self.video = self.video, None
            if frame is not None and self.clock() - frame.captured_ns > self.video_age_ns:
                self.counts["video_stale"] += 1
                return None
            return frame

    def put_audio(self, block):
        """@brief Queue audio, evicting the oldest blocks when either limit is full.

        @param block Complete encoded audio block; its codec remains undecided.
        """
        self._validate(block.payload, block.captured_ns, self.audio_bytes)
        if type(block.duration_ns) is not int or block.duration_ns <= 0:
            raise ValueError("Audio duration must be a positive integer")
        with self.lock:
            if block.captured_ns < self.last_audio_ns:
                raise ValueError("Audio blocks must be queued in capture order")
            while (
                len(self.audio) >= self.audio_blocks
                or self.audio_size + len(block.payload) > self.audio_bytes
            ):
                self._drop_audio("audio_overflow")
            self.audio.append(block)
            self.audio_size += len(block.payload)
            self.last_audio_ns = block.captured_ns

    def _drop_audio(self, reason):
        """@brief Remove the oldest block under the lock and record a discontinuity."""
        self.audio_size -= len(self.audio.popleft().payload)
        self.counts[reason] += 1
        self.audio_discontinuity = True

    def take_audio(self):
        """@brief Take the oldest nonstale block and report any preceding drops.

        @return Eligible block or None when no nonstale audio is queued.
        """
        with self.lock:
            now = self.clock()
            while self.audio and now - self.audio[0].captured_ns > self.audio_age_ns:
                self._drop_audio("audio_stale")
            if not self.audio:
                return None
            block = self.audio.popleft()
            self.audio_size -= len(block.payload)
            result = replace(block, discontinuity=block.discontinuity or self.audio_discontinuity)
            self.audio_discontinuity = False
            return result

    def reset(self):
        """@brief Clear pending media and force a discontinuity on the next audio block."""
        with self.lock:
            self.video = None
            self.last_video_ns = -1
            self.audio.clear()
            self.last_audio_ns = -1
            self.audio_size = 0
            self.audio_discontinuity = True

    def snapshot(self):
        """@brief Return a consistent copy of queue occupancy and drop counters.

        @return Dictionary with bounded queue sizes and cumulative counters.
        """
        with self.lock:
            return {
                "video_frames": int(self.video is not None),
                "audio_blocks": len(self.audio),
                "audio_bytes": self.audio_size,
                "drops": dict(self.counts),
            }


class ButtonState:
    """@brief Track logical button snapshots and release all on session disconnect."""

    def __init__(self, allowed):
        """@brief Create an empty state from an explicitly supplied logical button set.

        @param allowed Nonempty iterable of nonempty button-name strings.
        """
        self.allowed = frozenset(allowed)
        if not self.allowed or any(not isinstance(name, str) or not name for name in self.allowed):
            raise ValueError("A nonempty set of button names is required")
        self.lock = Lock()
        self.sequence = -1
        self.pressed = frozenset()

    def apply(self, sequence, pressed):
        """@brief Apply a newer complete state snapshot and return changed buttons.

        @param sequence Local session sequence, strictly increasing and nonnegative.
        @param pressed Iterable of allowed logical names in the complete snapshot.
        @return Pair of newly pressed and released frozensets; old snapshots are ignored.
        """
        if type(sequence) is not int or sequence < 0:
            raise ValueError("Sequence must be a nonnegative integer")
        state = frozenset(pressed)
        if not state <= self.allowed:
            raise ValueError("Unknown button")
        with self.lock:
            if sequence <= self.sequence:
                return frozenset(), frozenset()
            changes = state - self.pressed, self.pressed - state
            self.sequence, self.pressed = sequence, state
            return changes

    def disconnect(self):
        """@brief Reset the session and return buttons the input adapter must release.

        @return Previously pressed buttons, cleared atomically.
        """
        with self.lock:
            released, self.pressed, self.sequence = self.pressed, frozenset(), -1
            return released
