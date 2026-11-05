"""@brief Reproducible launcher tests never capture, inject or contact hardware."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import session_launcher as launcher


class LauncherTests(unittest.TestCase):
    """@brief Validate opt-in modes, provenance, finite children and failure logs."""

    def args(self, root, extra=()):
        """@brief Parse a finite default video run in a fresh evidence directory."""
        return launcher.parser().parse_args(
            [
                "--receiver",
                "127.0.0.1",
                "--bind",
                "127.0.0.1",
                "--start-frame-id",
                "100",
                "--output",
                str(root / "new"),
                "--video",
                *extra,
            ]
        )

    def test_dry_run_manifest_no_devices_network_or_process(self):
        """@brief Dry-run records every media setting and source hash without side effects."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(
                Path(directory), ["--audio", "--gamepad", "--profile", "wow", "--dry-run"]
            )
            with (
                patch.object(launcher, "run_av") as av,
                patch.object(launcher, "VideoProcess") as video,
            ):
                result = launcher.run(args)
            self.assertTrue(result["dry_run"])
            av.assert_not_called()
            video.assert_not_called()
            manifest = json.loads((args.output / "manifest.json").read_text())
            self.assertEqual(manifest["profile"], "wow")
            self.assertEqual(manifest["canvas"], [720, 480])
            self.assertIn("--packet-timing", result["video_command"])
            command = result["video_command"]
            self.assertEqual(command[command.index("--bind") + 1], "127.0.0.1")
            with self.assertRaises(FileExistsError):
                launcher.run(args)

    def test_validation_before_files(self):
        """@brief Reject bad modes, bounds and nonfinite values before any resources open."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for extra in (
                ["--seconds", "nan"],
                ["--seconds", "0"],
                ["--gain", "2"],
                ["--fps", "31"],
                ["--quality", "0"],
                ["--mbps", "0"],
                ["--deadline-ms", "0"],
                ["--source-timeout", "0"],
                ["--start-frame-id", "-1"],
                ["--start-frame-id", "4294967295"],
                ["--seconds", "7200", "--fps", "30"],
                ["--video-port", "0"],
                ["--av-source-port", "65536"],
                ["--av-source-port", "4", "--video-source-port", "4"],
                ["--pacing-spin-us", "-1"],
                ["--pacing-wait", "hybrid", "--pacing-spin-us", "1001"],
                ["--pacing-wait", "sleep", "--pacing-spin-us", "400"],
                ["--capture-interface", "adapter"],
                ["--clip-selection", "native"],
            ):
                with self.subTest(extra=extra), self.assertRaises(ValueError):
                    launcher.run(self.args(root, extra))
            args = self.args(root)
            args.video = False
            with self.assertRaises(ValueError):
                launcher.run(args)
            self.assertFalse(args.output.exists())

    def test_explicit_hybrid_tail_forwarded_to_video(self):
        """@brief Preserve the selected bounded tail through the production child command."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(
                Path(directory), ["--pacing-wait", "hybrid", "--pacing-spin-us", "400", "--dry-run"]
            )
            result = launcher.run(args)
            command = result["video_command"]
            self.assertEqual(command[command.index("--pacing-spin-us") + 1], "400")

    def test_owned_video_cleanup_normal_timeout_and_kill(self):
        """@brief Bound termination to the spawned process object; record forced shutdown."""
        for waits, forced in (
            ([0], False),
            ([subprocess.TimeoutExpired("video", 1), 2], True),
            (
                [subprocess.TimeoutExpired("video", 1), subprocess.TimeoutExpired("video", 2), 3],
                True,
            ),
        ):
            with tempfile.TemporaryDirectory() as directory:
                args = self.args(Path(directory))
                args.output.mkdir()
                process = MagicMock()
                process.wait.side_effect = waits
                with patch.object(launcher.subprocess, "Popen", return_value=process):
                    child = launcher.VideoProcess(args)
                result = child.close()
                self.assertEqual(result["forced_stop"], forced)
                self.assertTrue(child.stdout.closed)
                if len(waits) == 3:
                    process.kill.assert_called_once()
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory))
            args.output.mkdir()
            with (
                patch.object(launcher.subprocess, "Popen", side_effect=OSError("spawn")),
                self.assertRaises(OSError),
            ):
                launcher.VideoProcess(args)

    def test_combined_start_after_active_and_result(self):
        """@brief Video begins through AV-ready callback; worker shutdown remains explicit."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory), ["--audio"])
            child = MagicMock()
            child.process.pid = 123
            child.close.return_value = {"exit_code": 0, "forced_stop": False}

            def av(options, event, ready, health, stop_when):
                event("active")
                ready()
                child.process.poll.return_value = None
                health()
                self.assertEqual(options.seconds, args.seconds + 5)
                self.assertFalse(stop_when())
                child.process.poll.return_value = 0
                self.assertTrue(stop_when())
                return {"audio_worker": {"shutdown_complete": True}}

            with (
                patch.object(launcher, "run_av", side_effect=av),
                patch.object(launcher, "VideoProcess", return_value=child),
            ):
                result = launcher.run(args)
            child.close.assert_called_once_with(grace=5)
            self.assertEqual(result["logging"]["dropped"], 0)
            self.assertFalse(result["end_to_end_verified"])
            self.assertTrue((args.output / "session-summary.json").exists())

    def test_failure_retains_summary_and_stops_owned_video(self):
        """@brief Capture/session errors preserve logs and do not leave an owned sender running."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory), ["--audio"])
            child = MagicMock()
            child.process.pid = 123
            child.close.return_value = {"exit_code": 2, "forced_stop": True}

            def failed(options, event, ready, health, stop_when):
                ready()
                child.process.poll.return_value = 2
                health()
                raise RuntimeError("capture failed")

            with (
                patch.object(launcher, "run_av", side_effect=failed),
                patch.object(launcher, "VideoProcess", return_value=child),
                self.assertRaises(RuntimeError),
            ):
                launcher.run(args)
            child.close.assert_called_once_with(grace=0)
            result = json.loads((args.output / "session-summary.json").read_text())
            self.assertIn("Owned video sender exited", result["error"])

    def test_av_summary_survives_session_and_child_cleanup_failure(self):
        """@brief Retain final AV evidence even when the owner subsequently raises."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory), ["--av-input"])
            child = MagicMock()
            child.process.pid = 123
            child.close.side_effect = OSError("child cleanup")

            def failed(options, event, ready, health, stop_when):
                """@brief Publish the real owner's failure-summary event before propagating."""
                ready()
                event("av_summary", input_packets=7, stop_sent=True)
                raise RuntimeError("session failure")

            with (
                patch.object(launcher, "run_av", side_effect=failed),
                patch.object(launcher, "VideoProcess", return_value=child),
                self.assertRaisesRegex(RuntimeError, "session failure"),
            ):
                launcher.run(args)
            result = json.loads((args.output / "session-summary.json").read_text())
            self.assertEqual(result["av"], {"input_packets": 7, "stop_sent": True})
            self.assertTrue(result["video"]["forced_stop"])
            self.assertIn("child cleanup", result["video"]["cleanup_error"])

    def test_capture_rejects_unspecified_source_and_missing_tools(self):
        """@brief Failed capture prerequisites never create an AV/media owner."""
        for unspecified in (False, True):
            with self.subTest(unspecified=unspecified), tempfile.TemporaryDirectory() as directory:
                args = self.args(Path(directory), ["--av-input", "--capture-interface", "adapter"])
                args.video = False
                args.bind = "0.0.0.0" if unspecified else "127.0.0.1"
                with (
                    patch.object(Path, "is_file", return_value=False),
                    patch.object(launcher, "run_av") as av,
                    patch.object(launcher, "CaptureOwner") as capture,
                    self.assertRaises((ValueError, FileNotFoundError)),
                ):
                    launcher.run(args)
                av.assert_not_called()
                capture.assert_not_called()
                result = json.loads((args.output / "session-summary.json").read_text())
                self.assertIn(
                    "concrete source" if unspecified else "installed dumpcap", result["error"]
                )

    def test_video_only_and_cli_exit_status(self):
        """@brief Video-only needs no AV owner; CLI exposes incomplete cleanup as failure."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory))
            child = MagicMock()
            child.process.pid = 123
            child.close.return_value = {"exit_code": 0, "forced_stop": False}
            with (
                patch.object(launcher, "VideoProcess", return_value=child),
                patch.object(launcher, "run_av") as av,
            ):
                launcher.run(args)
            av.assert_not_called()
            child.close.assert_called_once_with(grace=65)
        argv = ["--receiver", "127.0.0.1", "--start-frame-id", "0", "--output", "unused", "--video"]
        with (
            patch.object(
                launcher, "run", return_value={"av": {"audio_worker": {"shutdown_complete": False}}}
            ),
            patch("builtins.print"),
        ):
            self.assertEqual(launcher.main(argv), 1)
        with (
            patch.object(launcher, "run", return_value={"logging": {"dropped": 1}}),
            patch("builtins.print"),
        ):
            self.assertEqual(launcher.main(argv), 1)
        with (
            patch.object(launcher, "run", side_effect=ValueError("invalid")),
            patch("sys.stderr"),
            self.assertRaises(SystemExit),
        ):
            launcher.main(argv)

    def test_route_preflight_and_partial_file_cleanup(self):
        """@brief Reject wrong source routes and close stdout if stderr cannot be opened."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory))
            probe = MagicMock()
            probe.__enter__.return_value = probe
            probe.getsockname.return_value = ("192.0.2.1", 123)
            with (
                patch.object(launcher.socket, "socket", return_value=probe),
                self.assertRaises(ValueError),
            ):
                launcher.run(args)
            probe.bind.assert_called_once_with(("127.0.0.1", 0))
            self.assertFalse(args.output.exists())
            probe.bind.side_effect = OSError("source address unavailable")
            probe.connect.reset_mock()
            with (
                patch.object(launcher.socket, "socket", return_value=probe),
                self.assertRaisesRegex(OSError, "source address unavailable"),
            ):
                launcher.run(args)
            probe.connect.assert_not_called()
            self.assertFalse(args.output.exists())
            args.output.mkdir()
            output = MagicMock()
            with (
                patch.object(Path, "open", side_effect=[output, OSError("stderr exists")]),
                self.assertRaises(OSError),
            ):
                launcher.VideoProcess(args)
            output.close.assert_called_once()

    def test_av_only_and_entrypoint(self):
        """@brief AV-only skips route/capture and command entrypoint stays dry without side effects."""
        import runpy

        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory), ["--audio"])
            args.video = False

            def av_only(options, event, ready, health, stop_when):
                ready()
                health()
                self.assertFalse(stop_when())
                return {"cleanup_errors": []}

            with patch.object(launcher, "run_av", side_effect=av_only):
                result = launcher.run(args)
            self.assertNotIn("video", result)
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            argv = [
                "session_launcher.py",
                "--receiver",
                "127.0.0.1",
                "--audio",
                "--dry-run",
                "--start-frame-id",
                "0",
                "--output",
                str(Path(directory) / "dry"),
            ]
            with patch("sys.argv", argv), self.assertRaises(SystemExit) as stopped:
                runpy.run_path(launcher.__file__, run_name="__main__")
            self.assertEqual(stopped.exception.code, 0)

    def test_explicit_input_only_without_audio_or_injection(self):
        """@brief Input-only selects AV directly without requesting devices or video."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory), ["--av-input"])
            args.video = False

            def av_only(options, event, ready, health, stop_when):
                """@brief Check input-only intent at the actual owner boundary."""
                self.assertFalse(options.audio)
                self.assertFalse(options.gamepad)
                self.assertEqual(options.seconds, args.seconds)
                ready()
                health()
                self.assertFalse(stop_when())
                return {"input_packets": 4}

            with patch.object(launcher, "run_av", side_effect=av_only):
                result = launcher.run(args)
            self.assertEqual(result["av"]["input_packets"], 4)

    def test_saved_clip_preview_records_identity_and_looping(self):
        """@brief Reproducible clip runs require no artifact-only command replacement."""
        import hashlib

        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / "source.webm"
            clip.write_bytes(b"pinned-source-test")
            args = self.args(
                Path(directory),
                [
                    "--clip",
                    str(clip),
                    "--loop-clip",
                    "--av-input",
                    "--dry-run",
                    "--clip-selection",
                    "native",
                    "--fps",
                    "30",
                ],
            )
            preview = launcher.run(args)
            manifest = json.loads((args.output / "manifest.json").read_text())
            self.assertEqual(manifest["clip_sha256"], hashlib.sha256(clip.read_bytes()).hexdigest())
            self.assertEqual(manifest["clip_start_offset_seconds"], 0)
            self.assertEqual(manifest["clip_selection"], "native")
            command = preview["video_command"]
            self.assertEqual(command[command.index("--clip-selection") + 1], "native")
            self.assertIn("--loop-clip", preview["video_command"])
            self.assertNotIn("--desktop", preview["video_command"])
            args.video = False
            with self.assertRaisesRegex(ValueError, "requires --video"):
                launcher.validate(args)
            args.video = True
            args.clip = None
            with self.assertRaisesRegex(ValueError, "requires --clip"):
                launcher.validate(args)

    def test_relative_clip_is_resolved_before_child_changes_directory(self):
        """@brief Root-relative source paths survive VideoProcess's tools-directory cwd."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / "movie.webm"
            clip.write_bytes(b"source")
            args = self.args(root, ["--clip", "movie.webm", "--dry-run"])
            with patch("os.getcwd", return_value=str(root)):
                preview = launcher.run(args)
            command = preview["video_command"]
            self.assertEqual(command[command.index("--clip") + 1], str(clip))

    def test_video_exceeding_av_grace_is_failure(self):
        """@brief A nominal AV deadline cannot hide a still-running video process."""
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory), ["--av-input"])
            child = MagicMock()
            child.process.poll.return_value = None
            child.process.pid = 321
            child.close.return_value = {"exit_code": 1, "forced_stop": True}

            def finite(options, event, ready, health, stop_when):
                """@brief Simulate an exhausted finite AV grace before child completion."""
                ready()
                return {}

            with (
                patch.object(launcher, "run_av", side_effect=finite),
                patch.object(launcher, "VideoProcess", return_value=child),
                self.assertRaisesRegex(TimeoutError, "finite AV grace"),
            ):
                launcher.run(args)
            child.close.assert_called_once_with(grace=0)

    def test_capture_starts_before_av_and_finalizes_after_stop(self):
        """@brief Lifecycle and exact STOP inspection gate successful capture reporting."""
        from av_protocol import Packet

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dumpcap = root / "dumpcap.exe"
            dumpcap.touch()
            (root / "tshark.exe").touch()
            args = self.args(
                root,
                [
                    "--av-input",
                    "--capture-interface",
                    "loopback",
                    "--capture-executable",
                    str(dumpcap),
                ],
            )
            args.video = False
            capture = MagicMock()
            capture.start.return_value = {"active": True}
            capture.close.return_value = {"lifecycle_complete": True, "complete": True}
            capture.capture_path = root / "link.pcapng"
            calls = []
            capture.start.side_effect = lambda: calls.append("capture") or {"active": True}

            def av(options, event, ready, health, stop_when):
                """@brief Model a full active/STOP session after capture confirmation."""
                self.assertEqual(calls, ["capture"])
                calls.append("av")
                ready()
                health()
                event("stop_sent", wire_hex=Packet(b"MSC1", 4, 1).encode().hex())
                return {"stop_sent": True}

            with (
                patch.object(launcher, "CaptureOwner", return_value=capture),
                patch.object(launcher, "run_av", side_effect=av),
                patch.object(
                    launcher, "verify_stop", return_value={"stop_packet_verified": True}
                ) as verify,
            ):
                result = launcher.run(args)
            capture.record_stop.assert_called_once()
            capture.close.assert_called_once()
            verify.assert_called_once()
            self.assertTrue(result["capture"]["complete"])

    def test_capture_verification_failure_remains_in_summary(self):
        """@brief A finalized file without verified STOP is not a complete capture."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dumpcap = root / "dumpcap.exe"
            dumpcap.touch()
            (root / "tshark.exe").touch()
            args = self.args(
                root,
                [
                    "--av-input",
                    "--capture-interface",
                    "loopback",
                    "--capture-executable",
                    str(dumpcap),
                ],
            )
            args.video = False
            capture = MagicMock()
            capture.start.return_value = {"active": True}
            capture.close.return_value = {"lifecycle_complete": True, "complete": True}

            def av(options, event, ready, health, stop_when):
                """@brief Omit STOP to leave savefile identity unverified."""
                return {}

            with (
                patch.object(launcher, "CaptureOwner", return_value=capture),
                patch.object(launcher, "run_av", side_effect=av),
            ):
                result = launcher.run(args)
            self.assertFalse(result["capture"]["complete"])

    def test_capture_failure_between_ready_and_active_prevents_video(self):
        """@brief A capture that ended during handshake cannot precede a new video child."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dumpcap = root / "dumpcap.exe"
            dumpcap.touch()
            (root / "tshark.exe").touch()
            args = self.args(
                root,
                [
                    "--av-input",
                    "--capture-interface",
                    "loopback",
                    "--capture-executable",
                    str(dumpcap),
                ],
            )
            capture = MagicMock()
            capture.start.return_value = {"active": True}
            capture.health.side_effect = RuntimeError("capture expired")
            capture.close.return_value = {"lifecycle_complete": False}

            def active(options, event, ready, health, stop_when):
                """@brief Reach the ready callback after simulated AV handshake."""
                ready()

            with (
                patch.object(launcher, "CaptureOwner", return_value=capture),
                patch.object(launcher, "run_av", side_effect=active),
                patch.object(launcher, "VideoProcess") as video,
                self.assertRaisesRegex(RuntimeError, "capture expired"),
            ):
                launcher.run(args)
            video.assert_not_called()
            capture.close.assert_called_once()
            summary = json.loads((args.output / "session-summary.json").read_text())
            self.assertFalse(summary["capture"]["complete"])

    def test_capture_tool_error_does_not_lose_final_session_summary(self):
        """@brief Inspection failure remains explicit while logs/resources finish closing."""
        from av_protocol import Packet

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dumpcap = root / "dumpcap.exe"
            dumpcap.touch()
            (root / "tshark.exe").touch()
            args = self.args(
                root,
                [
                    "--av-input",
                    "--capture-interface",
                    "loopback",
                    "--capture-executable",
                    str(dumpcap),
                ],
            )
            args.video = False
            capture = MagicMock()
            capture.start.return_value = {"active": True}
            capture.close.return_value = {"lifecycle_complete": True}

            def active(options, event, ready, health, stop_when):
                """@brief Emit exact STOP bytes before modeled inspection failure."""
                event("stop_sent", wire_hex=Packet(b"MSC1", 4, 1).encode().hex())
                return {}

            with (
                patch.object(launcher, "CaptureOwner", return_value=capture),
                patch.object(launcher, "run_av", side_effect=active),
                patch.object(launcher, "verify_stop", side_effect=OSError("tshark failed")),
            ):
                summary = launcher.run(args)
            self.assertEqual(summary["logging"]["error"], None)
            self.assertFalse(summary["capture"]["complete"])
            self.assertIn("tshark failed", summary["capture"]["verification_error"])


if __name__ == "__main__":
    unittest.main()
