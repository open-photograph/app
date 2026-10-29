from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import Gallery, GallerySelection, Photo, PhotoComment, PhotoLike


class GalleryFeedbackTests(TestCase):
    def test_admin_can_save_interaction_settings(self):
        user = get_user_model().objects.create_user(username="config-admin", is_staff=True)
        self.client.force_authenticate(user)
        response = self.client.patch(
            f"/api/galleries/{self.gallery.pk}/",
            {
                "allow_likes": False,
                "allow_comments": False,
                "allow_selection": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.gallery.refresh_from_db()
        self.assertFalse(self.gallery.allow_likes)
        self.assertFalse(self.gallery.allow_comments)
        self.assertFalse(self.gallery.allow_selection)

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="client-user", first_name="Cliente")
        self.client.force_authenticate(self.user)
        self.gallery = Gallery.objects.create(
            name="Ensaio",
            slug="ensaio",
            is_published=True,
            allow_likes=True,
            allow_comments=True,
            allow_selection=True,
        )
        self.photo = Photo.objects.create(gallery=self.gallery, name="Retrato", status="ready")
        self.other_gallery = Gallery.objects.create(name="Outra", slug="outra", is_published=True)
        self.other_photo = Photo.objects.create(gallery=self.other_gallery, name="Outra", status="ready")

    def post(self, action, payload, **headers):
        return self.client.post(f"/api/galleries/public/ensaio/{action}/", payload, format="json", **headers)

    def selection_payload(self, **overrides):
        return {"name": "Cliente", "email": "cliente@example.com", "photo_ids": [str(self.photo.pk)], **overrides}

    def test_likes_are_idempotent_and_can_be_removed(self):
        payload = {"photo_id": str(self.photo.pk), "liked": True}
        self.assertEqual(self.post("like", payload).status_code, 200)
        self.assertEqual(self.post("like", payload).status_code, 200)
        self.assertEqual(PhotoLike.objects.count(), 1)
        data = self.client.get("/api/galleries/public/ensaio/feedback/").json()
        self.assertEqual(data["liked_photo_ids"], [str(self.photo.pk)])
        self.assertEqual(self.post("like", {**payload, "liked": False}).status_code, 200)
        self.assertFalse(PhotoLike.objects.exists())

    def test_social_comments_are_shared_but_selection_is_private(self):
        response = self.post("comment", {"photo_id": str(self.photo.pk), "name": "Cliente", "text": "Gostei!"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post("selection", self.selection_payload()).status_code, 201)
        own = self.client.get("/api/galleries/public/ensaio/feedback/").json()
        self.assertEqual(len(own["comments"]), 1)
        self.assertEqual(len(own["selections"]), 1)
        other = APIClient().get("/api/galleries/public/ensaio/feedback/").json()
        self.assertEqual(len(other["comments"]), 1)
        self.assertEqual(other["comments"][0]["name"], "Cliente")
        self.assertEqual(other["selections"], [])
        self.assertNotIn("visitor", own["comments"][0])

    def test_disabled_features_reject_writes(self):
        self.gallery.allow_likes = False
        self.gallery.allow_comments = False
        self.gallery.allow_selection = False
        self.gallery.save()
        for action, payload in (
            ("like", {"photo_id": str(self.photo.pk), "liked": True}),
            ("comment", {"photo_id": str(self.photo.pk), "name": "Cliente", "text": "Olá"}),
            ("selection", self.selection_payload()),
        ):
            with self.subTest(action=action):
                self.assertEqual(self.post(action, payload).status_code, 403)
        self.assertFalse(PhotoLike.objects.exists())
        self.assertFalse(PhotoComment.objects.exists())
        self.assertFalse(GallerySelection.objects.exists())

    def test_selection_rejects_empty_invalid_or_foreign_photos(self):
        for ids in ([], [str(self.other_photo.pk)], ["invalid"]):
            with self.subTest(ids=ids):
                self.assertEqual(self.post("selection", self.selection_payload(photo_ids=ids)).status_code, 400)
        self.photo.status = "processing"
        self.photo.save()
        self.assertEqual(self.post("selection", self.selection_payload()).status_code, 400)
        self.assertFalse(GallerySelection.objects.exists())

    def test_like_and_comment_cannot_target_another_gallery(self):
        self.assertEqual(self.post("like", {"photo_id": str(self.other_photo.pk), "liked": True}).status_code, 404)
        self.assertEqual(
            self.post(
                "comment",
                {
                    "photo_id": str(self.other_photo.pk),
                    "name": "Cliente",
                    "text": "Olá",
                },
            ).status_code,
            404,
        )

    def test_private_gallery_requires_code_for_read_and_write(self):
        self.gallery.access_type = "private"
        self.gallery.access_code_hash = make_password("secret-code")
        self.gallery.save()
        self.assertEqual(self.client.get("/api/galleries/public/ensaio/feedback/").status_code, 403)
        self.assertEqual(self.post("selection", self.selection_payload()).status_code, 403)
        self.assertEqual(
            self.post("selection", self.selection_payload(), HTTP_X_GALLERY_ACCESS_CODE="secret-code").status_code, 201
        )

    def test_unpublished_gallery_rejects_feedback(self):
        self.gallery.is_published = False
        self.gallery.save()
        self.assertEqual(self.post("selection", self.selection_payload()).status_code, 404)

    def test_admin_can_read_feedback_but_anonymous_cannot(self):
        self.post("selection", self.selection_payload())
        self.post("like", {"photo_id": str(self.photo.pk), "liked": True})
        url = f"/api/galleries/{self.gallery.pk}/feedback/"
        self.assertIn(self.client.get(url).status_code, (401, 403))
        user = get_user_model().objects.create_user(username="photographer", is_staff=True)
        self.client.force_authenticate(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["selections"][0]["photos"][0]["name"], "Retrato")
        self.assertEqual(response.data["likes"][0]["count"], 1)

    def test_anonymous_writes_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            "/api/galleries/public/ensaio/like/", {"photo_id": str(self.photo.pk), "liked": True}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        client.force_login(self.user)
        client.cookies["csrftoken"] = "a" * 32
        response = client.post(
            "/api/galleries/public/ensaio/like/",
            {"photo_id": str(self.photo.pk), "liked": True},
            format="json",
            HTTP_X_CSRFTOKEN="a" * 32,
        )
        self.assertEqual(response.status_code, 200)

    def test_anonymous_cannot_like_or_comment_even_with_csrf(self):
        client = APIClient()
        for action, payload in (
            ("like", {"photo_id": str(self.photo.pk), "liked": True}),
            ("comment", {"photo_id": str(self.photo.pk), "text": "Hello"}),
        ):
            self.assertIn(
                client.post(f"/api/galleries/public/ensaio/{action}/", payload, format="json").status_code, (401, 403)
            )
        self.assertFalse(PhotoLike.objects.exists())
        self.assertFalse(PhotoComment.objects.exists())

    def test_likes_follow_account_across_sessions_and_are_photo_specific(self):
        self.post("like", {"photo_id": str(self.photo.pk), "liked": True})
        other_browser = APIClient()
        other_browser.force_authenticate(self.user)
        response = other_browser.get("/api/galleries/public/ensaio/feedback/")
        self.assertEqual(response.data["liked_photo_ids"], [self.photo.pk])
        self.assertEqual(response.data["like_counts"][str(self.photo.pk)], 1)
        self.assertEqual(PhotoLike.objects.get().user, self.user)
        other_user = get_user_model().objects.create_user(username="second-user")
        other_browser.force_authenticate(other_user)
        self.assertEqual(other_browser.get("/api/galleries/public/ensaio/feedback/").data["liked_photo_ids"], [])

    def test_comment_uses_account_name_and_targets_one_photo(self):
        response = self.post("comment", {"photo_id": str(self.photo.pk), "name": "Fake", "text": "Beautiful"})
        self.assertEqual(response.status_code, 201)
        comment = PhotoComment.objects.get()
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.name, "Cliente")
        self.assertEqual(comment.photo, self.photo)

    def test_legacy_comments_do_not_become_public(self):
        import uuid

        PhotoComment.objects.create(photo=self.photo, visitor=uuid.uuid4(), name="Private", text="Private")
        self.assertEqual(APIClient().get("/api/galleries/public/ensaio/feedback/").data["comments"], [])

    def test_public_gallery_exposes_feature_settings(self):
        response = self.client.get("/api/galleries/public/ensaio/")
        self.assertEqual(response.status_code, 200)
        for feature in ("allow_likes", "allow_comments", "allow_selection"):
            self.assertTrue(response.data[feature])
