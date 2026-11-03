"""@brief Regression tests for the isolated host laboratory; no service/network use."""

import contextlib
import io
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import av
from PIL import Image

import host


def segment(marker, payload):
    """@brief Build a JPEG marker segment for malformed-input regression cases."""
    return bytes((255, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload


def replace_segment(data, marker, transform):
    """@brief Transform one JPEG header payload while preserving other segments."""
    offset = data.index(bytes((255, marker)))
    length = int.from_bytes(data[offset + 2 : offset + 4], "big")
    return (
        data[:offset]
        + transform(data[offset + 4 : offset + 2 + length])
        + data[offset + 2 + length :]
    )


class ImageTests(unittest.TestCase):
    """@brief Check canvas geometry and deterministic source pixels."""

    def test_geometry_preserves_sixteen_by_nine_and_black_bars(self):
        """@brief A solid 16:9 source occupies exactly 720x405 without stretching."""
        image = host.canvas(Image.new("RGB", (1280, 720), "red"))
        self.assertEqual(image.size, (720, 480))
        self.assertEqual(image.getbbox(), (0, 37, 720, 442))
        self.assertEqual(image.getpixel((0, 37)), (255, 0, 0))

    def test_portrait_is_fitted_without_cropping(self):
        """@brief Portrait and tiny inputs retain proportions and stay in the viewport."""
        self.assertEqual(
            host.canvas(Image.new("RGB", (1, 3), "white")).getbbox(), (292, 37, 427, 442)
        )
        self.assertEqual(
            host.canvas(Image.new("RGB", (10000, 1), "white")).getbbox(), (0, 239, 720, 240)
        )

    def test_video_frame_retains_color_and_letterbox(self):
        """@brief Video scaling keeps the fitted viewport and its source color."""
        source = av.VideoFrame.from_image(Image.new("RGB", (1280, 720), (240, 64, 32)))
        image = host.canvas(source)
        self.assertEqual(image.size, (720, 480))
        self.assertEqual(image.getbbox(), (0, 37, 720, 442))
        self.assertEqual(image.getpixel((360, 240)), (240, 64, 32))

    def test_alternate_resize_filters_keep_canvas_geometry(self):
        """@brief Desktop filters preserve letterbox geometry while changing interpolation."""
        source = host.pattern(2)
        lanczos = host.canvas(source)
        for filter_type in (Image.Resampling.BILINEAR, Image.Resampling.BICUBIC):
            with self.subTest(filter_type=filter_type):
                scaled = host.canvas(source, filter_type)
                self.assertEqual(scaled.size, (720, 480))
                self.assertEqual(scaled.getpixel((0, 0)), (0, 0, 0))
                self.assertNotEqual(scaled.tobytes(), lanczos.tobytes())

    def test_pattern_is_deterministic_and_moves(self):
        """@brief ID patch and motion are deterministic, including wrapped IDs."""
        self.assertEqual(host.pattern(1).tobytes(), host.pattern(1).tobytes())
        self.assertNotEqual(host.pattern(0).tobytes(), host.pattern(1).tobytes())
        self.assertEqual(host.pattern(1).getpixel((0, 700)), (255, 255, 255))
        self.assertEqual(host.pattern(0).getpixel((0, 700)), (0, 0, 0))


class JpegTests(unittest.TestCase):
    """@brief Inspect actual encoded bytes and reject unsupported/malformed headers."""

    @classmethod
    def setUpClass(cls):
        """@brief Create a valid baseline image once for mutation tests."""
        cls.image = host.canvas(host.pattern(2))
        cls.data, cls.metadata = host.encode(cls.image, 75, host.Profile())

    def test_profile_bounds(self):
        """@brief Reject unsupported sampling, bounds, and malformed digests."""
        for options in (
            {"subsampling": "4:1:1"},
            {"restart_mcus": -1},
            {"restart_mcus": 65536},
            {"max_frame_bytes": 0},
            {"max_frame_bytes": 16777217},
            {"huffman_sha256": "a"},
            {"huffman_sha256": "G" * 64},
            {"huffman_sha256": 123},
            {"restart_mcus": True},
            {"max_frame_bytes": 1.5},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                host.Profile(**options)

    def test_every_supported_sampling_and_restart_setting(self):
        """@brief Parse every supported sampling mode, with restart markers on/off."""
        for sampling in ("4:4:4", "4:2:2", "4:2:0"):
            for interval in (0, 7, 65535):
                with self.subTest(sampling=sampling, interval=interval):
                    data, info = host.encode(self.image, 75, host.Profile(sampling, interval))
                    self.assertEqual(info["subsampling"], sampling)
                    self.assertEqual(info["restart_mcus"], interval)
                    self.assertEqual((info["width"], info["height"]), (720, 480))
                    with Image.open(io.BytesIO(data)) as image:
                        image.load()
                        self.assertEqual(image.mode, "RGB")

    def test_huffman_reference_and_size_enforced(self):
        """@brief Match a receiver table fingerprint and enforce maximum frame bytes."""
        host.encode(self.image, 20, host.Profile(huffman_sha256=self.metadata["huffman_sha256"]))
        with self.assertRaisesRegex(ValueError, "Huffman"):
            host.encode(self.image, 75, host.Profile(huffman_sha256="0" * 64))
        with self.assertRaises(OverflowError):
            host.encode(self.image, 75, host.Profile(max_frame_bytes=1))
        for quality, image in ((0, self.image), (96, self.image), (75, Image.new("RGB", (1, 1)))):
            with self.assertRaises(ValueError):
                host.encode(image, quality, host.Profile())

    def test_encoder_option_mismatch_detected_from_bitstream(self):
        """@brief Detect a library ignoring a sampling/restart option."""
        with (
            patch("host.inspect_jpeg", return_value={"subsampling": "4:4:4", "restart_mcus": 0}),
            self.assertRaisesRegex(ValueError, "honor"),
        ):
            host.encode(self.image, 75, host.Profile())

    def test_truncations_and_unsupported_markers(self):
        """@brief Reject bad segment lengths, marker syntax, coding modes, and tails."""
        invalid = [
            b"",
            b"bad",
            b"\xff\xd8",
            b"\xff\xd8x",
            b"\xff\xd8\xff\xe0",
            b"\xff\xd8\xff\xe0\x00",
            b"\xff\xd8\xff\xe0\x00\x01",
            b"\xff\xd8\xff\xe0\xff\xff",
            self.data[:-2],
            self.data[:-1],
            self.data + b"x",
            self.data[:-2] + b"\xff\xd0\xff\xd9",
            self.data.replace(b"\xff\xc0", b"\xff\xc2", 1),
        ]
        for data in invalid:
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                host.inspect_jpeg(data)

    def test_header_restrictions(self):
        """@brief Reject missing/duplicate tables and unsupported component/scan layouts."""
        mutations = [
            (0xC0, lambda p: segment(0xC0, p) * 2),
            (0xC0, lambda p: segment(0xC0, b"\x0c" + p[1:])),
            (0xC0, lambda p: segment(0xC0, p[:-1])),
            (0xC0, lambda p: segment(0xC0, p[:6] + b"\x02" + p[7:])),
            (0xC0, lambda p: segment(0xC0, p[:8] + b"\x01" + p[9:])),
            (0xC0, lambda p: segment(0xC0, p[:7] + b"\x41" + p[8:])),
            (0xC0, lambda p: segment(0xC0, p[:9] + b"\x04" + p[10:])),
            (0xC0, lambda p: segment(0xC0, p[:3] + b"\x00\x00" + p[5:])),
            (0xC0, lambda p: b""),
            (0xDA, lambda p: segment(0xDA, b"bad scan")),
            (0xC4, lambda p: segment(0xC4, p[:10])),
            (0xC4, lambda p: segment(0xC4, p[:-1])),
            (0xC4, lambda p: segment(0xC4, b"\x02" + p[1:])),
            (0xC4, lambda p: segment(0xC4, p * 2)),
            (0xC4, lambda p: b""),
            (0xDB, lambda p: segment(0xDB, b"\x10" + p[1:])),
            (0xDB, lambda p: segment(0xDB, p[:-1])),
            (0xDB, lambda p: segment(0xDB, p * 2)),
            (0xDB, lambda p: b""),
        ]
        for marker, transform in mutations:
            with self.subTest(marker=marker, transform=transform), self.assertRaises(ValueError):
                host.inspect_jpeg(replace_segment(self.data, marker, transform))
        # APP and COM payloads are permitted but never interpreted as entropy data.
        self.assertEqual(
            host.inspect_jpeg(self.data[:2] + segment(0xFE, b"note") + self.data[2:]), self.metadata
        )

    def test_restart_sequence_count_and_interval(self):
        """@brief Detect wrong restart order, missing markers, and invalid DRI lengths."""
        data, _ = host.encode(self.image, 75, host.Profile(restart_mcus=10))
        mutations = [
            data.replace(b"\xff\xd0", b"\xff\xd1", 1),
            data.replace(b"\xff\xd0", b"", 1),
            replace_segment(data, 0xDD, lambda p: segment(0xDD, b"\x00")),
            replace_segment(data, 0xDD, lambda p: segment(0xDD, p) * 2),
            replace_segment(data, 0xDD, lambda p: segment(0xDD, b"\xff\xff")),
        ]
        for changed in mutations:
            with self.assertRaises(ValueError):
                host.inspect_jpeg(changed)

    def test_entropy_scan_handles_stuffed_bytes_and_truncation(self):
        """@brief Search past stuffed 0xff bytes and reject incomplete entropy markers."""
        prefix = self.data[:-2]
        self.assertEqual(host.inspect_jpeg(prefix + b"\xff\x00\x01\xff\xd9"), self.metadata)
        for tail in (b"\x01\x02", b"\xff", b"\xff\x00", b"\xff\xc4"):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                host.inspect_jpeg(prefix + tail)


class LinkTests(unittest.TestCase):
    """@brief Check exact simulated deadlines and bounded capacity under overload."""

    def test_capacity_and_rejection_do_not_build_a_queue(self):
        """@brief A rejected frame does not consume simulated link capacity."""
        link = host.LinkModel(8000, 0.2)
        self.assertEqual(link.reserve(100, 1, 1), 1.1)
        self.assertIsNone(link.reserve(1000, 1, 1.01))
        self.assertAlmostEqual(link.next_free, 1.1)
        self.assertAlmostEqual(link.reserve(10, 1, 1.01), 1.11)
        self.assertIsNone(link.reserve(1, 0, 1.2))

    def test_empty_and_nearest_rank_statistics(self):
        """@brief Empty runs are explicit and quantiles follow nearest-rank selection."""
        self.assertEqual(host.distribution([]), {"count": 0, "p50": None, "p95": None, "max": None})
        self.assertEqual(host.distribution([3, 1, 2]), {"count": 3, "p50": 2, "p95": 3, "max": 3})


class PipelineTests(unittest.TestCase):
    """@brief Exercise real file output, video decoding, and overload handling."""

    def invoke(self, folder, *options):
        """@brief Run the CLI and load its machine-readable summary and attempt log."""
        clock = [1.0]

        def sleep(seconds):
            """@brief Advance simulated monotonic time to make pacing tests reproducible."""
            clock[0] += seconds

        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch("host.time.perf_counter", side_effect=lambda: clock[0]),
            patch("host.time.sleep", side_effect=sleep),
        ):
            status = host.main(["--output", str(folder), "--frames", "3", *options])
        summary = json.loads((folder / "summary.json").read_text())
        rows = [json.loads(row) for row in (folder / "frames.jsonl").read_text().splitlines()]
        return status, summary, rows

    def test_successful_file_sink_and_profile(self):
        """@brief Save decodable files and logs without claiming receiver playback."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            profile = folder / "profile.json"
            profile.write_text(json.dumps({"restart_mcus": 20}))
            status, summary, rows = self.invoke(
                folder, "--profile", str(profile), "--save-jpeg", "--link-mbps", "1000"
            )
            self.assertEqual(status, 0)
            self.assertFalse(summary["end_to_end_verified"])
            self.assertEqual(summary["counts"]["simulated_complete"], len(rows))
            self.assertGreater(len(list(folder.glob("*.jpg"))), 0)
            self.assertEqual(rows[0]["jpeg"]["restart_mcus"], 20)

    def test_slow_link_drops_and_reduces_quality(self):
        """@brief Stale frames are dropped and quality decreases, without a growing queue."""
        with tempfile.TemporaryDirectory() as temp:
            _, summary, rows = self.invoke(Path(temp), "--link-mbps", "0.001")
            self.assertEqual(summary["counts"]["stale"], len(rows))
            self.assertEqual(summary["simulated_complete_fps"], 0)
            self.assertLess(rows[-1]["quality"], rows[0]["quality"])

    def test_over_budget_success_also_reduces_quality(self):
        """@brief A link slower than target cadence reduces quality and skips stale slots."""
        with tempfile.TemporaryDirectory() as temp:
            _, summary, rows = self.invoke(Path(temp), "--link-mbps", "8", "--max-age-ms", "500")
            self.assertGreater(summary["counts"]["skipped_slots"], 0)
            self.assertEqual(rows[0]["status"], "simulated_complete")
            self.assertLess(rows[-1]["quality"], rows[0]["quality"])

    def test_quality_recovers_to_user_ceiling(self):
        """@brief After transient overload, quality increases within the requested ceiling."""
        original = host.LinkModel.reserve

        def once_stale(link, size, captured, now):
            """@brief Reject only the first attempt to simulate transient congestion."""
            if not link.next_free:
                link.next_free = now
                return None
            return original(link, size, captured, now)

        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(host.LinkModel, "reserve", once_stale),
        ):
            _, _, rows = self.invoke(Path(temp), "--link-mbps", "1000")
            self.assertGreater(rows[-1]["quality"], rows[1]["quality"])

    def test_quality_stays_stable_with_moderate_headroom(self):
        """@brief Avoid quality oscillation when frame size is within the stable band."""
        with tempfile.TemporaryDirectory() as temp:
            _, _, rows = self.invoke(Path(temp), "--link-mbps", "21")
            self.assertTrue(all(row["quality"] == 75 for row in rows))

    def test_desktop_filter_is_applied_and_recorded(self):
        """@brief An opted-in fast desktop filter is used and recorded in the run summary."""
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("host.ImageGrab.grab", return_value=host.pattern(0)),
            patch("host.canvas", wraps=host.canvas) as resize,
        ):
            status, summary, _ = self.invoke(
                Path(temp), "--desktop", "--desktop-filter", "bilinear", "--link-mbps", "1000"
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["desktop_filter"], "bilinear")
            self.assertEqual(resize.call_args.args[1], Image.Resampling.BILINEAR)

    def test_failure_exit_and_desktop_source(self):
        """@brief Desktop capture errors are logged and produce a failing exit status."""
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("host.ImageGrab.grab", side_effect=OSError("capture")),
        ):
            status, summary, rows = self.invoke(Path(temp), "--desktop")
            self.assertEqual(status, 2)
            self.assertGreater(summary["counts"]["failures"], 0)
            self.assertIn("capture", rows[0]["error"])
            self.assertEqual(summary["source"], "desktop")

    def test_real_video_decode_resampling_and_eof(self):
        """@brief Decode a real 60-Hz clip on the 30-Hz source timeline, then stop at EOF."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            clip = folder / "input.mp4"
            with av.open(str(clip), "w") as container:
                stream = container.add_stream("mpeg4", rate=60)
                stream.width, stream.height, stream.pix_fmt = 160, 90, "yuv420p"
                for index in range(6):
                    frame = av.VideoFrame.from_image(
                        Image.new("RGB", (160, 90), (index * 30, 0, 0))
                    )
                    frame.pts, frame.time_base = index, Fraction(1, 60)
                    for packet in stream.encode(frame):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)
            frames = list(host.clip_frames(clip, 30))
            self.assertEqual(len(frames), 3)
            self.assertLess(
                frames[0].to_image().getpixel((0, 0))[0], frames[1].to_image().getpixel((0, 0))[0]
            )
            _, summary, _ = self.invoke(
                folder, "--clip", str(clip), "--frames", "30", "--link-mbps", "1000"
            )
            self.assertEqual(summary["counts"]["eof"], 1)
            self.assertEqual(summary["source"], str(clip))

    def test_clip_rejects_bad_pixel_aspect_and_timestamps(self):
        """@brief Refuse sources whose timing or pixel aspect would distort measurements."""
        for aspect, times in ((2, []), (1, [None]), (1, [0, 0])):
            container = unittest.mock.MagicMock()
            container.__enter__.return_value = container
            container.streams.video[0].sample_aspect_ratio = aspect
            frames = []
            for timestamp in times:
                frame = unittest.mock.Mock()
                frame.time = timestamp
                frames.append(frame)
            container.decode.return_value = iter(frames)
            with patch("host.av.open", return_value=container), self.assertRaises(ValueError):
                list(host.clip_frames(Path("fake"), 30))

    def test_empty_clip(self):
        """@brief An empty decoded source yields no fabricated video frames."""
        container = unittest.mock.MagicMock()
        container.__enter__.return_value = container
        container.streams.video[0].sample_aspect_ratio = 1
        container.decode.return_value = iter(())
        with patch("host.av.open", return_value=container):
            self.assertEqual(list(host.clip_frames(Path("fake"), 30)), [])

    def test_last_frame_without_duration_uses_source_rate(self):
        """@brief A final 24-Hz frame is held for its duration, including fallback metadata."""
        for rate in (24, None):
            container = unittest.mock.MagicMock()
            container.__enter__.return_value = container
            stream = container.streams.video[0]
            stream.sample_aspect_ratio, stream.average_rate = 1, rate
            frame = unittest.mock.Mock(time=0, duration=0)
            frame.to_image.return_value = Image.new("RGB", (16, 9))
            container.decode.return_value = iter([frame])
            with patch("host.av.open", return_value=container):
                self.assertEqual(len(list(host.clip_frames(Path("fake"), 30))), 2 if rate else 1)

    def test_invalid_profile_and_existing_measurements_are_preserved(self):
        """@brief Fail cleanly for malformed profiles and refuse overwriting prior runs."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            profile = folder / "profile.json"
            profile.write_text("invalid json")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                host.main(["--output", temp, "--profile", str(profile)])
            self.invoke(folder, "--link-mbps", "1000")
            before = (folder / "summary.json").read_bytes()
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                host.main(["--output", temp])
            self.assertEqual(before, (folder / "summary.json").read_bytes())

    def test_assets_reproduce_the_committed_manifest(self):
        """@brief Regenerate and verify all fixtures against the committed integrity hashes."""
        from make_assets import generate

        with tempfile.TemporaryDirectory() as temp:
            manifest = generate(Path(temp))
            self.assertEqual(
                manifest, json.loads((Path(__file__).parent / "fixtures/manifest.json").read_text())
            )
            for item in manifest["frames"]:
                self.assertEqual(
                    host.inspect_jpeg((Path(temp) / item["jpeg"]).read_bytes())["width"], 720
                )

    def test_argument_bounds(self):
        """@brief Reject invalid cadence, unbounded floats, and invalid quality intervals."""
        for option, value in (
            ("--frames", "0"),
            ("--frames", "108001"),
            ("--fps", "60"),
            ("--quality", "96"),
            ("--min-quality", "80"),
            ("--link-mbps", "nan"),
            ("--link-mbps", "0"),
            ("--max-age-ms", "inf"),
            ("--max-age-ms", "0"),
        ):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                host.main(["--output", "unused", option, value])


if __name__ == "__main__":
    unittest.main()
