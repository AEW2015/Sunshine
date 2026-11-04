"""@brief Explicit-path ViGEm Xbox controller and transport-independent ordered input.

This module installs no driver, injects no MSF1 input and chooses no packet layout.
"""

import argparse
import ctypes
import json
from pathlib import Path

from msv1 import gamebub_buttons
from realtime import gamepad_buttons

SUCCESS = 0x20000000
BUTTON_FLAGS = 0xF37F  # Digital controls plus left-stick click for explicit game profiles.


class XusbReport(ctypes.Structure):
    """@brief ViGEm XUSB_REPORT ABI with explicit buttons, sticks and triggers."""

    _fields_ = [
        ("buttons", ctypes.c_uint16),
        ("left_trigger", ctypes.c_uint8),
        ("right_trigger", ctypes.c_uint8),
        ("lx", ctypes.c_int16),
        ("ly", ctypes.c_int16),
        ("rx", ctypes.c_int16),
        ("ry", ctypes.c_int16),
    ]


def load_client(path):
    """@brief Load an explicitly located ViGEm client DLL and declare its ABI.

    @param path Existing absolute DLL path supplied by the operator.
    @return Loaded library with ctypes argument and return types.
    """
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("Supply an existing absolute ViGEm client DLL path")
    library = ctypes.WinDLL(str(path))
    pointer = ctypes.c_void_p
    signatures = {
        "vigem_alloc": ([], pointer),
        "vigem_free": ([pointer], None),
        "vigem_connect": ([pointer], ctypes.c_uint32),
        "vigem_disconnect": ([pointer], None),
        "vigem_target_x360_alloc": ([], pointer),
        "vigem_target_free": ([pointer], None),
        "vigem_target_add": ([pointer, pointer], ctypes.c_uint32),
        "vigem_target_remove": ([pointer, pointer], ctypes.c_uint32),
        "vigem_target_x360_update": ([pointer, pointer, XusbReport], ctypes.c_uint32),
    }
    for name, (args, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes, function.restype = args, result
    return library


class XboxController:
    """@brief Own one neutral-by-default virtual Xbox360 controller with cleanup."""

    def __init__(self, library):
        """@brief Connect using a declared ViGEm ABI; clean up failed initialization."""
        self.library = library
        self.client = self.target = None
        self.connected = self.attached = False
        try:
            self.client = library.vigem_alloc()
            if not self.client:
                raise OSError("ViGEm client allocation failed")
            self._check(library.vigem_connect(self.client), "connect (driver required)")
            self.connected = True
            self.target = library.vigem_target_x360_alloc()
            if not self.target:
                raise OSError("ViGEm target allocation failed")
            self._check(library.vigem_target_add(self.client, self.target), "attach")
            self.attached = True
            self.set_buttons(0)
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _check(status, operation):
        """@brief Raise a diagnostic containing the exact failing ViGEm status."""
        if status != SUCCESS:
            raise OSError(f"ViGEm {operation} failed: 0x{status:08x}")

    def set_buttons(self, flags):
        """@brief Publish supported digital flags with neutral sticks and triggers."""
        self.set_state(flags, 0, 0)

    def set_state(
        self, flags, left_x=0, left_y=0, left_trigger=0, right_x=0, right_y=0, right_trigger=0
    ):
        """@brief Publish a complete report; unspecified axes and triggers stay neutral.

        @param flags Supported Xbox button flags, including left-stick click.
        @param left_x Signed16 horizontal stick coordinate; positive means right.
        @param left_y Signed16 vertical stick coordinate; positive means up.
        @param left_trigger Left trigger intensity0..255.
        @param right_x Signed16 horizontal aim coordinate; positive means right.
        @param right_y Signed16 vertical aim coordinate; positive means up.
        @param right_trigger Right trigger intensity0..255.
        """
        if type(flags) is not int or flags < 0 or flags & ~BUTTON_FLAGS:
            raise ValueError("Unsupported digital Xbox flags")
        if any(
            type(axis) is not int or not -32768 <= axis <= 32767
            for axis in (left_x, left_y, right_x, right_y)
        ):
            raise ValueError("Invalid stick coordinate")
        if any(
            type(trigger) is not int or not 0 <= trigger <= 255
            for trigger in (left_trigger, right_trigger)
        ):
            raise ValueError("Invalid trigger intensity")
        if not self.attached:
            raise RuntimeError("Controller is not attached")
        report = XusbReport(flags, left_trigger, right_trigger, left_x, left_y, right_x, right_y)
        self._check(
            self.library.vigem_target_x360_update(self.client, self.target, report),
            "update",
        )

    def close(self):
        """@brief Attempt neutral release then unplug/free even if the driver rejects it.

        @return Tuple of cleanup errors; normal cleanup returns an empty tuple.
        """
        errors = []
        if self.attached:
            for operation, call in (
                (
                    "neutral",
                    lambda: self.library.vigem_target_x360_update(
                        self.client, self.target, XusbReport()
                    ),
                ),
                ("remove", lambda: self.library.vigem_target_remove(self.client, self.target)),
            ):
                try:
                    self._check(call(), operation)
                except OSError as error:
                    errors.append(str(error))
            self.attached = False
        if self.target:
            self.library.vigem_target_free(self.target)
            self.target = None
        if self.connected:
            self.library.vigem_disconnect(self.client)
            self.connected = False
        if self.client:
            self.library.vigem_free(self.client)
            self.client = None
        return tuple(errors)


class OrderedInput:
    """@brief Enforce a fixed session, wrapping input sequence and silence release.

    This is a local contract adapter, not a proposed network encoding. The caller
    validates peer/session establishment before supplying complete snapshots.
    """

    def __init__(self, session, sink, timeout_ns=250_000_000):
        """@brief Start neutral with a nonzero 128-bit session and positive timeout."""
        if not isinstance(session, bytes) or len(session) != 16 or not any(session):
            raise ValueError("Expected a nonzero 16-byte session")
        if type(timeout_ns) is not int or timeout_ns <= 0:
            raise ValueError("Expected a positive input timeout")
        self.session, self.sink, self.timeout_ns = session, sink, timeout_ns
        self.sequence = self.last_ns = None
        self.buttons = 0
        self.closed = False
        sink.set_buttons(0)

    def _time(self, now_ns):
        """@brief Reject invalid/backward host monotonic timestamps."""
        if (
            type(now_ns) is not int
            or now_ns < 0
            or (self.last_ns is not None and now_ns < self.last_ns)
        ):
            raise ValueError("Invalid input monotonic timestamp")

    def accept(self, session, sequence, mask, now_ns):
        """@brief Apply a newer complete button snapshot from the established session.

        @return True for a fresh snapshot, false for wrong-session/stale/closed input.
        """
        self._time(now_ns)
        if type(sequence) is not int or not 0 <= sequence <= 0xFFFFFFFF:
            raise ValueError("Invalid input sequence")
        flags = gamepad_buttons(gamebub_buttons(mask))
        if self.closed or session != self.session:
            return False
        if self.sequence is not None:
            delta = (sequence - self.sequence) & 0xFFFFFFFF
            if not 0 < delta < 0x80000000:
                return False
        try:
            if flags != self.buttons:
                self.sink.set_buttons(flags)
        except OSError:
            self.close()
            raise
        self.sequence, self.last_ns, self.buttons = sequence, now_ns, flags
        return True

    def expire(self, now_ns):
        """@brief Neutralize once after silence; stale sequences cannot refresh liveness."""
        self._time(now_ns)
        if self.closed or self.last_ns is None or now_ns - self.last_ns < self.timeout_ns:
            return False
        if not self.buttons:
            return False
        try:
            self.sink.set_buttons(0)
        except OSError:
            self.close()
            raise
        self.buttons = 0
        return True

    def close(self):
        """@brief End a session with a neutral report; backend owns device removal."""
        if not self.closed:
            self.closed = True
            self.buttons = 0
            self.sink.set_buttons(0)


def main(argv=None):
    """@brief Probe neutral virtual-controller attachment without sending presses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    args = parser.parse_args(argv)
    controller = XboxController(load_client(args.dll))
    errors = controller.close()
    print(json.dumps({"attached_and_removed": True, "cleanup_errors": errors}))
    if errors:
        raise OSError("Virtual-controller cleanup reported an error")


if __name__ == "__main__":
    main()
