from urllib.parse import quote

from django.conf import settings
from django.db import models
from payments import PurchasedItem
from payments.models import BasePayment


class Payment(BasePayment):
    """Persisted django-payments transaction for an order."""

    order = models.OneToOneField(
        "commerce.Order",
        on_delete=models.PROTECT,
        related_name="payment",
        primary_key=True,
    )
    gallery_slug = models.SlugField(blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default="0.0")
    captured_amount = models.DecimalField(max_digits=10, decimal_places=2, default="0.0")

    def get_success_url(self):
        return f"{settings.FRONTEND_URL.rstrip('/')}/g/{quote(self.gallery_slug)}/purchases?order={self.order_id}"

    def get_failure_url(self):
        return self.get_success_url()

    def get_purchased_items(self):
        yield PurchasedItem(self.description, 1, self.total, self.currency, str(self.order_id))
