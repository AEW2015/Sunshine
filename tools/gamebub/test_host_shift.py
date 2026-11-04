"""@brief Regression tests for deterministic rightward canvas shifting."""

import unittest

from PIL import Image

import host
from msv1 import encode_receiver_jpeg


class ShiftCanvasRightTests(unittest.TestCase):
    """@brief Verify rightward shifts preserve the RGB canvas contract."""

    @staticmethod
    def column_pattern():
        """@brief Make a deterministic RGB image with identifiable columns and rows."""
        image = Image.new("RGB", (720, 480))
        pixels = image.load()
        for y in range(480):
            for x in range(720):
                pixels[x, y] = (x & 0xFF, (x >> 8) & 0xFF, y & 0xFF)
        return image

    def assert_shift(self, amount):
        """@brief Check geometry, exact pixels, allocation, and source preservation."""
        source = self.column_pattern()
        original = source.copy()

        result = host.shift_canvas_right(source, amount)

        self.assertIsInstance(result, Image.Image)
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (720, 480))
        self.assertIsNot(result, source)
        self.assertEqual(source.tobytes(), original.tobytes())
        for y in range(480):
            for x in range(720):
                expected = (0, 0, 0) if x < amount else source.getpixel((x - amount, y))
                self.assertEqual(result.getpixel((x, y)), expected, (amount, x, y))

    def test_shift_twenty_crops_the_right_edge(self):
        """@brief A twenty-pixel shift inserts black at left and crops right."""
        self.assert_shift(20)

    def test_zero_shift_returns_an_owned_copy(self):
        """@brief A zero-pixel shift preserves every pixel in a new image."""
        self.assert_shift(0)

    def test_maximum_shift_keeps_only_the_leftmost_source_column(self):
        """@brief A 719-pixel shift leaves one source column at the right edge."""
        self.assert_shift(719)

    def test_shifted_canvas_passes_receiver_jpeg_validation(self):
        """@brief The actual twenty-pixel result encodes under the strict receiver profile."""
        shifted = host.shift_canvas_right(self.column_pattern(), 20)

        jpeg = encode_receiver_jpeg(shifted, 65)

        self.assertGreater(len(jpeg), 0)
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        self.assertTrue(jpeg.endswith(b"\xff\xd9"))

    def test_invalid_images_and_shift_values_raise_value_error(self):
        """@brief Reject non-RGB, incorrect-sized, non-image, and invalid shift inputs."""
        valid = self.column_pattern()
        invalid_images = (
            object(),
            Image.new("L", (720, 480)),
            Image.new("RGB", (719, 480)),
        )
        for image in invalid_images:
            with (
                self.subTest(
                    image_type=type(image).__name__, image_mode=getattr(image, "mode", None)
                ),
                self.assertRaises(ValueError),
            ):
                host.shift_canvas_right(image, 20)

        for amount in (-1, 720, True, 1.5):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                host.shift_canvas_right(valid, amount)


if __name__ == "__main__":
    unittest.main()
