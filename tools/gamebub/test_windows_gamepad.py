"""@brief Regression tests for Xbox ABI, cleanup and ordered input with fake drivers."""

import ctypes
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import windows_gamepad as pad


class GamepadTests(unittest.TestCase):
    """@brief Exercise adapter behavior without installing drivers or injecting presses."""

    def library(self):
        """@brief Return a fake ViGEm library with success defaults and allocated handles."""
        library = MagicMock()
        library.vigem_alloc.return_value = 1
        library.vigem_target_x360_alloc.return_value = 2
        for name in ("connect", "target_add", "target_remove", "target_x360_update"):
            getattr(library, "vigem_" + name).return_value = pad.SUCCESS
        return library

    def test_abi_and_neutral_lifecycle(self):
        """@brief Reports have the expected ABI and never synthesize analog controls."""
        self.assertEqual(ctypes.sizeof(pad.XusbReport), 12)
        library = self.library()
        controller = pad.XboxController(library)
        controller.set_buttons(0x1001)
        report = library.vigem_target_x360_update.call_args.args[2]
        self.assertEqual(
            (
                report.buttons,
                report.lx,
                report.ly,
                report.rx,
                report.ry,
                report.left_trigger,
                report.right_trigger,
            ),
            (0x1001, 0, 0, 0, 0, 0, 0),
        )
        for flags in (-1, True, 0x80, 65536):
            with self.assertRaises(ValueError):
                controller.set_buttons(flags)
        self.assertEqual(controller.close(), ())
        self.assertEqual(controller.close(), ())
        library.vigem_target_remove.assert_called_once_with(1, 2)
        library.vigem_target_free.assert_called_once_with(2)
        library.vigem_disconnect.assert_called_once_with(1)
        library.vigem_free.assert_called_once_with(1)
        with self.assertRaises(RuntimeError):
            controller.set_buttons(0)

    def test_left_stick_and_crouch_report_validation(self):
        """@brief Explicit movement/crouch preserve neutral right stick and triggers."""
        library = self.library()
        controller = pad.XboxController(library)
        controller.set_state(0x40, -32767, 32767)
        report = library.vigem_target_x360_update.call_args.args[2]
        self.assertEqual(
            (
                report.buttons,
                report.lx,
                report.ly,
                report.rx,
                report.ry,
                report.left_trigger,
                report.right_trigger,
            ),
            (0x40, -32767, 32767, 0, 0, 0, 0),
        )
        for x, y in ((True, 0), (0, False), (-32769, 0), (0, 32768), (1.5, 0)):
            with self.assertRaises(ValueError):
                controller.set_state(0, x, y)
        controller.set_state(0, 0, 0, 255)
        report = library.vigem_target_x360_update.call_args.args[2]
        self.assertEqual((report.left_trigger, report.right_trigger), (255, 0))
        for trigger in (-1, 256, True, 0.5):
            with self.assertRaises(ValueError):
                controller.set_state(0, 0, 0, trigger)
        controller.close()

    def test_failed_initialization_cleanup(self):
        """@brief Every failed allocation/connect/attach/update frees earlier resources."""
        for method in (
            "vigem_alloc",
            "vigem_connect",
            "vigem_target_x360_alloc",
            "vigem_target_add",
            "vigem_target_x360_update",
        ):
            with self.subTest(method=method):
                library = self.library()
                getattr(library, method).return_value = 0
                with self.assertRaises(OSError):
                    pad.XboxController(library)
                if method != "vigem_alloc":
                    library.vigem_free.assert_called_once()
                if method in ("vigem_target_add", "vigem_target_x360_update"):
                    library.vigem_target_free.assert_called_once()

    def test_dual_sticks_triggers_and_release(self):
        """@brief Preserve full report field order and reject malformed right-side controls."""
        library = self.library()
        controller = pad.XboxController(library)
        controller.set_state(0x110, -123, 456, 78, -901, 2345, 67)
        report = library.vigem_target_x360_update.call_args.args[2]
        self.assertEqual(
            (
                report.buttons,
                report.lx,
                report.ly,
                report.left_trigger,
                report.rx,
                report.ry,
                report.right_trigger,
            ),
            (0x110, -123, 456, 78, -901, 2345, 67),
        )
        for value in (True, 1.5, -32769, 32768):
            for field in ("right_x", "right_y"):
                with self.assertRaises(ValueError):
                    controller.set_state(0, **{field: value})
        for value in (True, 0.5, -1, 256):
            with self.assertRaises(ValueError):
                controller.set_state(0, right_trigger=value)
        controller.set_buttons(0)
        self.assertEqual(bytes(library.vigem_target_x360_update.call_args.args[2]), bytes(12))
        controller.close()

    def test_cleanup_driver_failure_still_removes_and_frees(self):
        """@brief A failed neutral report or unplug cannot leak the owned handles."""
        library = self.library()
        controller = pad.XboxController(library)
        library.vigem_target_x360_update.return_value = 0
        library.vigem_target_remove.return_value = 0
        self.assertEqual(len(controller.close()), 2)
        library.vigem_free.assert_called_once()

    def test_explicit_dll_path_and_cli(self):
        """@brief Avoid DLL search-path ambiguity and configure all declared ABI signatures."""
        for path in ("relative.dll", Path(tempfile.gettempdir()) / "absent-gamebub.dll"):
            with self.assertRaises(ValueError):
                pad.load_client(path)
        library = self.library()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "client.dll"
            path.touch()
            with patch.object(pad.ctypes, "WinDLL", return_value=library):
                self.assertIs(pad.load_client(path), library)
            self.assertEqual(library.vigem_target_x360_update.argtypes[-1], pad.XusbReport)
            with patch.object(pad, "load_client", return_value=library), patch("builtins.print"):
                pad.main(["--dll", str(path)])
            library.vigem_target_remove.return_value = 0
            with (
                patch.object(pad, "load_client", return_value=library),
                patch("builtins.print"),
                self.assertRaises(OSError),
            ):
                pad.main(["--dll", str(path)])

    def test_command_entrypoint(self):
        """@brief Exercise the real neutral-only probe CLI using fake native symbols."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "client.dll"
            path.touch()
            with (
                patch.object(pad.ctypes, "WinDLL", return_value=self.library()),
                patch("sys.argv", ["windows_gamepad.py", "--dll", str(path)]),
                patch("builtins.print"),
            ):
                runpy.run_path(str(Path(pad.__file__)), run_name="__main__")


class OrderedInputTests(unittest.TestCase):
    """@brief Independently ordered snapshots survive video stalls, reordering and silence."""

    session = bytes(range(16))

    def test_wrap_reorder_duplicate_and_timeout(self):
        """@brief Same-sequence traffic cannot replay a press or postpone neutral release."""
        sink = MagicMock()
        state = pad.OrderedInput(self.session, sink, 10)
        self.assertFalse(state.expire(0))
        self.assertTrue(state.accept(self.session, 0xFFFFFFFF, 1 << 11, 100))
        self.assertFalse(state.accept(self.session, 0xFFFFFFFF, 0, 105))
        self.assertFalse(state.accept(self.session, 0xFFFFFFFE, 0, 106))
        self.assertFalse(state.accept(self.session, 0x7FFFFFFF, 0, 107))
        self.assertFalse(state.accept(bytes(16), 0, 0, 108))
        self.assertFalse(state.expire(109))
        self.assertTrue(state.expire(110))
        self.assertFalse(state.expire(111))
        self.assertFalse(state.accept(self.session, 0xFFFFFFFF, 1 << 11, 112))
        self.assertTrue(state.accept(self.session, 0, 1 << 11, 113))
        self.assertTrue(state.accept(self.session, 1, 1 << 11, 114))
        self.assertTrue(state.accept(self.session, 2, 0, 115))
        state.close()
        state.close()
        self.assertFalse(state.accept(self.session, 3, 0, 116))
        self.assertFalse(state.expire(200))
        self.assertEqual(
            [x.args[0] for x in sink.set_buttons.call_args_list], [0, 0x1000, 0, 0x1000, 0, 0]
        )

    def test_invalid_snapshot_never_updates_liveness(self):
        """@brief Reject malformed session setup, monotonic time, sequence and masks."""
        sink = MagicMock()
        for session in (None, b"", bytes(16), bytes(17)):
            with self.assertRaises(ValueError):
                pad.OrderedInput(session, sink)
        for timeout in (0, -1, True):
            with self.assertRaises(ValueError):
                pad.OrderedInput(self.session, sink, timeout)
        state = pad.OrderedInput(self.session, sink, 10)
        state.accept(self.session, 1, 1 << 11, 100)
        for now in (-1, True, 99):
            with self.assertRaises(ValueError):
                state.expire(now)
        for sequence in (-1, 2**32, True):
            with self.assertRaises(ValueError):
                state.accept(self.session, sequence, 0, 101)
        with self.assertRaises(ValueError):
            state.accept(self.session, 2, 4096, 102)
        self.assertTrue(state.expire(110))

    def test_sink_error_ends_session(self):
        """@brief Driver failures during a press or timeout attempt neutral session shutdown."""
        for expire in (False, True):
            sink = MagicMock()
            state = pad.OrderedInput(self.session, sink, 10)
            if expire:
                state.accept(self.session, 1, 1 << 11, 100)
            sink.set_buttons.side_effect = [OSError("driver fault"), None]
            with self.assertRaises(OSError):
                if expire:
                    state.expire(111)
                else:
                    state.accept(self.session, 1, 1 << 11, 100)
            self.assertTrue(state.closed)
            self.assertEqual(sink.set_buttons.call_args.args, (0,))


if __name__ == "__main__":
    unittest.main()
