import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from djmoney.money import Money
from rest_framework.test import APIClient

from apps.domains.client.models import Client
from apps.domains.gallery.models import Gallery, IncludedPhoto, Photo
from apps.domains.setup.models import Setup

from ..models import Order, OrderItem, OrderPhoto


@override_settings(PAYMENT_VARIANTS={"stripe": ("payments.stripe.StripeProviderV3", {"api_key": "test"})})
class PackageBalanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="balance-buyer", email="balance@example.com")
        self.other = get_user_model().objects.create_user(username="balance-other")
        self.buyer = Client.objects.create(user=self.user, email=self.user.email, name="Buyer")
        self.gallery = Gallery.objects.create(
            name="Balance",
            slug="balance",
            is_published=True,
            enable_sales=True,
            allow_individual_purchase=True,
            gallery_price=Money(100, "BRL"),
            default_photo_price=25,
        )
        self.photo = Photo.objects.create(
            gallery=self.gallery, name="first.jpg", status="ready", source_file_id="first", source_user=self.user
        )
        self.extra = Photo.objects.create(
            gallery=self.gallery, name="extra.jpg", status="ready", source_file_id="extra", source_user=self.user
        )
        Setup.objects.create(type="payment", provider="stripe", name="Stripe", is_active=True)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        gateway = patch(
            "apps.domains.commerce.services.order.create_checkout",
            return_value=("session", "https://checkout.stripe.com/test"),
        )
        self.gateway = gateway.start()
        self.addCleanup(gateway.stop)

    def paid_photo(self, amount=25, currency="BRL", status="paid"):
        order = Order.objects.create(
            client=self.buyer, payment_provider="stripe", status=status, total=Money(amount, currency)
        )
        OrderItem.objects.create(order=order, item_type="photo", photo=self.photo, unit_price=Money(amount, currency))
        OrderPhoto.objects.create(order=order, photo=self.photo)
        return order

    def checkout_package(self, request_id=None):
        return self.api.post(
            "/api/commerce/orders/checkout/",
            {"request_id": request_id or str(uuid.uuid4()), "gallery_id": str(self.gallery.pk)},
            format="json",
        )

    def test_package_subtracts_actual_paid_snapshot_and_delivers_complete_package(self):
        self.paid_photo(40)
        self.photo.price = Money(80, "BRL")
        self.photo.save()
        public = self.api.get("/api/galleries/public/balance/").data
        self.assertEqual(float(public["package_discount"]), 40)
        self.assertEqual(float(public["package_remaining"]), 60)
        result = self.checkout_package()
        self.assertEqual(result.status_code, 201, result.data)
        order = Order.objects.get(pk=result.data["id"])
        self.assertEqual(order.total, Money(60, "BRL"))
        self.assertEqual(order.items.get().unit_price, Money(60, "BRL"))
        self.assertEqual(order.order_photos.count(), 2)

    def test_refunds_different_currencies_and_other_users_are_not_credited(self):
        self.paid_photo(40, status="refunded")
        self.paid_photo(30, currency="USD")
        public = self.api.get("/api/galleries/public/balance/").data
        self.assertEqual(float(public["package_discount"]), 0)
        self.api.force_authenticate(self.other)
        self.assertEqual(float(self.api.get("/api/galleries/public/balance/").data["package_discount"]), 0)

    def test_fully_credited_package_is_free_and_idempotent(self):
        self.paid_photo(120)
        request_id = str(uuid.uuid4())
        response = self.checkout_package(request_id)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "paid")
        self.assertEqual(float(response.data["total"]), 0)
        self.gateway.assert_not_called()
        again = self.checkout_package(request_id)
        self.assertEqual(again.data["id"], response.data["id"])
        self.assertEqual(self.checkout_package().status_code, 400)

    def test_exhausted_allowance_still_allows_individual_extras(self):
        self.gallery.included_photo_mode = "client"
        self.gallery.included_photo_limit = 1
        self.gallery.allow_individual_purchase = False
        self.gallery.save()
        self.gallery.clients.add(self.buyer)
        IncludedPhoto.objects.create(gallery=self.gallery, photo=self.photo, user=self.user)
        public = self.api.get("/api/galleries/public/balance/").data
        self.assertEqual(public["included_remaining"], 0)
        self.assertTrue(public["allow_individual_purchase"])
        self.assertEqual(float(public["package_discount"]), 0)
        response = self.api.post(
            "/api/commerce/orders/checkout/",
            {"request_id": str(uuid.uuid4()), "photo_ids": [str(self.extra.pk)]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(float(response.data["total"]), 25)

    def test_included_photos_list_is_private_to_each_client(self):
        IncludedPhoto.objects.create(gallery=self.gallery, photo=self.photo, user=self.user)
        url = "/api/galleries/public/balance/included-photos/"
        self.assertEqual(self.api.get(url).data[0]["id"], str(self.photo.pk))
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get(url).data, [])
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(url).status_code, (401, 403))
