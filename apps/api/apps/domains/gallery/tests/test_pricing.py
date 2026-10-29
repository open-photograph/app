from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money
from rest_framework.test import APIClient

from ..models import Gallery, Photo
from ..serialzers.gallery import GallerySerializer


class GalleryPricingTests(TestCase):
    def setUp(self):
        self.gallery = Gallery.objects.create(
            name="Pricing",
            slug="pricing",
            is_published=True,
            enable_sales=True,
            allow_individual_purchase=True,
            default_photo_price=Decimal("15.00"),
            gallery_price_currency="BRL",
        )
        self.photo = Photo.objects.create(gallery=self.gallery, name="Photo", status="ready")

    def test_public_photo_inherits_default_price_and_currency(self):
        photo = APIClient().get("/api/galleries/public/pricing/").data["photos"][0]
        self.assertEqual(photo["price"], "15.00")
        self.assertEqual(photo["price_currency"], "BRL")
        self.assertIsNone(self.photo.price)

    def test_photo_override_wins_and_clearing_restores_default(self):
        self.photo.price = Money(25, "USD")
        self.assertEqual(self.photo.effective_price, Money(25, "USD"))
        self.photo.price = None
        self.assertEqual(self.photo.effective_price, Money(15, "BRL"))

    def test_default_price_must_be_positive(self):
        serializer = GallerySerializer(self.gallery, data={"default_photo_price": "0.00"}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_photo_price", serializer.errors)
