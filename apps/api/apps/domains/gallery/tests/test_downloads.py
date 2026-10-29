from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ..models import Gallery, Photo


class PhotoDownloadTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client = APIClient()
        self.gallery = Gallery.objects.create(name="Ensaio", slug="ensaio", is_published=True)
        self.photo = Photo.objects.create(gallery=self.gallery, name="portrait.jpg", status="ready")
        self.photo.preview.save("preview.webp", ContentFile(b"preview-bytes"))
        self.photo.watermarked_preview.save("marked.webp", ContentFile(b"marked-bytes"))
        self.url = f"/api/galleries/public/ensaio/photos/{self.photo.pk}/download/"

    def test_download_policy_matrix_matches_public_contract(self):
        for default in (False, True):
            for policy in ("inherit", "allow", "deny"):
                with self.subTest(default=default, policy=policy):
                    self.gallery.allow_downloads = default
                    self.gallery.save()
                    self.photo.download_policy = policy
                    self.photo.save()
                    expected = default if policy == "inherit" else policy == "allow"
                    response = self.client.get("/api/galleries/public/ensaio/")
                    self.assertEqual(response.data["photos"][0]["can_download"], expected)
                    download = self.client.get(self.url)
                    self.assertEqual(download.status_code, 200 if expected else 403)
                    if expected:
                        self.assertEqual(b"".join(download.streaming_content), b"preview-bytes")

    def test_download_uses_watermark_and_correct_filename(self):
        self.gallery.watermark_enabled = True
        self.gallery.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"marked-bytes")
        self.assertIn('filename="portrait.webp"', response["Content-Disposition"])
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_inactive_photo_cannot_be_downloaded_publicly(self):
        self.photo.is_active = False
        self.photo.save(update_fields=["is_active"])

        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_missing_watermark_never_falls_back_to_unmarked_preview(self):
        self.gallery.watermark_enabled = True
        self.gallery.save()
        self.photo.watermarked_preview = ""
        self.photo.save()
        response = self.client.get("/api/galleries/public/ensaio/")
        self.assertFalse(response.data["photos"][0]["can_download"])
        self.assertIsNone(response.data["photos"][0]["preview"])
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_private_gallery_requires_access_code_even_when_photo_allows_downloads(self):
        self.gallery.access_type = "private"
        self.gallery.access_code_hash = make_password("secret-code")
        self.gallery.save()
        self.photo.download_policy = "allow"
        self.photo.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        response = self.client.get(self.url, HTTP_X_GALLERY_ACCESS_CODE="secret-code")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"preview-bytes")

    def test_draft_processing_foreign_and_missing_files_are_not_downloadable(self):
        self.gallery.is_published = False
        self.gallery.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.gallery.is_published = True
        self.gallery.save()
        self.photo.status = "processing"
        self.photo.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.photo.status = "ready"
        other = Gallery.objects.create(name="Other", slug="other", is_published=True)
        self.photo.gallery = other
        self.photo.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.photo.gallery = self.gallery
        self.photo.preview = "missing.webp"
        self.photo.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_only_photographer_can_change_policy_and_invalid_values_are_rejected(self):
        url = f"/api/photos/{self.photo.pk}/"
        self.assertIn(self.client.patch(url, {"download_policy": "allow"}).status_code, (401, 403))
        user = get_user_model().objects.create_user(username="client")
        self.client.force_authenticate(user)
        self.assertEqual(self.client.patch(url, {"download_policy": "allow"}).status_code, 403)
        user.is_staff = True
        user.save()
        for policy in ("allow", "deny", "inherit"):
            response = self.client.patch(url, {"download_policy": policy}, format="json")
            self.assertEqual(response.status_code, 200)
            self.photo.refresh_from_db()
            self.assertEqual(self.photo.download_policy, policy)
        self.assertEqual(self.client.patch(url, {"download_policy": "invalid"}).status_code, 400)

    def test_public_serializer_excludes_admin_fields(self):
        response = self.client.get("/api/galleries/public/ensaio/")
        for field in ("download_policy", "source_file_id", "source_user", "exif"):
            self.assertNotIn(field, response.data["photos"][0])

    def test_new_photos_inherit_the_gallery_default(self):
        self.assertEqual(self.photo.download_policy, "inherit")
