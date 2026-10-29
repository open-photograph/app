import io
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve
from djmoney.money import Money
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.domains.client.models import Client
from apps.domains.commerce.services import PaymentError, payment_status
from apps.domains.gallery.models import Gallery, Photo
from apps.domains.photographer.models import Photographer
from apps.domains.setup.models import Setup

from ..models import Order, OrderPhoto, Payment

TEST_PAYMENT_VARIANTS = {
    "stripe": ("payments.stripe.StripeProviderV3", {"api_key": "test-secret", "use_token": True}),
    "mercado_pago": ("payments.mercadopago.MercadoPagoProvider", {"access_token": "test-token", "sandbox": False}),
}


class NativePaymentsMixin:
    def setUp(self):
        super().setUp()
        from payments.core import PROVIDER_CACHE

        PROVIDER_CACHE.clear()

    def tearDown(self):
        from payments.core import PROVIDER_CACHE

        PROVIDER_CACHE.clear()
        super().tearDown()


@override_settings(PAYMENT_PROVIDER="stripe", PAYMENT_VARIANTS=TEST_PAYMENT_VARIANTS)
class PurchaseFlowTests(NativePaymentsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="buyer", email="buyer@example.com")
        self.other = get_user_model().objects.create_user(username="other", email="other@example.com")
        self.admin = get_user_model().objects.create_user(username="photographer", is_staff=True)
        Photographer.objects.create(user=self.admin)
        self.gallery = Gallery.objects.create(
            name="Gallery",
            slug="buy",
            is_published=True,
            enable_sales=True,
            allow_individual_purchase=True,
            gallery_price=Money(30, "BRL"),
        )
        self.photo = Photo.objects.create(
            gallery=self.gallery,
            name="original.jpg",
            status="ready",
            source_file_id="drive-id",
            source_user=self.admin,
            price=Money(10, "BRL"),
        )
        Setup.objects.create(name="Stripe", type="payment", provider="stripe")
        self.factory = APIRequestFactory()

    def call(self, path, method="get", data=None, user=None):
        request = getattr(self.factory, method)(path, data or {}, format="json")
        if user is not False:
            force_authenticate(request, user=user or self.user)
        match = resolve(path.split("?")[0])
        return match.func(request, **match.kwargs)

    def checkout(self, **payload):
        return self.call(
            "/api/commerce/orders/checkout/",
            "post",
            {"request_id": str(uuid.uuid4()), "photo_ids": [str(self.photo.pk)], **payload},
        )

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_checkout_uses_gallery_individual_default(self, create):
        self.gallery.default_photo_price = 15
        self.gallery.save()
        self.photo.price = None
        self.photo.save()
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get().total, Money(15, "BRL"))

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_checkout_uses_session_buyer_and_is_idempotent(self, create):
        key = str(uuid.uuid4())
        payload = {"request_id": key, "photo_ids": [str(self.photo.pk)], "client_id": str(uuid.uuid4())}
        first = self.call("/api/commerce/orders/checkout/", "post", payload)
        second = self.call("/api/commerce/orders/checkout/", "post", payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.get().client.user_id, self.user.pk)
        self.assertEqual(Order.objects.get().total, Money(10, "BRL"))
        self.assertEqual(first.data["photos"][0]["download_url"], None)
        create.assert_called_once()

    @patch("apps.domains.commerce.services.order.create_checkout")
    def test_long_gateway_url_is_saved_without_aborting_transaction(self, create):
        url = "https://checkout.stripe.com/c/pay/" + "x" * 900
        create.return_value = ("session-long-url", url)
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["checkout_url"], url)
        self.assertEqual(Order.objects.get().checkout_url, url)
        self.assertEqual(Order.objects.count(), 1)

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("preference", "https://mercadopago.com/test"),
    )
    def test_checkout_uses_provider_selected_in_setup(self, create):
        selected = self.call(
            "/api/setup/",
            "post",
            {"name": "Mercado Pago", "type": "payment", "provider": "mercado_pago"},
            user=self.admin,
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(self.checkout().status_code, 201)
        self.assertEqual(Order.objects.get().payment_provider, "mercado_pago")

    def test_anonymous_checkout_rejected(self):
        response = self.call(
            "/api/commerce/orders/checkout/",
            "post",
            {"request_id": str(uuid.uuid4()), "photo_ids": [str(self.photo.pk)]},
            user=False,
        )
        self.assertIn(response.status_code, [401, 403])
        self.assertFalse(Order.objects.exists())

    @patch("apps.domains.commerce.services.order.create_checkout", side_effect=PaymentError("Unavailable"))
    def test_gateway_failure_rolls_back_order(self, create):
        self.assertEqual(self.checkout().status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_draft_and_invalid_selection_rejected(self):
        self.gallery.is_published = False
        self.gallery.save()
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(self.checkout(photo_ids=[str(self.photo.pk), str(self.photo.pk)]).status_code, 400)
        self.assertEqual(self.checkout(gallery_id=str(self.gallery.pk)).status_code, 400)

    def test_inactive_photo_cannot_be_purchased(self):
        self.photo.is_active = False
        self.photo.save(update_fields=["is_active"])

        self.assertEqual(self.checkout().status_code, 400)

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_whole_gallery_excludes_inactive_photos(self, create):
        self.photo.is_active = False
        self.photo.save(update_fields=["is_active"])
        active_photo = Photo.objects.create(
            gallery=self.gallery,
            name="active.jpg",
            status="ready",
            source_file_id="active",
        )

        response = self.call(
            "/api/commerce/orders/checkout/",
            "post",
            {"request_id": str(uuid.uuid4()), "gallery_id": str(self.gallery.pk)},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(list(OrderPhoto.objects.values_list("photo_id", flat=True)), [active_photo.pk])

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_whole_gallery_snapshots_current_photos(self, create):
        response = self.call(
            "/api/commerce/orders/checkout/",
            "post",
            {"request_id": str(uuid.uuid4()), "gallery_id": str(self.gallery.pk)},
        )
        self.assertEqual(response.status_code, 201)
        Photo.objects.create(gallery=self.gallery, name="later.jpg", status="ready", source_file_id="later")
        self.assertEqual(OrderPhoto.objects.count(), 1)
        self.assertEqual(Order.objects.get().total, Money(30, "BRL"))

    def paid_order(self, status="paid"):
        client = Client.objects.create(user=self.user, email=self.user.email, name="Buyer")
        order = Order.objects.create(client=client, payment_provider="offline", status=status, total=Money(10, "BRL"))
        OrderPhoto.objects.create(order=order, photo=self.photo)
        return order

    @patch("apps.domains.commerce.services.download.GoogleDriveService")
    def test_download_preserves_jpeg_bytes_and_uses_photographer_storage(self, service):
        order = self.paid_order()
        original = b"\xff\xd8\xfforiginal-bytes-no-recompression"
        service.return_value.open_file.return_value = io.BytesIO(original)
        response = self.call(f"/api/commerce/orders/{order.pk}/download/{self.photo.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), original)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        service.assert_called_once_with(self.admin)
        service.return_value.open_file.assert_called_once_with("drive-id")
        service.return_value.open_file.return_value.close()

    @patch("apps.domains.commerce.services.download.GoogleDriveService")
    def test_download_uses_importing_account_instead_of_photographer_account(self, service):
        order = self.paid_order()
        self.photo.source_user = self.other
        self.photo.save(update_fields=["source_user"])
        service.return_value.open_file.return_value = io.BytesIO(b"\xff\xd8\xfforiginal")
        response = self.call(f"/api/commerce/orders/{order.pk}/download/{self.photo.pk}/")
        self.assertEqual(response.status_code, 200)
        service.assert_called_once_with(self.other)
        service.return_value.open_file.return_value.close()

    @patch("apps.domains.commerce.services.download.GoogleDriveService")
    def test_pending_and_other_users_cannot_download(self, service):
        order = self.paid_order(status="pending")
        path = f"/api/commerce/orders/{order.pk}/download/{self.photo.pk}/"
        self.assertEqual(self.call(path).status_code, 403)
        self.assertEqual(self.call(path, user=self.other).status_code, 404)
        service.assert_not_called()

    def test_cannot_download_photo_not_in_order(self):
        order = self.paid_order()
        self.assertEqual(self.call(f"/api/commerce/orders/{order.pk}/download/{uuid.uuid4()}/").status_code, 404)
        self.assertEqual(self.call("/api/commerce/orders/mine/?gallery=buy", user=self.other).data["count"], 0)
        self.assertEqual(self.call("/api/commerce/orders/mine/?gallery=buy").data["count"], 1)

    def test_only_staff_can_manually_mark_paid(self):
        order = self.paid_order(status="pending")
        path = f"/api/commerce/orders/{order.pk}/mark_paid/"
        self.assertEqual(self.call(path, "post").status_code, 403)
        self.assertEqual(self.call(path, "post", user=self.admin).status_code, 200)

    @patch("apps.domains.commerce.services.order.payment_status", return_value="paid")
    def test_gateway_confirmation_unlocks_download(self, verify):
        order = self.paid_order(status="pending")
        order.payment_reference = "reference"
        order.save()
        response = self.call(f"/api/commerce/orders/{order.pk}/refresh/", "post")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "paid")
        self.assertIsNotNone(response.data["photos"][0]["download_url"])
        order.refresh_from_db()
        self.assertIsNotNone(order.paid_at)

    @patch("apps.domains.commerce.services.order.payment_status", return_value="refunded")
    def test_refund_revokes_download(self, verify):
        order = self.paid_order()
        order.payment_reference = "reference"
        order.save()
        response = self.call(f"/api/commerce/orders/{order.pk}/download/{self.photo.pk}/")
        self.assertEqual(response.status_code, 403)

    @patch("payments.stripe.providers.stripe.checkout.Session.retrieve")
    def test_stripe_status_uses_library(self, retrieve):
        from stripe import StripeObject

        order = self.paid_order(status="pending")
        order.payment_provider = "stripe"
        order.payment_reference = "session"
        order.save()
        retrieve.return_value = StripeObject.construct_from({"payment_status": "paid"}, "test")
        self.assertEqual(payment_status(order), "paid")
        retrieve.assert_called_once_with("session")
        retrieve.return_value = StripeObject.construct_from({"payment_status": "unpaid"}, "test")
        self.assertEqual(payment_status(order), "paid")
        self.assertEqual(Payment.objects.get(order=order).status, "confirmed")

    @patch("payments.mercadopago.SDK")
    def test_mercado_pago_status_uses_library_collection_processing(self, sdk):
        order = self.paid_order(status="pending")
        order.payment_provider = "mercado_pago"
        order.payment_reference = "preference"
        order.save()
        client = sdk.return_value
        client.preference.return_value.get.return_value = {
            "status": 200,
            "response": {"external_reference": "reference"},
        }
        client.payment.return_value.search.return_value = {
            "status": 200,
            "response": {"results": [{"id": 123}]},
        }
        for upstream, expected in [
            ("approved", "paid"),
            ("pending", "pending"),
            ("refunded", "refunded"),
            ("rejected", "failed"),
        ]:
            client.payment.return_value.get.return_value = {"status": 200, "response": {"status": upstream}}
            self.assertEqual(payment_status(order), expected)
        client.payment.return_value.search.assert_called_with({"external_reference": "reference"})
        client.payment.return_value.get.assert_called_with(123)

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_other_user_cannot_reuse_checkout_request_id(self, create):
        key = str(uuid.uuid4())
        self.checkout(request_id=key)
        response = self.call(
            "/api/commerce/orders/checkout/",
            "post",
            {"request_id": key, "photo_ids": [str(self.photo.pk)]},
            user=self.other,
        )
        self.assertEqual(response.status_code, 400)

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_duplicate_pending_purchase_rejected(self, create):
        self.assertEqual(self.checkout().status_code, 201)
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    @patch(
        "apps.domains.commerce.services.order.create_checkout",
        return_value=("session", "https://checkout.stripe.com/test"),
    )
    def test_mixed_currencies_are_rejected(self, create):
        other = Photo.objects.create(
            gallery=self.gallery, name="Other", source_file_id="other", status="ready", price=Money(10, "USD")
        )
        self.assertEqual(self.checkout(photo_ids=[str(self.photo.pk), str(other.pk)]).status_code, 400)
        create.assert_not_called()

    def test_photo_price_can_be_configured_by_photographer(self):
        response = self.call(
            f"/api/photos/{self.photo.pk}/", "patch", {"price": "12.34", "price_currency": "BRL"}, user=self.admin
        )
        self.assertEqual(response.status_code, 200)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.price, Money("12.34", "BRL"))

    def test_setup_does_not_accept_credentials(self):
        response = self.call(
            "/api/setup/",
            "post",
            {"name": "Stripe", "type": "payment", "provider": "stripe", "credentials": {"secret_key": "new-secret"}},
            user=self.admin,
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(PAYMENT_PROVIDER="", PAYMENT_VARIANTS={})
    def test_checkout_requires_environment_configuration(self):
        self.assertEqual(self.checkout().status_code, 400)
        self.assertFalse(Order.objects.exists())


class BuyerSignupTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signup_creates_buyer_session(self):
        response = self.client.post(
            "/api/browser/v1/auth/signup",
            {"email": "new-buyer@example.com", "password": "VeryStrongBuyerPassword-3920"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["meta"]["is_authenticated"])
        self.assertFalse(get_user_model().objects.get(email="new-buyer@example.com").is_staff)


@override_settings(PAYMENT_PROVIDER="stripe", PAYMENT_VARIANTS=TEST_PAYMENT_VARIANTS)
class PaymentBackendTests(NativePaymentsMixin, TestCase):
    def make_order(self, provider):
        client = Client.objects.create(name="Buyer", email="buyer@example.com")
        return Order.objects.create(
            client=client,
            payment_provider=provider,
            total=Money("10", "BRL"),
        )

    def test_native_factory_uses_environment_settings(self):
        from payments.core import provider_factory
        from payments.mercadopago import MercadoPagoProvider
        from payments.stripe import StripeProviderV3

        self.assertIs(type(provider_factory("stripe")), StripeProviderV3)
        self.assertEqual(provider_factory("stripe").api_key, "test-secret")
        self.assertIs(type(provider_factory("mercado_pago")), MercadoPagoProvider)

    @patch("payments.mercadopago.SDK")
    def test_native_checkout_persists_metadata_and_callback_confirms_order(self, sdk):
        from payments import get_payment_model
        from payments.models import BasePayment

        from apps.domains.commerce.services import create_checkout

        order = self.make_order("mercado_pago")
        sdk.return_value.preference.return_value.create.return_value = {
            "status": 201,
            "response": {"id": "preference", "init_point": "https://mercadopago.com/test"},
        }
        self.assertEqual(create_checkout(order, "demo"), ("preference", "https://mercadopago.com/test"))
        payment = Payment.objects.get(order=order)
        self.assertIs(get_payment_model(), Payment)
        self.assertIsInstance(payment, BasePayment)
        self.assertTrue(payment.attrs.external_reference)
        self.assertEqual(payment.transaction_id, "preference")
        self.assertEqual(payment.get_success_url(), payment.get_failure_url())
        self.assertIn("/g/demo/purchases", payment.get_success_url())
        self.assertEqual(sdk.return_value.preference.return_value.create.call_count, 1)
        # Reusing the payment loads the existing preference instead of creating another.
        sdk.return_value.preference.return_value.get.return_value = {
            "status": 200,
            "response": {"id": "preference", "init_point": "https://mercadopago.com/test"},
        }
        create_checkout(order, "demo")
        self.assertEqual(sdk.return_value.preference.return_value.create.call_count, 1)
        sdk.return_value.payment.return_value.get.return_value = {
            "status": 200,
            "response": {"status": "approved"},
        }
        response = self.client.post(
            payment.get_process_url(),
            {"topic": "payment", "resource": "/v1/payments/123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, "confirmed")
        self.assertEqual(order.status, "paid")
        self.assertIsNotNone(order.paid_at)
        payment.change_status("refunded")
        order.refresh_from_db()
        self.assertEqual(order.status, "refunded")

    @patch("payments.stripe.providers.stripe.checkout.Session.create")
    def test_signed_stripe_callback_uses_native_route(self, create_session):
        import hashlib
        import hmac
        import json
        import time

        from django.conf import settings
        from django.urls import reverse
        from stripe import SignatureVerificationError

        from apps.domains.commerce.services import create_checkout

        order = self.make_order("stripe")
        create_session.return_value = {"id": "session", "url": "https://checkout.stripe.com/test"}
        endpoint_secret = "whsec_test"
        variants = dict(settings.PAYMENT_VARIANTS)
        variants["stripe"] = (
            variants["stripe"][0],
            {"api_key": "test-secret", "use_token": True, "endpoint_secret": endpoint_secret},
        )
        with override_settings(PAYMENT_VARIANTS=variants):
            create_checkout(order, "demo")
            payment = Payment.objects.get(order=order)
            body = json.dumps(
                {
                    "id": "evt_test",
                    "object": "event",
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "session",
                            "object": "checkout.session",
                            "status": "complete",
                            "payment_status": "paid",
                            "client_reference_id": payment.token,
                        }
                    },
                }
            )
            timestamp = str(int(time.time()))
            signature = hmac.new(endpoint_secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
            url = reverse("static_process_payment", kwargs={"variant": "stripe"})
            response = self.client.post(
                url,
                body,
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
            )
            self.assertEqual(response.status_code, 200)
            order.refresh_from_db()
            self.assertEqual(order.status, "paid")
            self.assertIsNotNone(order.paid_at)
            # The same native endpoint rejects an invalid signature.
            with self.assertRaises(SignatureVerificationError):
                self.client.post(url, body, content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=invalid")

    @patch("payments.stripe.StripeProviderV3.create_session")
    def test_checkout_uses_library_backend(self, create_session):

        from apps.domains.commerce.services import create_checkout

        order = self.make_order("stripe")
        create_session.return_value = {"id": "session", "url": "https://checkout.stripe.com/test"}
        self.assertEqual(create_checkout(order, "demo"), ("session", "https://checkout.stripe.com/test"))
        payment = create_session.call_args.args[0]
        self.assertEqual(payment.order_id, order.pk)
        self.assertEqual(payment.total, order.total.amount)

    @patch("payments.mercadopago.MercadoPagoProvider.get_or_create_preference")
    def test_mercado_pago_checkout_uses_library_backend(self, preference):

        from apps.domains.commerce.services import create_checkout

        order = self.make_order("mercado_pago")

        def get_preference(payment):
            payment.transaction_id = "preference"
            payment.attrs.external_reference = "reference"
            payment.save()
            return {"id": "preference", "init_point": "https://mercadopago.com/test"}

        preference.side_effect = get_preference
        self.assertEqual(create_checkout(order, "demo"), ("preference", "https://mercadopago.com/test"))


class PaymentRegistryTests(NativePaymentsMixin, SimpleTestCase):
    @override_settings(PAYMENT_VARIANTS={"custom": ("example.Backend", {"api_key": "secret", "sandbox": True})})
    @patch("payments.core.import_string")
    def test_custom_backend_uses_native_factory(self, import_string):
        from payments.core import provider_factory

        self.assertIs(provider_factory("custom"), import_string.return_value.return_value)
        import_string.assert_called_once_with("example.Backend")
        import_string.return_value.assert_called_once_with(api_key="secret", sandbox=True)


class PaymentFailureTests(SimpleTestCase):
    @patch("apps.domains.commerce.services.payment.get_order_payment")
    def test_library_error_does_not_expose_credentials(self, factory):
        from types import SimpleNamespace

        from apps.domains.commerce.services import create_checkout

        secret = "sk_test_private"
        factory.side_effect = RuntimeError(secret)
        with self.assertRaises(PaymentError) as raised:
            create_checkout(SimpleNamespace(payment_provider="stripe"), "demo")
        self.assertNotIn(secret, str(raised.exception))
