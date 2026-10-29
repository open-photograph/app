from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from ..models import Gallery, GalleryTag
from ..views.gallery import GalleryTagViewSet


class GalleryTagUsageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tags-admin", is_staff=True)
        self.factory = APIRequestFactory()

    def list_tags(self):
        request = self.factory.get("/api/tags/")
        force_authenticate(request, user=self.user)
        response = GalleryTagViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
        return {tag["title"]: tag["gallery_count"] for tag in response.data["results"]}

    def test_counts_all_associated_galleries_and_unused_tags(self):
        used = GalleryTag.objects.create(title="Wedding", slug="wedding")
        GalleryTag.objects.create(title="Unused", slug="unused")
        draft = Gallery.objects.create(name="Draft", slug="draft")
        published = Gallery.objects.create(name="Published", slug="published", is_published=True)
        draft.tags.add(used)
        published.tags.add(used)
        self.assertEqual(self.list_tags(), {"Wedding": 2, "Unused": 0})

        draft.tags.remove(used)
        self.assertEqual(self.list_tags()["Wedding"], 1)
        published.delete()
        self.assertEqual(self.list_tags()["Wedding"], 0)

    def test_creating_a_tag_returns_zero_usage(self):
        request = self.factory.post("/api/tags/", {"title": "New", "slug": "new"}, format="json")
        force_authenticate(request, user=self.user)
        response = GalleryTagViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["gallery_count"], 0)
