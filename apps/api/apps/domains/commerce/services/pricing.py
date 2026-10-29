from decimal import Decimal

from django.db.models import Sum

from ..models import OrderItem, OrderItemType, OrderStatus


def package_balance(gallery, user):
    """Credit only actual paid individual-item snapshots in the package currency."""
    base = gallery.gallery_price.amount if gallery.gallery_price is not None else Decimal(0)
    paid = Decimal(0)
    if user.is_authenticated:
        paid = OrderItem.objects.filter(
            order__client__user=user,
            order__status=OrderStatus.PAID,
            item_type=OrderItemType.PHOTO,
            photo__gallery=gallery,
            unit_price_currency=gallery.gallery_price_currency,
            order__total_currency=gallery.gallery_price_currency,
        ).aggregate(amount=Sum("unit_price"))["amount"] or Decimal(0)
    discount = min(base, paid)
    return {"base": base, "discount": discount, "remaining": max(Decimal(0), base - discount)}
