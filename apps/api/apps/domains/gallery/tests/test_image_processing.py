import io
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from ..models import Gallery, Photo, PreviewSettings
from ..tasks import apply_watermark, process_photo
from ..utils import convert_to_webp


class PreviewConversionTests(SimpleTestCase):
    def test_thumbnail_does_not_reduce_the_source_used_for_preview(self):
        for size in ((700, 300), (300, 700), (3000, 2000)):
            with self.subTest(size=size), Image.new("RGB", size) as source:
                thumbnail = convert_to_webp(source, (400, 400))
                preview = convert_to_webp(source, (1920, 1920))
                self.assertEqual(source.size, size)
                with Image.open(io.BytesIO(thumbnail)) as image:
                    self.assertLessEqual(max(image.size), 400)
                with Image.open(io.BytesIO(preview)) as image:
                    self.assertEqual(max(image.size), min(1920, max(size)))


class PhotoProcessingTests(TestCase):
    @patch("apps.domains.gallery.tasks.apply_watermark")
    @patch("apps.domains.gallery.tasks.GoogleDriveService")
    def test_worker_uses_saved_preview_dimensions(self, service, watermark):
        PreviewSettings.objects.create(quality=70, max_size=900)
        buffer = io.BytesIO()
        with Image.new("RGB", (1800, 1200)) as image:
            image.save(buffer, format="JPEG")
        buffer.seek(0)
        service.return_value.open_file.return_value = buffer
        process_photo.func(str(self.photo.pk), self.user.pk)
        self.photo.refresh_from_db()
        with self.photo.preview.open("rb") as preview, Image.open(preview) as image:
            self.assertEqual(image.size, (900, 600))
        with self.photo.thumbnail.open("rb") as thumbnail, Image.open(thumbnail) as image:
            self.assertEqual(max(image.size), 400)
        self.assertEqual((self.photo.width, self.photo.height), (1800, 1200))
        watermark.enqueue.assert_called_once()

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user(username="image-admin", is_staff=True)
        self.gallery = Gallery.objects.create(name="Images", slug="images", watermark_enabled=True)
        self.photo = Photo.objects.create(
            gallery=self.gallery,
            name="image.jpg",
            source_file_id="file",
            watermarked_preview="old.webp",
        )

    @patch("apps.domains.gallery.tasks.apply_watermark")
    @patch("apps.domains.gallery.tasks.GoogleDriveService")
    def test_reprocessing_clears_old_watermark_and_versions_preview(self, service, watermark):
        def original():
            buffer = io.BytesIO()
            with Image.new("RGB", (700, 300)) as image:
                image.save(buffer, format="JPEG")
            buffer.seek(0)
            return buffer

        service.return_value.open_file.side_effect = lambda _file_id: original()
        process_photo.func(str(self.photo.pk), self.user.pk)
        self.photo.refresh_from_db()
        first_preview = self.photo.preview.name
        self.assertFalse(self.photo.watermarked_preview)
        self.assertEqual((self.photo.width, self.photo.height), (700, 300))
        with self.photo.preview.open("rb") as preview_file, Image.open(preview_file) as image:
            self.assertEqual(image.size, (700, 300))
        process_photo.func(str(self.photo.pk), self.user.pk)
        self.photo.refresh_from_db()
        self.assertNotEqual(self.photo.preview.name, first_preview)
        self.assertEqual(watermark.enqueue.call_count, 2)

    @patch("apps.domains.gallery.tasks.apply_watermark")
    @patch("apps.domains.gallery.tasks.GoogleDriveService")
    def test_processing_respects_exif_orientation(self, service, _watermark):
        buffer = io.BytesIO()
        with Image.new("RGB", (700, 300)) as image:
            exif = Image.Exif()
            exif[274] = 6
            image.save(buffer, format="JPEG", exif=exif)
        buffer.seek(0)
        service.return_value.open_file.return_value = buffer
        process_photo.func(str(self.photo.pk), self.user.pk)
        self.photo.refresh_from_db()
        self.assertEqual((self.photo.width, self.photo.height), (300, 700))

    @patch("apps.domains.gallery.tasks._resolve_watermark_asset")
    @patch("apps.domains.gallery.tasks._build_watermarked_image")
    def test_outdated_watermark_job_cannot_replace_a_newer_preview(self, build, asset):
        asset.return_value = object()
        buffer = io.BytesIO()
        with Image.new("RGB", (50, 50)) as image:
            image.save(buffer, format="WEBP")
        self.photo.preview.save("source.webp", ContentFile(buffer.getvalue()))
        self.photo.watermarked_preview = None
        self.photo.save()

        def replace_preview(image, _asset):
            Photo.objects.filter(pk=self.photo.pk).update(preview="newer.webp")
            return image.copy()

        build.side_effect = replace_preview
        apply_watermark.func(str(self.photo.pk))
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.preview.name, "newer.webp")
        self.assertFalse(self.photo.watermarked_preview)
