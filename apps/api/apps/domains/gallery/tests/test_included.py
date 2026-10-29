import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from djmoney.money import Money
from rest_framework.test import APIClient

from apps.domains.client.models import Client

from ..models import Gallery, IncludedPhoto, Photo


class IncludedPhotoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="included", email="included@example.com")
        self.other = get_user_model().objects.create_user(username="included-other", email="other@example.com")
        self.admin = get_user_model().objects.create_user(username="included-admin", is_staff=True)
        self.gallery = Gallery.objects.create(
            name="Included",
            slug="included",
            is_published=True,
            included_photo_mode="client",
            included_photo_limit=1,
            default_photo_price=20,
            enable_sales=True,
            allow_individual_purchase=True,
        )
        self.buyer = Client.objects.create(user=self.user, name="Buyer", email=self.user.email)
        self.gallery.clients.add(self.buyer)
        self.photo = Photo.objects.create(
            gallery=self.gallery,
            name="portrait.jpg",
            status="ready",
            source_file_id="original-1",
            source_user=self.admin,
        )
        self.extra = Photo.objects.create(
            gallery=self.gallery,
            name="extra.jpg",
            status="ready",
            source_file_id="original-2",
            source_user=self.admin,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.claim_url = "/api/galleries/public/included/included/"

    def claim(self, photo=None, **headers):
        return self.api.post(self.claim_url, {"photo_id": str((photo or self.photo).pk)}, format="json", **headers)

    def public(self):
        return self.api.get("/api/galleries/public/included/").data

    def test_claim_is_idempotent_and_quota_cannot_be_exceeded(self):
        self.assertEqual(self.public()["included_remaining"], 1)
        self.assertEqual(self.claim().status_code, 200)
        self.assertEqual(self.claim().status_code, 200)
        self.assertEqual(self.claim(self.extra).status_code, 400)
        self.assertEqual(IncludedPhoto.objects.count(), 1)
        data = self.public()
        self.assertEqual(data["included_remaining"], 0)
        photos = {item["id"]: item for item in data["photos"]}
        self.assertTrue(photos[str(self.photo.pk)]["can_download_original"])
        self.assertIsNone(photos[str(self.photo.pk)]["price"])
        self.assertEqual(photos[str(self.extra.pk)]["price"], "20.00")

    def test_only_assigned_clients_get_a_separate_allowance(self):
        self.assertEqual(self.claim().status_code, 200)
        self.api.force_authenticate(self.other)
        self.assertFalse(self.public()["included_eligible"])
        self.assertEqual(self.claim().status_code, 403)
        other_buyer = Client.objects.create(user=self.other, name="Other", email=self.other.email)
        self.gallery.clients.add(other_buyer)
        self.assertEqual(self.claim(self.extra).status_code, 200)
        self.assertEqual(IncludedPhoto.objects.count(), 2)
        self.api.force_authenticate(None)
        self.assertIn(self.claim().status_code, (401, 403))

    def test_private_gallery_requires_code_and_rejects_foreign_or_inactive_photos(self):
        self.gallery.access_type = "private"
        self.gallery.access_code_hash = make_password("secret")
        self.gallery.save()
        self.assertEqual(self.claim().status_code, 403)
        self.photo.is_active = False
        self.photo.save()
        self.assertEqual(self.claim(HTTP_X_GALLERY_ACCESS_CODE="secret").status_code, 404)
        foreign = Gallery.objects.create(name="Foreign", slug="foreign")
        self.extra.gallery = foreign
        self.extra.save()
        self.assertEqual(self.claim(self.extra, HTTP_X_GALLERY_ACCESS_CODE="secret").status_code, 404)
        self.assertFalse(IncludedPhoto.objects.exists())

    @patch(
        "apps.domains.commerce.services.download.open_original", side_effect=lambda photo: io.BytesIO(b"jpeg-original")
    )
    def test_original_requires_entitlement_and_survives_limit_changes(self, open_original):
        url = f"/api/galleries/public/included/photos/{self.photo.pk}/original/"
        self.assertEqual(self.api.get(url).status_code, 403)
        self.claim()
        self.gallery.included_photo_mode = "none"
        self.gallery.included_photo_limit = 0
        self.gallery.save()
        response = self.api.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"jpeg-original")
        self.assertIn("portrait.jpg", response["Content-Disposition"])
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get(url).status_code, 403)
        self.assertEqual(open_original.call_count, 1)

    @patch(
        "apps.domains.commerce.services.download.open_original", side_effect=lambda photo: io.BytesIO(b"free-original")
    )
    def test_photographer_marks_free_original_without_changing_other_prices(self, open_original):
        self.gallery.included_photo_mode = "photographer"
        self.gallery.save()
        self.api.force_authenticate(self.admin)
        response = self.api.patch(f"/api/photos/{self.photo.pk}/", {"is_included": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.api.force_authenticate(None)
        data = self.public()
        photo = next(item for item in data["photos"] if item["id"] == str(self.photo.pk))
        self.assertIsNone(photo["price"])
        self.assertTrue(photo["can_download_original"])
        self.assertEqual(
            self.api.get(f"/api/galleries/public/included/photos/{self.extra.pk}/original/").status_code, 403
        )
        response = self.api.get(f"/api/galleries/public/included/photos/{self.photo.pk}/original/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"free-original")
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.effective_price, Money(20, "USD"))

    def test_quota_requires_positive_limit(self):
        self.api.force_authenticate(self.admin)
        response = self.api.patch(f"/api/galleries/{self.gallery.pk}/", {"included_photo_limit": 0}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_client_mode_requires_linked_clients_on_create_and_update(self):
        self.api.force_authenticate(self.admin)
        payload = {
            "name": "New gallery",
            "default_photo_price": "25.00",
            "slug": "new-included",
            "enable_sales": True,
            "allow_individual_purchase": True,
            "included_photo_mode": "client",
            "included_photo_limit": 15,
        }
        response = self.api.post("/api/galleries/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.api.post("/api/galleries/", {**payload, "clients": [str(self.buyer.pk)]}, format="json")
        self.assertEqual(response.status_code, 201)
        url = f"/api/galleries/{self.gallery.pk}/"
        self.assertEqual(self.api.patch(url, {"clients": []}, format="json").status_code, 400)
        self.assertEqual(self.api.patch(url, {"name": "Updated"}, format="json").status_code, 200)

    def test_disabling_extra_sales_preserves_delivery(self):
        self.api.force_authenticate(self.admin)
        response = self.api.patch(f"/api/galleries/{self.gallery.pk}/", {"enable_sales": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.gallery.refresh_from_db()
        self.assertEqual(self.gallery.included_photo_mode, "client")
        self.assertEqual(self.gallery.included_photo_limit, 1)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.claim().status_code, 200)

    def test_missing_original_does_not_consume_allowance(self):
        self.photo.source_file_id = ""
        self.photo.save()
        self.assertEqual(self.claim().status_code, 400)
        self.assertFalse(IncludedPhoto.objects.exists())

    @patch("apps.domains.commerce.services.download.open_original", side_effect=lambda photo: io.BytesIO(b"original"))
    def test_all_included_disables_sales_and_releases_every_original(self, open_original):
        self.api.force_authenticate(self.admin)
        response = self.api.patch(
            f"/api/galleries/{self.gallery.pk}/", {"included_photo_mode": "all", "enable_sales": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.gallery.refresh_from_db()
        self.assertFalse(self.gallery.enable_sales)
        self.assertFalse(self.gallery.allow_individual_purchase)
        self.api.force_authenticate(None)
        data = self.public()
        for photo in data["photos"]:
            self.assertTrue(photo["can_download_original"])
            self.assertIsNone(photo["price"])
            response = self.api.get(f"/api/galleries/public/included/photos/{photo['id']}/original/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"original")
        self.gallery.access_type = "private"
        self.gallery.access_code_hash = make_password("secret")
        self.gallery.save()
        self.assertEqual(
            self.api.get(f"/api/galleries/public/included/photos/{self.photo.pk}/original/").status_code, 403
        )

    def test_switching_off_allowance_does_not_allow_new_choices(self):
        self.claim()
        self.gallery.included_photo_mode = "none"
        self.gallery.save()
        self.assertEqual(self.claim(self.extra).status_code, 403)
        self.assertEqual(IncludedPhoto.objects.count(), 1)
