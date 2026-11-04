"""@brief Regression checks for the opt-in live AV Xbox adapter with fake drivers."""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import gamepad_backend as output


class GamepadBackendTests(unittest.TestCase):
    """@brief Verify mapping, cleanup, failure release and explicit DLL selection."""

    def test_mass_effect_all_masks_and_release(self):
        """@brief Independently verify all4096 movement/aim/action combinations and neutral."""
        from msv1 import gamebub_buttons

        backend = MagicMock()
        backend.close.return_value = ()
        dispatcher = output.GamepadDispatcher(backend, profile="mass-effect")
        for mask in range(4096):
            pressed = gamebub_buttons(mask)
            axes = []
            for positive_x, negative_x, positive_y, negative_y in (
                ("right", "left", "up", "down"),
                ("a", "y", "x", "b"),
            ):
                x = (positive_x in pressed) - (negative_x in pressed)
                y = (positive_y in pressed) - (negative_y in pressed)
                scale = 23169 if x != 0 and y != 0 else 32767
                axes.extend((x * scale, y * scale))
                self.assertLessEqual((x * scale) ** 2 + (y * scale) ** 2, 32767**2)
            flags = (0x10 if mask & 2 else 0) | (0x100 if mask & 1 else 0)
            expected = (flags, *axes[:2], 255 if mask & 8 else 0, *axes[2:], 255 if mask & 4 else 0)
            dispatcher.apply(mask)
            self.assertEqual(backend.set_state.call_args.args, expected, hex(mask))
        dispatcher.neutral()
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0, 0, 0, 0))
        backend.set_buttons.assert_not_called()
        backend.set_state.side_effect = OSError("driver fault")
        with self.assertRaises(OSError):
            dispatcher.apply(0xFFF)
        backend.close.assert_called_once()

    def test_mapping_neutral_and_close(self):
        """@brief Face buttons, shoulders and D-pad map to digital Xbox flags."""
        backend = MagicMock()
        backend.close.return_value = ()
        dispatcher = output.GamepadDispatcher(backend)
        dispatcher.apply(0xFFF)
        self.assertEqual(backend.set_buttons.call_args.args, (0xF33F,))
        dispatcher.apply(0x880)
        self.assertEqual(backend.set_buttons.call_args.args, (0x1001,))
        dispatcher.neutral()
        self.assertEqual(backend.set_buttons.call_args.args, (0,))
        with self.assertRaises(ValueError):
            dispatcher.apply(0x1000)
        dispatcher.close()
        dispatcher.close()
        backend.close.assert_called_once()
        with self.assertRaises(RuntimeError):
            dispatcher.neutral()

    def test_wow_sticks_buttons_and_failure_release(self):
        """@brief Verify all4096 WoW masks, neutral triggers and failure cleanup."""
        backend = MagicMock()
        backend.close.return_value = ()
        dispatcher = output.GamepadDispatcher(backend, profile="wow")
        for mask in range(4096):
            axes = []
            for right, left, up, down in ((0x10, 0x20, 0x80, 0x40), (0x800, 0x100, 0x200, 0x400)):
                x = int(bool(mask & right)) - int(bool(mask & left))
                y = int(bool(mask & up)) - int(bool(mask & down))
                scale = 23169 if x and y else 32767
                axes.extend((x * scale, y * scale))
                self.assertLessEqual((x * scale) ** 2 + (y * scale) ** 2, 32767**2)
            flags = sum(
                flag for bit, flag in ((1, 0x20), (2, 0x10), (4, 0x200), (8, 0x100)) if mask & bit
            )
            dispatcher.apply(mask)
            self.assertEqual(
                backend.set_state.call_args.args, (flags, *axes[:2], 0, *axes[2:], 0), hex(mask)
            )
        dispatcher.neutral()
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0, 0, 0, 0))
        backend.set_buttons.assert_not_called()
        backend.set_state.side_effect = OSError("driver fault")
        with self.assertRaises(OSError):
            dispatcher.apply(0xFFF)
        backend.close.assert_called_once()

    def test_driver_failure_and_cleanup_errors(self):
        """@brief Failed initial/report/neutral publication removes the owned device."""
        for operation in ("initial", "press", "neutral"):
            backend = MagicMock()
            backend.close.return_value = ()
            if operation == "initial":
                backend.set_buttons.side_effect = OSError("driver fault")
                with self.assertRaises(OSError):
                    output.GamepadDispatcher(backend)
            else:
                dispatcher = output.GamepadDispatcher(backend)
                backend.set_buttons.side_effect = OSError("driver fault")
                with self.assertRaises(OSError):
                    if operation == "press":
                        dispatcher.apply(0x800)
                    else:
                        dispatcher.neutral()
            backend.close.assert_called_once()
        backend = MagicMock()
        dispatcher = output.GamepadDispatcher(backend)
        backend.close.return_value = ("unplug failed",)
        with self.assertRaisesRegex(OSError, "unplug failed"):
            dispatcher.close()

    def test_factory_selects_explicit_env_or_default_library(self):
        """@brief Use the pinned build path unless an explicit DLL selection overrides it."""
        default = (
            Path(output.__file__).resolve().parents[2]
            / "cmake-build-gamebub-vigem/libViGEmClient.dll"
        )
        for argument, environment, expected in (
            (None, {}, default),
            (None, {"GAMEBUB_VIGEM_DLL": "C:/test/env.dll"}, Path("C:/test/env.dll")),
            (
                "C:/test/explicit.dll",
                {"GAMEBUB_VIGEM_DLL": "ignored"},
                Path("C:/test/explicit.dll"),
            ),
        ):
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(output, "load_client", return_value="library") as load,
                patch.object(output, "XboxController", return_value="target") as create,
            ):
                self.assertEqual(output.VigemXbox360Backend.create(argument), "target")
                load.assert_called_once_with(expected)
                create.assert_called_once_with("library")
        with (
            patch.object(output, "load_client", side_effect=OSError("missing driver")),
            self.assertRaises(OSError),
        ):
            output.VigemXbox360Backend.create()

    def test_elden_ring_movement_faces_and_neutral(self):
        """@brief Normalize diagonals, cancel opposing directions and apply requested actions."""
        backend = MagicMock()
        backend.close.return_value = ()
        dispatcher = output.GamepadDispatcher(backend, profile="elden-ring")
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0))
        for mask, x, y in (
            (0x00, 0, 0),
            (0x80, 0, 32767),
            (0x40, 0, -32767),
            (0x20, -32767, 0),
            (0x10, 32767, 0),
            (0x90, 23169, 23169),
            (0xA0, -23169, 23169),
            (0x50, 23169, -23169),
            (0x60, -23169, -23169),
            (0x30, 0, 0),
            (0xC0, 0, 0),
            (0xF0, 0, 0),
            (0xD0, 32767, 0),
            (0xE0, -32767, 0),
            (0xB0, 0, 32767),
            (0x70, 0, -32767),
        ):
            dispatcher.apply(mask)
            self.assertEqual(backend.set_state.call_args.args, (0, x, y, 0))
            self.assertLessEqual(x * x + y * y, 32767 * 32767)
        for mask, expected in ((0x800, 0x200), (0x400, 0x40), (0x100, 0x1000)):
            dispatcher.apply(mask | 0x80)
            self.assertEqual(backend.set_state.call_args.args, (expected, 0, 32767, 0))
        dispatcher.apply(0x280)
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 32767, 255))
        dispatcher.apply(0xFFF)
        self.assertEqual(backend.set_state.call_args.args, (0x1370, 0, 0, 255))
        dispatcher.neutral()
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0))
        backend.set_buttons.assert_not_called()
        dispatcher.close()

    def test_elden_ring_profile_validation_and_driver_failure(self):
        """@brief Reject unknown profiles and close the analog output device on failure."""
        backend = MagicMock()
        backend.close.return_value = ()
        with (
            patch.dict(os.environ, {"GAMEBUB_CONTROLLER_PROFILE": "invalid"}),
            self.assertRaises(ValueError),
        ):
            output.GamepadDispatcher(backend)
        backend.close.assert_called_once()
        backend.reset_mock()
        with patch.dict(os.environ, {"GAMEBUB_CONTROLLER_PROFILE": "elden-ring"}):
            dispatcher = output.GamepadDispatcher(backend)
        backend.set_state.side_effect = OSError("driver fault")
        with self.assertRaises(OSError):
            dispatcher.apply(0x80)
        backend.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
