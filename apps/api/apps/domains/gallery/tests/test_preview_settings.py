import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from ..models import PreviewSettings
from ..utils import convert_to_webp


class PreviewSettingsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="preview-admin", is_staff=True)
        self.user = get_user_model().objects.create_user(username="preview-client")
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.url = "/api/gallery-preview-settings/"

    def test_defaults_and_persistence(self):
        self.assertEqual(self.api.get(self.url).data, {"quality": 85, "max_size": 1920})
        self.assertEqual(self.api.patch(self.url, {"quality": 70, "max_size": 1200}, format="json").status_code, 200)
        self.assertEqual(self.api.get(self.url).data, {"quality": 70, "max_size": 1200})
        self.assertEqual(PreviewSettings.objects.count(), 1)

    def test_rejects_invalid_ranges_and_client_access(self):
        for payload in ({"quality": 0}, {"quality": 101}, {"max_size": 20}, {"max_size": 10000}):
            self.assertEqual(self.api.patch(self.url, payload, format="json").status_code, 400)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(self.url).status_code, 403)
        self.assertEqual(self.api.patch(self.url, {"quality": 70}, format="json").status_code, 403)
        self.assertEqual(self.api.post(self.url).status_code, 403)

    @patch("apps.domains.gallery.tasks.regenerate_previews")
    def test_reprocessing_is_explicit_and_queued(self, task):
        self.api.patch(self.url, {"quality": 75}, format="json")
        task.enqueue.assert_not_called()
        self.assertEqual(self.api.post(self.url).status_code, 202)
        task.enqueue.assert_called_once_with()

    @patch("apps.domains.gallery.utils.Image.Image.save", autospec=True)
    def test_conversion_passes_configured_quality_without_mutating_source(self, save):
        with Image.new("RGB", (1600, 1000)) as image:
            convert_to_webp(image, (800, 800), quality=65)
            self.assertEqual(image.size, (1600, 1000))
        self.assertEqual(save.call_args.kwargs["quality"], 65)

    def test_configured_dimensions_are_respected(self):
        with Image.new("RGB", (1800, 1200)) as image:
            data = convert_to_webp(image, (900, 900), quality=75)
        with Image.open(io.BytesIO(data)) as converted:
            self.assertEqual(converted.size, (900, 600))
