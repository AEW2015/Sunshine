"""@brief Opt-in AV v1 virtual Xbox output using the built, pinned ViGEm client.

No driver installation or input injection occurs on import. The reference AV
client owns MSI1 sequence/session validation and its500ms release lease.
"""

import math
import os
import time
from pathlib import Path

from msv1 import gamebub_buttons
from realtime import gamepad_buttons
from windows_gamepad import XboxController, load_client

PROFILES = ("standard", "elden-ring", "mass-effect", "wow")
DIAGONAL_AXIS = 23169  # Floor(32767/sqrt(2)): diagonal magnitude never exceeds cardinal magnitude.
WOW_CAMERA_START = 10000  # Gentle initial radial deflection; game bindings set the final feel.
WOW_CAMERA_RAMP_NS = 2_000_000_000


def elden_ring_state(pressed):
    """@brief Map D-pad movement and operator-selected Elden Ring action bindings.

    @param pressed Validated logical Game Bub buttons.
    @return Xbox flags, normalized left-stick X/Y and left-trigger intensity.
    """
    x = int("right" in pressed) - int("left" in pressed)
    y = int("up" in pressed) - int("down" in pressed)
    magnitude = DIAGONAL_AXIS if x and y else 32767
    remaining = pressed - {"up", "down", "left", "right", "a", "b", "x", "y"}
    flags = gamepad_buttons(remaining)
    for source, target in (("a", 0x0200), ("b", 0x0040), ("y", 0x1000)):
        if source in pressed:
            flags |= target
    return flags, x * magnitude, y * magnitude, 255 if "x" in pressed else 0


def mass_effect_state(pressed):
    """@brief Map movement, face-button aim, shoulder triggers and weapon wheel.

    @param pressed Validated logical Game Bub buttons.
    @return Flags, left X/Y, left trigger, right X/Y and right trigger.
    """
    lx = int("right" in pressed) - int("left" in pressed)
    ly = int("up" in pressed) - int("down" in pressed)
    rx = int("a" in pressed) - int("y" in pressed)
    ry = int("x" in pressed) - int("b" in pressed)
    movement = DIAGONAL_AXIS if lx and ly else 32767
    aim = DIAGONAL_AXIS if rx and ry else 32767
    flags = (0x0010 if "start" in pressed else 0) | (0x0100 if "select" in pressed else 0)
    return (
        flags,
        lx * movement,
        ly * movement,
        255 if "l" in pressed else 0,
        rx * aim,
        ry * aim,
        255 if "r" in pressed else 0,
    )


def wow_state(pressed):
    """@brief Map D-pad movement and face-button camera to independent Xbox sticks.

    @param pressed Validated Game Bub buttons; X up, Y left, A right, B down.
    @return Flags, left X/Y, neutral left trigger, right X/Y, neutral right trigger.
    """
    _, left_x, left_y, _, right_x, right_y, _ = mass_effect_state(pressed)
    flags = gamepad_buttons(pressed & {"l", "r", "start", "select"})
    return flags, left_x, left_y, 0, right_x, right_y, 0


class RampedCamera:
    """@brief Convert held camera directions into a gradual, time-based right-stick deflection."""

    def __init__(self, start=WOW_CAMERA_START, ramp_ns=WOW_CAMERA_RAMP_NS, gap_ns=250_000_000):
        """@brief Configure bounded stick speed and a fresh slow start after input gaps.

        @param start Initial radial stick magnitude1..32767.
        @param ramp_ns Hold duration to reach full deflection using a quadratic ease-in.
        @param gap_ns Input silence that resets acceleration on the next valid snapshot.
        """
        if type(start) is not int or not 1 <= start <= 32767:
            raise ValueError("Invalid camera starting magnitude")
        if any(type(value) is not int or value <= 0 for value in (ramp_ns, gap_ns)):
            raise ValueError("Camera ramp and gap durations must be positive nanoseconds")
        self.start, self.ramp_ns, self.gap_ns = start, ramp_ns, gap_ns
        self.reset()

    def reset(self):
        """@brief Clear hold history on neutral release, lease expiry or shutdown."""
        self.direction = (0, 0)
        self.started_ns = self.last_ns = None

    def sample(self, x, y, now_ns):
        """@brief Sample a complete direction snapshot without packet-count-dependent acceleration.

        @param x Horizontal direction -1/0/1; positive means right.
        @param y Vertical direction -1/0/1; positive means up.
        @param now_ns Nonnegative host monotonic timestamp.
        @return Signed16 X/Y stick coordinates, with normalized diagonal magnitude.
        """
        if any(type(value) is not int or value not in (-1, 0, 1) for value in (x, y)):
            raise ValueError("Invalid camera direction")
        if (
            type(now_ns) is not int
            or now_ns < 0
            or (self.last_ns is not None and now_ns < self.last_ns)
        ):
            raise ValueError("Invalid camera monotonic timestamp")
        direction = (x, y)
        gap = self.last_ns is not None and now_ns - self.last_ns >= self.gap_ns
        self.last_ns = now_ns
        if direction == (0, 0):
            self.direction, self.started_ns = direction, None
            return 0, 0
        if direction != self.direction or gap:
            self.direction, self.started_ns = direction, now_ns
        elapsed = min(now_ns - self.started_ns, self.ramp_ns)
        magnitude = self.start + (32767 - self.start) * elapsed * elapsed // (
            self.ramp_ns * self.ramp_ns
        )
        axis = math.isqrt(magnitude * magnitude // 2) if x and y else magnitude
        return x * axis, y * axis


class VigemXbox360Backend:
    """@brief Factory compatible with the published AV v1 opt-in gamepad client."""

    @staticmethod
    def create(dll=None):
        """@brief Attach one neutral Xbox360 target; fail clearly if the driver is absent.

        @param dll Optional absolute DLL path; otherwise use env override or local build.
        @return Owned XboxController; caller must close it on every exit.
        """
        default = (
            Path(__file__).resolve().parents[2] / "cmake-build-gamebub-vigem/libViGEmClient.dll"
        )
        path = Path(dll if dll is not None else os.environ.get("GAMEBUB_VIGEM_DLL", default))
        return XboxController(load_client(path))


class GamepadDispatcher:
    """@brief Map validated twelve-button snapshots to an owned virtual Xbox controller."""

    def __init__(self, backend, profile=None, clock=None):
        """@brief Start neutral; close the device if initial publication fails.

        @param backend Owned virtual controller output.
        @param profile Explicit mapping or the existing environment-selected profile.
        @param clock Optional monotonic nanosecond clock for reproducible ramp checks.
        """
        self.profile = (
            profile
            if profile is not None
            else os.environ.get("GAMEBUB_CONTROLLER_PROFILE", "standard")
        )
        if self.profile not in PROFILES:
            backend.close()
            raise ValueError("Unknown controller profile")
        self.backend, self.closed = backend, False
        self.clock = time.monotonic_ns if clock is None else clock
        self.camera = RampedCamera() if self.profile == "wow" else None
        self.neutral()

    def _set(
        self, flags, left_x=0, left_y=0, left_trigger=0, right_x=0, right_y=0, right_trigger=0
    ):
        """@brief Publish a report; unplug on driver failure to prevent held controls."""
        if self.closed:
            raise RuntimeError("Gamepad dispatcher is closed")
        try:
            if self.profile in ("mass-effect", "wow"):
                self.backend.set_state(
                    flags, left_x, left_y, left_trigger, right_x, right_y, right_trigger
                )
            elif self.profile == "elden-ring":
                self.backend.set_state(flags, left_x, left_y, left_trigger)
            else:
                self.backend.set_buttons(flags)
        except OSError:
            self.close()
            raise

    def apply(self, mask):
        """@brief Apply a complete Game Bub mask using the explicitly selected profile."""
        if self.closed:
            raise RuntimeError("Gamepad dispatcher is closed")
        pressed = gamebub_buttons(mask)
        if self.profile == "mass-effect":
            self._set(*mass_effect_state(pressed))
        elif self.profile == "wow":
            flags, lx, ly, lt, rx, ry, rt = wow_state(pressed)
            rx, ry = self.camera.sample((rx > 0) - (rx < 0), (ry > 0) - (ry < 0), self.clock())
            self._set(flags, lx, ly, lt, rx, ry, rt)
        elif self.profile == "elden-ring":
            self._set(*elden_ring_state(pressed))
        else:
            self._set(gamepad_buttons(pressed))

    def neutral(self):
        """@brief Release all buttons on input lease expiry or session shutdown."""
        if self.camera is not None:
            self.camera.reset()
        self._set(0)

    def close(self):
        """@brief Neutralize and unplug once, reporting any driver cleanup failure."""
        if not self.closed:
            self.closed = True
            if self.camera is not None:
                self.camera.reset()
            errors = self.backend.close()
            if errors:
                raise OSError("Gamepad cleanup failed: " + "; ".join(errors))
