"""@brief Track experimental MSF1 controller snapshots without injecting input.

MSF1 has no input sequence number: multiple snapshots for the same video frame
cannot be ordered reliably. This adapter is not suitable for real input injection
until a session and ordered input protocol are agreed with the receiver team.
"""

from msv1 import gamebub_buttons
from realtime import gamepad_buttons


class ControllerTracker:
    """@brief Translate receiver snapshots and produce a neutral state on silence."""

    def __init__(self, timeout_ns=500_000_000):
        """@brief Configure a positive monotonic timeout for held button states."""
        if type(timeout_ns) is not int or timeout_ns <= 0:
            raise ValueError("Controller timeout must be a positive integer")
        self.timeout_ns = timeout_ns
        self.frame_id = self.capture_us = self.last_ns = None
        self.buttons = 0
        self.timed_out = False

    def accept(self, frame_id, capture_us, mask, now_ns):
        """@brief Accept a current complete snapshot and return changes to gamepad flags.

        @param frame_id Wrapping unsigned 32-bit receiver video frame ID.
        @param capture_us Capture timestamp that identifies equal frame IDs.
        @param mask Receiver's complete 12-bit Game Bub button mask.
        @param now_ns Local monotonic nanoseconds at receipt.
        @return New Windows-style mask when changed, otherwise None.
        @throws ValueError If identifiers, mask or monotonic time are invalid.
        """
        if (
            type(frame_id) is not int
            or not 0 <= frame_id <= 0xFFFFFFFF
            or type(capture_us) is not int
            or not 0 <= capture_us <= 0xFFFFFFFFFFFFFFFF
            or type(now_ns) is not int
            or now_ns < 0
            or (self.last_ns is not None and now_ns < self.last_ns)
        ):
            raise ValueError("Invalid controller snapshot metadata")
        flags = gamepad_buttons(gamebub_buttons(mask))
        if self.frame_id is not None:
            delta = (frame_id - self.frame_id) & 0xFFFFFFFF
            if delta == 0:
                if capture_us != self.capture_us or self.timed_out:
                    return None
            elif delta >= 0x80000000:
                return None
        self.frame_id, self.capture_us, self.last_ns = frame_id, capture_us, now_ns
        self.timed_out = False
        if flags == self.buttons:
            return None
        self.buttons = flags
        return flags

    def expire(self, now_ns):
        """@brief Neutralize held buttons on feedback timeout; require a newer frame.

        @param now_ns Local monotonic nanoseconds.
        @return Zero if a held state was released, otherwise None.
        """
        if (
            type(now_ns) is not int
            or now_ns < 0
            or (self.last_ns is not None and now_ns < self.last_ns)
        ):
            raise ValueError("Invalid monotonic time")
        if self.last_ns is None or now_ns - self.last_ns <= self.timeout_ns or self.timed_out:
            return None
        self.timed_out = True
        if not self.buttons:
            return None
        self.buttons = 0
        return 0

    def disconnect(self):
        """@brief Reset session state and report a neutral state if buttons were held."""
        held = self.buttons
        self.frame_id = self.capture_us = self.last_ns = None
        self.buttons = 0
        self.timed_out = False
        return 0 if held else None
