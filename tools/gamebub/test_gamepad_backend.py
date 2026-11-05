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
        dispatcher = output.GamepadDispatcher(backend, profile="wow", clock=lambda: 0)
        for mask in range(4096):
            axes = []
            for index, (right, left, up, down) in enumerate(
                ((0x10, 0x20, 0x80, 0x40), (0x800, 0x100, 0x200, 0x400))
            ):
                x = int(bool(mask & right)) - int(bool(mask & left))
                y = int(bool(mask & up)) - int(bool(mask & down))
                maximum = 32767 if index == 0 else output.WOW_CAMERA_START
                scale = int((maximum * maximum // 2) ** 0.5) if x and y else maximum
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

    def test_wow_hold_accelerates_without_changing_movement_or_buttons(self):
        """@brief Hold a camera key over real elapsed time while movement/menu masks change."""
        backend = MagicMock()
        backend.close.return_value = ()
        now = [0]
        dispatcher = output.GamepadDispatcher(backend, profile="wow", clock=lambda: now[0])
        speeds = []
        for tick in range(21):
            now[0] = tick * 100_000_000
            movement, button = (0x80, 0x08) if tick % 2 else (0x10, 0x02)
            dispatcher.apply(0x800 | movement | button)
            flags, lx, ly, lt, rx, ry, rt = backend.set_state.call_args.args
            expected = (0x100, 0, 32767) if tick % 2 else (0x10, 32767, 0)
            self.assertEqual((flags, lx, ly), expected)
            self.assertEqual((lt, ry, rt), (0, 0, 0))
            speeds.append(rx)
        self.assertEqual(speeds[0], 10000)
        self.assertEqual(speeds[-1], 32767)
        self.assertEqual(speeds, sorted(speeds))
        self.assertLess(speeds[10], (speeds[0] + speeds[-1]) // 2)
        dispatcher.neutral()
        self.assertEqual(backend.set_state.call_args.args, (0, 0, 0, 0, 0, 0, 0))
        now[0] += 20_000_000
        dispatcher.apply(0x800)
        self.assertEqual(backend.set_state.call_args.args[4], 10000)
        dispatcher.close()
        self.assertIsNone(dispatcher.camera.started_ns)
        with self.assertRaises(RuntimeError):
            dispatcher.apply(0x800)

    def test_wow_reverse_and_opposition_restart_slow_camera(self):
        """@brief Direction changes/release cancel old acceleration instead of snapping full tilt."""
        backend = MagicMock()
        backend.close.return_value = ()
        now = [0]
        dispatcher = output.GamepadDispatcher(backend, profile="wow", clock=lambda: now[0])
        for tick in range(21):
            now[0] = tick * 100_000_000
            dispatcher.apply(0x800)
        now[0] += 20_000_000
        dispatcher.apply(0x100)
        self.assertEqual(backend.set_state.call_args.args[4:6], (-10000, 0))
        now[0] += 20_000_000
        dispatcher.apply(0x900)
        self.assertEqual(backend.set_state.call_args.args[4:6], (0, 0))
        now[0] += 20_000_000
        dispatcher.apply(0x200)
        self.assertEqual(backend.set_state.call_args.args[4:6], (0, 10000))
        backend.set_state.side_effect = OSError("driver fault")
        with self.assertRaises(OSError):
            dispatcher.apply(0x800)
        self.assertIsNone(dispatcher.camera.started_ns)
        backend.close.assert_called_once()

    def test_packet_frequency_does_not_change_elapsed_time_acceleration(self):
        """@brief Different valid snapshot cadences produce the same one-second speed."""
        results = []
        for period in (10_000_000, 20_000_000, 50_000_000, 100_000_000):
            camera = output.RampedCamera()
            for now in range(0, 1_000_000_001, period):
                current = camera.sample(1, 0, now)
            results.append(current)
        self.assertTrue(all(value == results[0] for value in results))
        self.assertGreater(results[0][0], 10000)
        self.assertLess(results[0][0], 32767)

    def test_diagonal_speed_is_normalized_and_bounded(self):
        """@brief Diagonals remain radially bounded at slow, intermediate and full speed."""
        diagonal = output.RampedCamera(gap_ns=10_000_000_000)
        cardinal = output.RampedCamera(gap_ns=10_000_000_000)
        for now in (0, 500_000_000, 1_000_000_000, 2_000_000_000, 5_000_000_000):
            x, y = diagonal.sample(-1, 1, now)
            magnitude = cardinal.sample(1, 0, now)[0]
            self.assertEqual(-x, y)
            self.assertLessEqual(x * x + y * y, magnitude * magnitude)
            self.assertLessEqual(abs(x), 23169)
        self.assertEqual((x, y), (-23169, 23169))

    def test_gaps_reset_without_catch_up_and_reset_forgets_hold(self):
        """@brief A 250ms gap restarts gently and explicit neutral resets all history."""
        camera = output.RampedCamera()
        self.assertEqual(camera.sample(1, 0, 0), (10000, 0))
        self.assertGreater(camera.sample(1, 0, 200_000_000)[0], 10000)
        self.assertEqual(camera.sample(1, 0, 450_000_000), (10000, 0))
        self.assertEqual(camera.sample(0, 0, 460_000_000), (0, 0))
        self.assertEqual(camera.sample(1, 0, 470_000_000), (10000, 0))
        camera.reset()
        self.assertEqual(camera.sample(0, 0, 0), (0, 0))
        self.assertEqual(camera.sample(1, 1, 1), (7071, 7071))

    def test_invalid_parameters_directions_and_clock_leave_history_unchanged(self):
        """@brief Reject bad dimensions/timestamps before corrupting a held direction."""
        for start in (0, 32768, True, 1.0):
            with self.assertRaises(ValueError):
                output.RampedCamera(start=start)
        for value in (0, -1, True, 1.0):
            for key in ("ramp_ns", "gap_ns"):
                with self.assertRaises(ValueError):
                    output.RampedCamera(**{key: value})
        camera = output.RampedCamera(start=32767)
        self.assertEqual(camera.sample(1, 0, 1), (32767, 0))
        state = (camera.direction, camera.started_ns, camera.last_ns)
        for x, y, now in (
            (2, 0, 2),
            (True, 0, 2),
            (0, 0.0, 2),
            (1, 0, -1),
            (1, 0, 0),
            (1, 0, True),
            (1, 0, 1.0),
        ):
            with self.assertRaises(ValueError):
                camera.sample(x, y, now)
            self.assertEqual((camera.direction, camera.started_ns, camera.last_ns), state)

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
