from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from ..models import Gallery
from ..views.gallery import GalleryViewSet


class GalleryConfigurationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="gallery-admin", is_staff=True)
        self.factory = APIRequestFactory()

    def create_gallery(self, **overrides):
        payload = {"name": "Ensaio", "slug": "ensaio", "access_type": "unlisted", **overrides}
        request = self.factory.post("/api/galleries/", payload, format="json")
        force_authenticate(request, user=self.user)
        return GalleryViewSet.as_view({"post": "create"})(request)

    def test_creates_draft_with_configuration(self):
        response = self.create_gallery(
            description="Fotos do ensaio", allow_downloads=False, source_folder_id="folder-id"
        )
        self.assertEqual(response.status_code, 201)
        gallery = Gallery.objects.get()
        self.assertFalse(gallery.is_published)
        self.assertFalse(gallery.allow_downloads)
        self.assertEqual(gallery.source_folder_id, "folder-id")

    def test_private_gallery_requires_access_code(self):
        response = self.create_gallery(access_type="private")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Gallery.objects.exists())

    def test_non_private_gallery_ignores_access_code(self):
        for access_type in ("public", "unlisted"):
            for code in ("1234", "", "test-code"):
                with self.subTest(access_type=access_type, code=code):
                    response = self.create_gallery(
                        slug=f"{access_type}-{code or 'empty'}", access_type=access_type, access_code=code
                    )
                    self.assertEqual(response.status_code, 201)
                    self.assertFalse(Gallery.objects.get(pk=response.data["id"]).access_code_hash)

    def test_private_gallery_rejects_short_access_code(self):
        response = self.create_gallery(access_type="private", access_code="1234")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            any(error["attr"] == "access_code" and error["code"] == "min_length" for error in response.data["errors"])
        )
        self.assertFalse(Gallery.objects.exists())

    def test_public_gallery_update_ignores_short_access_code(self):
        response = self.create_gallery(access_type="public")
        gallery = Gallery.objects.get(pk=response.data["id"])
        request = self.factory.patch(
            f"/api/galleries/{gallery.pk}/", {"access_code": "1234", "name": "Novo nome"}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = GalleryViewSet.as_view({"patch": "partial_update"})(request, pk=gallery.pk)
        self.assertEqual(response.status_code, 200)
        gallery.refresh_from_db()
        self.assertEqual(gallery.name, "Novo nome")
        self.assertFalse(gallery.access_code_hash)

    def test_private_access_code_is_hashed_and_not_returned(self):
        response = self.create_gallery(access_type="private", access_code="test-code")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(check_password("test-code", Gallery.objects.get().access_code_hash))
        self.assertNotIn("access_code", response.data)
        self.assertNotIn("access_code_hash", response.data)

    def test_sales_require_package_price_or_individual_purchase(self):
        self.assertEqual(self.create_gallery(enable_sales=True).status_code, 400)

    def test_accepts_positive_package_price_and_currency(self):
        response = self.create_gallery(enable_sales=True, gallery_price="150.00", gallery_price_currency="BRL")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Gallery.objects.get().gallery_price.amount, 150)
        self.assertEqual(str(Gallery.objects.get().gallery_price.currency), "BRL")

    def test_rejects_duplicate_slug(self):
        self.assertEqual(self.create_gallery().status_code, 201)
        self.assertEqual(self.create_gallery().status_code, 400)

    def test_edit_preserves_access_code_when_omitted(self):
        self.create_gallery(access_type="private", access_code="test-code")
        gallery = Gallery.objects.get()
        request = self.factory.patch(f"/api/galleries/{gallery.pk}/", {"name": "Novo nome"}, format="json")
        force_authenticate(request, user=self.user)
        response = GalleryViewSet.as_view({"patch": "partial_update"})(request, pk=gallery.pk)
        self.assertEqual(response.status_code, 200)
        gallery.refresh_from_db()
        self.assertEqual(gallery.name, "Novo nome")
        self.assertTrue(check_password("test-code", gallery.access_code_hash))

    def test_created_gallery_is_returned_in_paginated_list(self):
        response = self.create_gallery()
        request = self.factory.get("/api/galleries/")
        force_authenticate(request, user=self.user)
        listing = GalleryViewSet.as_view({"get": "list"})(request)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["id"], response.data["id"])

    def test_search_and_filters_apply_before_pagination(self):
        Gallery.objects.create(name="Cliente Ana", slug="ana", access_type="private", is_published=True)
        Gallery.objects.create(name="Cliente Pedro", slug="pedro", access_type="public")
        request = self.factory.get(
            "/api/galleries/", {"search": "Ana", "access_type": "private", "is_published": "true"}
        )
        force_authenticate(request, user=self.user)
        response = GalleryViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "ana")

    def test_theme_defaults_to_masonry(self):
        response = self.create_gallery()
        self.assertEqual(response.data["theme"], "masonry")
        self.assertEqual(Gallery.objects.get().theme, "masonry")

    def test_photographer_can_save_each_theme(self):
        for theme in ["masonry", "instagram", "classic", "featured", "carousel"]:
            with self.subTest(theme=theme):
                response = self.create_gallery(slug=theme, theme=theme)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.data["theme"], theme)
                self.assertEqual(Gallery.objects.get(slug=theme).theme, theme)

    def test_rejects_unknown_theme(self):
        response = self.create_gallery(theme="unknown")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"][0]["attr"], "theme")

    def test_photographer_can_update_theme(self):
        self.create_gallery()
        gallery = Gallery.objects.get()
        request = self.factory.patch(f"/api/galleries/{gallery.pk}/", {"theme": "carousel"}, format="json")
        force_authenticate(request, user=self.user)
        response = GalleryViewSet.as_view({"patch": "partial_update"})(request, pk=gallery.pk)
        self.assertEqual(response.status_code, 200)
        gallery.refresh_from_db()
        self.assertEqual(gallery.theme, "carousel")
        request = self.factory.get(f"/api/galleries/{gallery.pk}/")
        force_authenticate(request, user=self.user)
        response = GalleryViewSet.as_view({"get": "retrieve"})(request, pk=gallery.pk)
        self.assertEqual(response.data["theme"], "carousel")

    def test_client_cannot_change_theme(self):
        self.create_gallery()
        gallery = Gallery.objects.get()
        client = get_user_model().objects.create_user(username="gallery-client")
        request = self.factory.patch(f"/api/galleries/{gallery.pk}/", {"theme": "carousel"}, format="json")
        force_authenticate(request, user=client)
        response = GalleryViewSet.as_view({"patch": "partial_update"})(request, pk=gallery.pk)
        self.assertEqual(response.status_code, 403)
        gallery.refresh_from_db()
        self.assertEqual(gallery.theme, "masonry")


class PhotoSyncTests(TestCase):
    def setUp(self):
        from ..models import Photo

        self.user = get_user_model().objects.create_user(username="sync-admin", is_staff=True)
        self.gallery = Gallery.objects.create(name="Sync", slug="sync", source_folder_id="folder")
        self.photo = Photo.objects.create(gallery=self.gallery, name="Photo", source_file_id="file", status="ready")
        self.factory = APIRequestFactory()

    def sync_photo(self, user=None):
        from ..views.photo import PhotoViewSet

        request = self.factory.post(f"/api/photos/{self.photo.pk}/sync/")
        force_authenticate(request, user=user or self.user)
        return PhotoViewSet.as_view({"post": "sync"})(request, pk=self.photo.pk)

    @patch("apps.domains.gallery.views.photo.process_photo")
    def test_sync_enqueues_selected_photo(self, enqueue):
        response = self.sync_photo()
        self.assertEqual(response.status_code, 202)
        enqueue.enqueue.assert_called_once_with(str(self.photo.pk), self.user.pk)

    @patch("apps.domains.gallery.views.photo.process_photo")
    def test_missing_source_is_rejected(self, enqueue):
        self.photo.source_file_id = ""
        self.photo.save()
        self.assertEqual(self.sync_photo().status_code, 400)
        enqueue.enqueue.assert_not_called()

    @patch("apps.domains.gallery.views.photo.process_photo")
    def test_client_cannot_sync(self, enqueue):
        client = get_user_model().objects.create_user(username="sync-client")
        self.assertEqual(self.sync_photo(client).status_code, 403)
        enqueue.enqueue.assert_not_called()

    @patch("apps.domains.gallery.tasks.process_photo")
    @patch("apps.domains.gallery.tasks.GoogleDriveService")
    def test_full_sync_refreshes_existing_and_imports_new_photos(self, service_class, enqueue):
        from types import SimpleNamespace

        from ..models import Photo
        from ..tasks import sync_gallery_drive

        service_class.return_value.list_files.return_value = [
            SimpleNamespace(id="file", name="Updated", size=123, mime_type="image/jpeg"),
            SimpleNamespace(id="new", name="New", size=456, mime_type="image/jpeg"),
        ]
        self.photo.download_policy = "deny"
        self.photo.save(update_fields=["download_policy"])
        sync_gallery_drive.func(self.gallery.pk, self.user.pk)
        self.assertEqual(Photo.objects.filter(gallery=self.gallery).count(), 2)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.name, "Updated")
        self.assertEqual(self.photo.status, "processing")
        self.assertEqual(self.photo.download_policy, "deny")
        self.assertEqual(enqueue.enqueue.call_count, 2)

    @patch("apps.domains.gallery.tasks.GoogleDriveService")
    def test_gallery_sync_with_immediate_backend_accepts_uuid_ids(self, service_class):
        from django.test import override_settings

        service_class.return_value.list_files.return_value = []
        request = self.factory.post(f"/api/galleries/{self.gallery.pk}/sync/")
        force_authenticate(request, user=self.user)
        with override_settings(TASKS={"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}):
            response = GalleryViewSet.as_view({"post": "sync"})(request, pk=self.gallery.pk)
        self.assertEqual(response.status_code, 202)
        service_class.return_value.list_files.assert_called_once_with("folder")
        self.gallery.refresh_from_db()
        self.assertIsNotNone(self.gallery.last_synced_at)


class PublicGalleryTests(TestCase):
    def setUp(self):
        from ..models import Photo

        self.gallery = Gallery.objects.create(name="Public", slug="public-test", is_published=True)
        self.photo = Photo.objects.create(
            gallery=self.gallery,
            name="Photo",
            status="ready",
            preview="original.webp",
            thumbnail="thumb.webp",
            watermarked_preview="marked.webp",
        )
        self.factory = APIRequestFactory()

    def get_public(self, **headers):
        from django.urls import resolve

        request = self.factory.get("/api/galleries/public/public-test/", **headers)
        match = resolve("/api/galleries/public/public-test/")
        return match.func(request, **match.kwargs)

    def test_anonymous_can_read_published_gallery_and_photos(self):
        response = self.get_public()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["photos"]), 1)
        self.assertNotIn("clients", response.data)
        self.assertNotIn("source_file_id", response.data["photos"][0])

    def test_inactive_photo_is_hidden_from_public_gallery(self):
        self.photo.is_active = False
        self.photo.save(update_fields=["is_active"])

        response = self.get_public()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["photos"], [])

    def test_watermark_replaces_original_and_thumbnail(self):
        self.gallery.watermark_enabled = True
        self.gallery.save()
        photo = self.get_public().data["photos"][0]
        self.assertEqual(photo["preview"], photo["watermarked_preview"])
        self.assertEqual(photo["thumbnail"], photo["watermarked_preview"])
        self.assertNotIn("original.webp", photo["preview"])

    def test_draft_is_not_public(self):
        self.gallery.is_published = False
        self.gallery.save()
        self.assertEqual(self.get_public().status_code, 404)

    def test_private_requires_correct_code(self):
        from django.contrib.auth.hashers import make_password

        self.gallery.access_type = "private"
        self.gallery.access_code_hash = make_password("secret-code")
        self.gallery.save()
        self.assertEqual(self.get_public().status_code, 403)
        self.assertEqual(self.get_public(HTTP_X_GALLERY_ACCESS_CODE="secret-code").status_code, 200)
