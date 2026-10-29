from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from ..models import WatermarkAsset
from ..views.watermark import WatermarkAssetViewSet


class WatermarkManagementTests(TestCase):
    def test_multiple_assets_can_be_created_and_default_can_be_changed(self):
        user = get_user_model().objects.create_user(username="watermark-admin", is_staff=True)
        factory = APIRequestFactory()
        for name, is_default in (("Signature", True), ("Logo", False)):
            request = factory.post(
                "/api/commerce/watermarks/",
                {
                    "name": name,
                    "style": "text_diagonal",
                    "text": name,
                    "is_default": is_default,
                },
                format="json",
            )
            force_authenticate(request, user)
            response = WatermarkAssetViewSet.as_view({"post": "create"})(request)
            self.assertEqual(response.status_code, 201)
        self.assertEqual(WatermarkAsset.objects.count(), 2)
        second = WatermarkAsset.objects.get(name="Logo")
        request = factory.patch(f"/api/commerce/watermarks/{second.pk}/", {"is_default": True}, format="json")
        force_authenticate(request, user)
        response = WatermarkAssetViewSet.as_view({"patch": "partial_update"})(request, pk=second.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WatermarkAsset.objects.get(is_default=True).pk, second.pk)
