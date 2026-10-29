from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.domains.client.models import Client
from apps.domains.commerce.services.order import OrderService


@override_settings(CLIENT_REQUIRE_VERIFIED_EMAIL_LINK=True)
class BuyerLinkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="buyer-link", email="buyer-link@example.com")
        self.address = EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True)
        self.buyer = Client.objects.create(name="Existing buyer", email=self.user.email)

    def test_unverified_email_does_not_claim_existing_client(self):
        with self.assertRaises(ValidationError) as caught:
            OrderService()._buyer_for(self.user)
        self.assertEqual(caught.exception.detail["detail"].code, "email_verification_required")
        self.buyer.refresh_from_db()
        self.assertIsNone(self.buyer.user_id)

    def test_confirmed_email_links_existing_client(self):
        self.address.verified = True
        self.address.save()
        result = OrderService()._buyer_for(self.user)
        self.assertEqual(result.pk, self.buyer.pk)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.user_id, self.user.pk)

    @override_settings(CLIENT_REQUIRE_VERIFIED_EMAIL_LINK=False)
    def test_verification_can_be_disabled_for_unlinked_client(self):
        result = OrderService()._buyer_for(self.user)
        self.assertEqual(result.pk, self.buyer.pk)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.user_id, self.user.pk)

    @override_settings(CLIENT_REQUIRE_VERIFIED_EMAIL_LINK=False)
    def test_disabled_verification_does_not_replace_another_account(self):
        other = get_user_model().objects.create_user(username="linked-owner")
        self.buyer.user = other
        self.buyer.save()
        with self.assertRaises(ValidationError) as caught:
            OrderService()._buyer_for(self.user)
        self.assertEqual(caught.exception.detail["detail"].code, "client_already_linked")
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.user_id, other.pk)

    def test_another_account_is_not_replaced(self):
        other = get_user_model().objects.create_user(username="original-buyer")
        self.buyer.user = other
        self.buyer.save()
        self.address.verified = True
        self.address.save()
        with self.assertRaises(ValidationError) as caught:
            OrderService()._buyer_for(self.user)
        self.assertEqual(caught.exception.detail["detail"].code, "client_already_linked")
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.user_id, other.pk)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ACCOUNT_RATE_LIMITS={},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}},
    )
    def test_authenticated_buyer_can_request_confirmation(self):
        api = APIClient()
        api.force_login(self.user)
        response = api.put("/api/browser/v1/account/email", {"email": self.user.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
