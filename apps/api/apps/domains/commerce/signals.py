from django.dispatch import receiver
from django.utils import timezone
from payments import PaymentStatus
from payments.signals import status_changed

from .models import Order, OrderStatus, Payment

PAYMENT_ORDER_STATUSES = {
    PaymentStatus.WAITING: OrderStatus.PENDING,
    PaymentStatus.INPUT: OrderStatus.PENDING,
    PaymentStatus.PREAUTH: OrderStatus.PENDING,
    PaymentStatus.CONFIRMED: OrderStatus.PAID,
    PaymentStatus.REFUNDED: OrderStatus.REFUNDED,
    PaymentStatus.REJECTED: OrderStatus.FAILED,
    PaymentStatus.ERROR: OrderStatus.FAILED,
    PaymentStatus.CANCELLED: OrderStatus.FAILED,
}


@receiver(status_changed, sender=Payment, dispatch_uid="commerce.payment_status_changed")
def sync_order_payment_status(sender, instance, **kwargs):
    status = PAYMENT_ORDER_STATUSES[instance.status]
    orders = Order.objects.filter(pk=instance.order_id)

    if status == OrderStatus.PENDING:
        orders = orders.filter(status=OrderStatus.PENDING)

    orders.update(
        status=status,
        updated_at=timezone.now(),
    )

    if status == OrderStatus.PAID:
        orders.filter(paid_at__isnull=True).update(paid_at=timezone.now())
