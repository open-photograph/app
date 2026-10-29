from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money
from rest_framework.test import APIClient

from apps.domains.client.models import Client

from ..models import Order


class SalesTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="sales-admin", is_staff=True)
        self.buyer = get_user_model().objects.create_user(username="sales-buyer")
        self.client_record = Client.objects.create(name="Buyer", email="sales@example.com")
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def order(self, amount=20, currency="BRL", status="paid", paid_at=None):
        return Order.objects.create(
            client=self.client_record,
            total=Money(amount, currency),
            status=status,
            payment_provider="stripe",
            paid_at=paid_at or timezone.now(),
        )

    def test_totals_are_paid_only_in_period_and_currency(self):
        self.order(20)
        self.order(40)
        self.order(500, status="pending")
        self.order(500, status="refunded")
        self.order(500, currency="USD")
        self.order(500, paid_at=timezone.now() - timedelta(days=10))
        response = self.api.get("/api/commerce/orders/sales/", {"days": 7, "currency": "BRL"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(float(response.data["revenue"]), 60)
        self.assertEqual(float(response.data["average"]), 30)
        self.assertEqual(len(response.data["series"]), 7)
        self.assertEqual(sum(point["count"] for point in response.data["series"]), 2)
        self.assertEqual(len(response.data["recent"]), 2)
        self.assertEqual(response.data["currencies"], ["BRL", "USD"])

    def test_empty_and_invalid_period(self):
        response = self.api.get("/api/commerce/orders/sales/")
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["recent"], [])
        self.assertEqual(len(response.data["series"]), 30)
        for days in ("invalid", 0, 365):
            self.assertEqual(self.api.get("/api/commerce/orders/sales/", {"days": days}).status_code, 400)

    def test_recent_sales_are_limited_and_sorted_by_payment(self):
        for offset in range(12):
            self.order(paid_at=timezone.now() - timedelta(hours=offset))
        response = self.api.get("/api/commerce/orders/sales/")
        recent = response.data["recent"]
        self.assertEqual(len(recent), 10)
        self.assertGreaterEqual(recent[0]["paid_at"], recent[-1]["paid_at"])

    def test_non_staff_cannot_read_sales(self):
        self.api.force_authenticate(self.buyer)
        self.assertEqual(self.api.get("/api/commerce/orders/sales/").status_code, 403)
        self.api.force_authenticate(None)
        self.assertIn(self.api.get("/api/commerce/orders/sales/").status_code, (401, 403))
