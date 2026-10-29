import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image
from rest_framework.test import APIRequestFactory, force_authenticate

from ..views.image_preview import ImagePreviewView


class ImagePreviewTests(SimpleTestCase):
    def render(self, include_image=True, admin=True, **values):
        if include_image:
            output = io.BytesIO()
            Image.new("RGB", (1600, 1000), "#385371").save(output, format="JPEG")
            values["image"] = SimpleUploadedFile("sample.jpg", output.getvalue(), content_type="image/jpeg")
        request = APIRequestFactory().post("/api/gallery-preview-settings/render/", values, format="multipart")
        force_authenticate(request, user=SimpleNamespace(is_staff=admin, is_authenticated=True, pk=1))
        with patch(
            "apps.domains.gallery.views.image_preview.PreviewSettings.current",
            return_value=SimpleNamespace(quality=85, max_size=1920),
        ):
            return ImagePreviewView.as_view(throttle_classes=[])(request)

    def test_renders_webp_without_persisting_the_sample(self):
        with patch("django.core.files.storage.default_storage.save") as save:
            response = self.render(quality=65, max_size=800)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertEqual(response["Cache-Control"], "no-store")
        with Image.open(io.BytesIO(response.content)) as image:
            self.assertEqual(image.size, (800, 500))
        save.assert_not_called()

    def test_requires_an_uploaded_image_and_admin(self):
        self.assertEqual(self.render(include_image=False).status_code, 400)
        self.assertEqual(self.render(admin=False).status_code, 403)

    def test_rejects_invalid_settings_and_incomplete_watermark(self):
        for values in [{"quality": 101}, {"max_size": 0}, {"watermark": json.dumps({"text_color": "invalid"})}]:
            self.assertEqual(self.render(**values).status_code, 400)

    def test_uploaded_logo_is_rendered_at_the_selected_position(self):
        output = io.BytesIO()
        Image.new("RGBA", (100, 100), "red").save(output, format="PNG")
        logo = SimpleUploadedFile("logo.png", output.getvalue(), content_type="image/png")
        watermark = {
            "style": "image_overlay",
            "text": "",
            "text_color": "#FFF",
            "text_opacity": 0.5,
            "font_size_ratio": 0.03,
            "rotation_angle": -30,
            "tile_spacing": 200,
            "logo_opacity": 1,
            "logo_size_ratio": 0.15,
            "logo_position": "center",
        }
        response = self.render(logo=logo, watermark=json.dumps(watermark))
        self.assertEqual(response.status_code, 200)
        with Image.open(io.BytesIO(response.content)) as image:
            red, green, blue = image.getpixel((800, 500))
            self.assertGreater(red, 240)
            self.assertLess(max(green, blue), 15)
