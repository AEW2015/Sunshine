"""@brief Opt-in AV v1 virtual Xbox output using the built, pinned ViGEm client.

No driver installation or input injection occurs on import. The reference AV
client owns MSI1 sequence/session validation and its500ms release lease.
"""

import os
from pathlib import Path

from msv1 import gamebub_buttons
from realtime import gamepad_buttons
from windows_gamepad import XboxController, load_client

PROFILES = ("standard", "elden-ring", "mass-effect", "wow")
DIAGONAL_AXIS = 23169  # Floor(32767/sqrt(2)): diagonal magnitude never exceeds cardinal magnitude.


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

    def __init__(self, backend, profile=None):
        """@brief Start neutral; close the device if initial publication fails."""
        self.profile = (
            profile
            if profile is not None
            else os.environ.get("GAMEBUB_CONTROLLER_PROFILE", "standard")
        )
        if self.profile not in PROFILES:
            backend.close()
            raise ValueError("Unknown controller profile")
        self.backend, self.closed = backend, False
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
        pressed = gamebub_buttons(mask)
        if self.profile == "mass-effect":
            self._set(*mass_effect_state(pressed))
        elif self.profile == "wow":
            self._set(*wow_state(pressed))
        elif self.profile == "elden-ring":
            self._set(*elden_ring_state(pressed))
        else:
            self._set(gamepad_buttons(pressed))

    def neutral(self):
        """@brief Release all buttons on input lease expiry or session shutdown."""
        self._set(0)

    def close(self):
        """@brief Neutralize and unplug once, reporting any driver cleanup failure."""
        if not self.closed:
            self.closed = True
            errors = self.backend.close()
            if errors:
                raise OSError("Gamepad cleanup failed: " + "; ".join(errors))
