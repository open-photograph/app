from rest_framework import serializers

from ..models import Order


class OrderPaymentSerializer(serializers.ModelSerializer):
    """Payment details exposed in the order response."""

    class Meta:
        model = Order
        fields = ["payment_provider", "payment_reference", "status", "checkout_url", "paid_at"]
        read_only_fields = fields
