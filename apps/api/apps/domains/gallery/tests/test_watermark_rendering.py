from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image, ImageChops

from ..utils import _apply_logo_watermark, _apply_text_watermark, _load_font


class WatermarkRenderingTests(SimpleTestCase):
    def render(self, image, **overrides):
        values = {
            "text": "Studio",
            "color": "#FFFFFF",
            "opacity": 0.35,
            "font_size_ratio": 0.03,
            "rotation_angle": -30,
            "tile_spacing": 100,
        }
        return _apply_text_watermark(image, **(values | overrides))

    def test_reprocessing_keeps_the_preview_pattern_stable(self):
        with Image.new("RGB", (800, 600), "#345678") as source:
            first = self.render(source)
            second = self.render(source)
            rotated = self.render(source, rotation_angle=30)
            self.assertIsNone(ImageChops.difference(first, second).getbbox())
            self.assertIsNotNone(ImageChops.difference(first, rotated).getbbox())
            self.assertIsNotNone(ImageChops.difference(first, source).getbbox())

    def test_renderer_uses_the_bundled_font(self):
        self.assertEqual(Path(_load_font(24).path).name, "Arimo.ttf")

    def test_every_tile_respects_the_configured_rotation(self):
        rotate = Image.Image.rotate
        with Image.new("RGB", (320, 240), "#345678") as source:
            for angle in (0, -30, 30):
                for randomize in (True, False):
                    with self.subTest(angle=angle, randomize=randomize):
                        with patch.object(Image.Image, "rotate", autospec=True, side_effect=rotate) as mocked_rotate:
                            self.render(source, rotation_angle=angle, randomize=randomize)
                        self.assertGreater(mocked_rotate.call_count, 1)
                        self.assertEqual({call.args[1] for call in mocked_rotate.call_args_list}, {angle})

    def test_logo_uses_integer_center_coordinates(self):
        with Image.new("RGB", (101, 81), "black") as source, Image.new("RGBA", (10, 10), "red") as logo:
            rendered = _apply_logo_watermark(source, logo, opacity=1, size_ratio=0.1, position="center")
            self.assertGreater(rendered.getpixel((50, 40))[0], 240)
            self.assertEqual(rendered.size, (101, 81))
