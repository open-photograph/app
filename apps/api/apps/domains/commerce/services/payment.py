"""Connect orders to native django-payments checkout and status updates."""

import json
import logging

from payments import PaymentStatus, RedirectNeeded
from payments.core import provider_factory

from ..models import Payment
from ..signals import PAYMENT_ORDER_STATUSES

logger = logging.getLogger(__name__)

ORDER_TO_PAYMENT_STATUS = {
    "paid": PaymentStatus.CONFIRMED,
    "refunded": PaymentStatus.REFUNDED,
    "failed": PaymentStatus.ERROR,
    "expired": PaymentStatus.CANCELLED,
}

MSG_CHECKOUT_NO_URL = "O provider precisa fornecer uma URL de checkout."
MSG_CHECKOUT_FAILED = "Não foi possível criar o checkout. Verifique as credenciais de pagamento."
MSG_STATUS_FAILED = "Não foi possível verificar o pagamento. Tente novamente."
MSG_STATUS_UNAVAILABLE = "Não foi possível verificar o pagamento."


class PaymentError(Exception):
    """Payment failure safe to display to the buyer."""


def _build_extra_data(order):
    """Stripe: reaproveita a sessão de checkout já criada no pedido."""
    if order.payment_provider != "stripe":
        return ""

    if not (order.payment_reference and order.checkout_url):
        return ""

    return json.dumps(
        {
            "session": {
                "id": order.payment_reference,
                "url": order.checkout_url,
            }
        }
    )


def get_order_payment(order, slug=""):
    status = ORDER_TO_PAYMENT_STATUS.get(
        order.status,
        PaymentStatus.WAITING,
    )
    payment, _ = Payment.objects.get_or_create(
        order=order,
        defaults={
            "variant": order.payment_provider,
            "token": str(order.pk),
            "transaction_id": order.payment_reference,
            "extra_data": _build_extra_data(order),
            "currency": str(order.total.currency),
            "total": order.total.amount,
            "billing_email": order.client.email,
            "description": "Compra de fotos",
            "gallery_slug": slug,
            "status": status,
        },
    )

    return payment


def create_checkout(order, slug):
    try:
        payment = get_order_payment(order, slug)
        payment.get_form()

    except RedirectNeeded as redirect:
        return payment.transaction_id, str(redirect)

    except PaymentError:
        raise

    except Exception:
        logger.exception("Payment checkout failed for provider %s", order.payment_provider)
        raise PaymentError(MSG_CHECKOUT_FAILED) from None

    raise PaymentError(MSG_CHECKOUT_NO_URL)


def _poll_mercado_pago(backend, payment):
    """Adapt django-payments 4.1 polling to the Mercado Pago SDK 2.4 response.

    poll_for_updates reads search results at the top level, but SDK 2.4
    returns them inside `response`. Only adapt that envelope;
    process_collection owns status handling.
    """
    preference = backend.get_preference(payment)
    result = backend.client.payment().search({"external_reference": preference["external_reference"]})

    if result["status"] != 200:
        raise PaymentError(MSG_STATUS_UNAVAILABLE)

    results = result["response"].get("results", [])

    if results:
        backend.process_collection(payment, results[-1]["id"])


def _sync_payment(order, payment):
    backend = provider_factory(payment.variant, payment)
    provider = order.payment_provider

    if provider == "stripe":
        backend.status(payment)
    elif provider == "mercado_pago":
        _poll_mercado_pago(backend, payment)
    else:
        backend.poll_for_updates(payment)


def payment_status(order):
    try:
        payment = get_order_payment(order)
        _sync_payment(order, payment)

        return PAYMENT_ORDER_STATUSES[payment.status]
    except PaymentError:
        raise

    except Exception:
        logger.exception("Payment status failed for provider %s", order.payment_provider)
        raise PaymentError(MSG_STATUS_FAILED) from None
