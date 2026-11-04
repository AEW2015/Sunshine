"""@brief Test reference integrity and opt-in input-only launch without real devices."""

import hashlib
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gamepad_client as client


class GamepadClientTests(unittest.TestCase):
    """@brief Never send packets or install a driver in launcher regressions."""

    def test_pinned_download_cache_and_modified_source(self):
        """@brief Fetch reviewed bytes once; reject corrupt downloads or user-modified cache."""
        data = b"reviewed reference source"
        digest = hashlib.sha256(data).hexdigest()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(client, "REFERENCES", {"av_client.py": digest}),
            patch.object(client.urllib.request, "urlopen") as fetch,
        ):
            fetch.return_value.__enter__.return_value.read.return_value = data
            path = client.prepare_reference(directory)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(client.prepare_reference(directory), path)
            fetch.assert_called_once()
            path.write_bytes(b"local changes")
            with self.assertRaises(ValueError):
                client.prepare_reference(directory)
        for bad in (b"wrong digest", bytes(1024 * 1024 + 1)):
            with (
                tempfile.TemporaryDirectory() as directory,
                patch.object(client, "REFERENCES", {"av_client.py": digest}),
                patch.object(client.urllib.request, "urlopen") as fetch,
            ):
                fetch.return_value.__enter__.return_value.read.return_value = bad
                with self.assertRaises(ValueError):
                    client.prepare_reference(directory)

    def test_explicit_gamepad_and_default_observe_launch(self):
        """@brief Audio/video flags are never forwarded; injection is explicitly selected."""
        with (
            patch.object(client, "prepare_reference", return_value=Path("C:/test/av_client.py")),
            patch.object(
                client.subprocess, "run", return_value=SimpleNamespace(returncode=0)
            ) as launch,
        ):
            self.assertEqual(client.main([]), 0)
            self.assertNotIn("--gamepad", launch.call_args.args[0])
            self.assertNotIn("--tone", launch.call_args.args[0])
            self.assertNotIn("--loopback", launch.call_args.args[0])
            self.assertEqual(
                launch.call_args.kwargs["env"]["GAMEBUB_CONTROLLER_PROFILE"], "standard"
            )
            self.assertEqual(
                client.main(
                    [
                        "--gamepad",
                        "--seconds",
                        "30",
                        "--profile",
                        "elden-ring",
                        "--dll",
                        "C:/test/driver.dll",
                        "--log",
                        "test.jsonl",
                    ]
                ),
                0,
            )
            self.assertIn("--gamepad", launch.call_args.args[0])
            self.assertEqual(
                launch.call_args.kwargs["env"]["GAMEBUB_CONTROLLER_PROFILE"], "elden-ring"
            )
            self.assertEqual(
                launch.call_args.kwargs["env"]["GAMEBUB_VIGEM_DLL"], str(Path("C:/test/driver.dll"))
            )
            self.assertEqual(client.main(["--gamepad", "--profile", "mass-effect"]), 0)
            self.assertEqual(
                launch.call_args.kwargs["env"]["GAMEBUB_CONTROLLER_PROFILE"], "mass-effect"
            )
            self.assertEqual(client.main(["--gamepad", "--profile", "wow"]), 0)
            self.assertEqual(launch.call_args.kwargs["env"]["GAMEBUB_CONTROLLER_PROFILE"], "wow")
            launch.side_effect = KeyboardInterrupt
            self.assertEqual(client.main([]), 130)

    def test_validation_and_entrypoint(self):
        """@brief Invalid durations/relative DLL paths fail before launching the client."""
        for args in (
            ["--seconds", "0"],
            ["--seconds", "nan"],
            ["--seconds", "7201"],
            ["--dll", "relative.dll"],
            ["--profile", "invalid"],
        ):
            with self.assertRaises(SystemExit), patch("sys.stderr"):
                client.main(args)
        with (
            patch("sys.argv", ["gamepad_client.py", "--seconds", "0"]),
            patch("sys.stderr"),
            self.assertRaises(SystemExit) as stopped,
        ):
            runpy.run_path(client.__file__, run_name="__main__")
        self.assertEqual(stopped.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
