from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from djmoney.money import Money
from payments import PaymentStatus
from rest_framework.exceptions import ValidationError

from apps.domains.client.models import Client
from apps.domains.gallery.models import Gallery, Photo
from apps.domains.setup.models import Setup, SetupCategory

from ..models import Order, OrderItem, OrderItemType, OrderPhoto, OrderStatus
from .payment import PaymentError, create_checkout, get_order_payment, payment_status

ORDER_TTL = timedelta(hours=24)
ALLOWED_CURRENCIES = ("BRL", "USD", "EUR")


def _error(detail, code="invalid"):
    return ValidationError({"detail": detail}, code=code)


class OrderService:
    @transaction.atomic
    def checkout(self, user, data):
        get_user_model().objects.select_for_update().get(pk=user.pk)
        order, gallery_slug = self._get_or_create_order(user, data)
        self._ensure_gateway_checkout(order, gallery_slug)
        return order

    def _get_or_create_order(self, user, data):
        previous = Order.objects.filter(request_id=data["request_id"]).first()

        match previous:
            case None:
                return self._create_order(user, data)
            case _:
                self._validate_repeated_checkout(previous, user, data)
                return previous, self._order_gallery_slug(previous)

    def _create_order(self, user, data):
        client = self._buyer_for(user)
        gallery, photos, items = self._purchase_selection(data)
        if data.get("photo_ids"):
            from apps.domains.gallery.models import IncludedPhoto

            if IncludedPhoto.objects.filter(user=user, photo__in=photos).exists():
                raise _error("Uma foto selecionada já está incluída para sua conta. Baixe o original pela galeria.")
        currency = self._purchase_currency(items)

        self._validate_gallery_access(gallery, user, data.get("access_code", ""))
        if data.get("gallery_id"):
            from .pricing import package_balance

            if OrderItem.objects.filter(order__client=client, order__status=OrderStatus.PAID, gallery=gallery).exists():
                raise _error("Você já possui o pacote desta galeria. Acesse Minhas fotos.")
            paid_ids = set(
                OrderPhoto.objects.filter(order__client=client, order__status=OrderStatus.PAID).values_list(
                    "photo_id", flat=True
                )
            )
            self._validate_existing_purchases(client, [photo for photo in photos if photo.pk not in paid_ids])
            balance = package_balance(gallery, user)
            items = [(OrderItemType.GALLERY, gallery, Money(balance["remaining"], currency))]
        else:
            self._validate_existing_purchases(client, photos)

        total_price = Money(sum(price.amount for _, _, price in items), currency)
        provider = self._payment_provider() if total_price.amount > 0 else "package_balance"
        order = Order.objects.create(
            client=client,
            request_id=data["request_id"],
            payment_provider=provider,
            total=total_price,
            expires_at=timezone.now() + ORDER_TTL,
            status=OrderStatus.PENDING if total_price.amount > 0 else OrderStatus.PAID,
            paid_at=timezone.now() if total_price.amount == 0 else None,
        )

        self._create_order_items(order, items)
        self._create_order_photos(order, photos)

        return order, gallery.slug

    @staticmethod
    def _create_order_items(order, items):
        for kind, item, price in items:
            match kind:
                case OrderItemType.GALLERY:
                    target = {"gallery": item}
                case OrderItemType.PHOTO:
                    target = {"photo": item}
                case _:
                    raise ValueError(f"Tipo de item desconhecido: {kind}")

            OrderItem.objects.create(
                order=order,
                item_type=kind,
                unit_price=price,
                **target,
            )

    @staticmethod
    def _create_order_photos(order, photos):
        OrderPhoto.objects.bulk_create(
            [OrderPhoto(order=order, photo=photo) for photo in photos],
        )

    @staticmethod
    def _order_gallery_slug(order):
        return order.order_photos.select_related("photo__gallery").first().photo.gallery.slug

    # ------------------------------------------------------------------
    # Comprador do checkout
    # ------------------------------------------------------------------

    def _buyer_for(self, user):
        client = Client.objects.filter(user=user).first()
        if client:
            return client

        if not user.email:
            raise _error("Cadastre um email na sua conta antes de comprar.")

        existing = Client.objects.select_for_update().filter(email__iexact=user.email).first()

        match existing:
            case None:
                return Client.objects.create(
                    user=user,
                    email=user.email,
                    name=user.get_full_name() or user.email,
                )
            case Client(user_id=None) if not settings.CLIENT_REQUIRE_VERIFIED_EMAIL_LINK or self._has_verified_email(
                user
            ):
                existing.user = user
                existing.save(update_fields=["user", "updated_at"])

                return existing
            case Client(user_id=None):
                raise _error(
                    "Verifique seu email para vincular o cadastro de cliente existente.",
                    code="email_verification_required",
                )
            case _:
                raise _error(
                    "Este cadastro já está vinculado a outra conta. Entre com essa conta ou contate o fotógrafo.",
                    code="client_already_linked",
                )

    @staticmethod
    def _has_verified_email(user):
        return EmailAddress.objects.filter(
            user=user,
            email__iexact=user.email,
            verified=True,
        ).exists()

    # ------------------------------------------------------------------
    # Selecao do checkout
    # ------------------------------------------------------------------

    def _purchase_selection(self, data):
        gallery_selection = self._gallery_selection(data)
        photo_selection = self._photo_selection(data)

        galleries = {
            gallery.pk: gallery
            for gallery in [
                *gallery_selection[0],
                *photo_selection[0],
            ]
        }

        photos = [
            *gallery_selection[1],
            *photo_selection[1],
        ]

        items = [
            *gallery_selection[2],
            *photo_selection[2],
        ]

        match list(galleries.values()):
            case [gallery] if photos:
                return gallery, photos, items
            case _:
                raise _error("Compre fotos de uma unica galeria por pedido.")

    def _gallery_selection(self, data):
        match data.get("gallery_id"):
            case None | "":
                return [], [], []

            case gallery_id:
                gallery = get_object_or_404(Gallery, pk=gallery_id)

        if not self._has_valid_price(gallery.gallery_price):
            raise _error("A galeria nao possui preco de pacote.")

        photos = list(gallery.photos.filter(status="ready", is_active=True).exclude(source_file_id=""))
        items = [
            (
                OrderItemType.GALLERY,
                gallery,
                gallery.gallery_price,
            )
        ]

        return [gallery], photos, items

    def _photo_selection(self, data):
        photo_ids = data.get("photo_ids", [])
        if not photo_ids:
            return [], [], []

        photos = list(Photo.objects.select_related("gallery").filter(pk__in=photo_ids))
        if len(photos) != len(photo_ids):
            raise _error("Uma ou mais fotos nao existem.")

        for photo in photos:
            self._validate_sellable_photo(photo)

        galleries = [photo.gallery for photo in photos]
        items = [
            (
                OrderItemType.PHOTO,
                photo,
                photo.effective_price,
            )
            for photo in photos
        ]

        return galleries, photos, items

    def _validate_sellable_photo(self, photo):
        if not photo.is_active:
            raise _error("Uma foto selecionada nao esta disponivel para venda.")

        if not photo.gallery.individual_sales_enabled or not self._has_valid_price(photo.effective_price):
            raise _error("Uma foto selecionada nao esta disponivel para venda.")

        if photo.status != "ready" or not photo.source_file_id:
            raise _error("Uma foto selecionada ainda nao esta pronta.")

    @staticmethod
    def _has_valid_price(price):
        return price is not None and price.amount > 0

    @staticmethod
    def _purchase_currency(items):
        currencies = sorted({str(price.currency) for _, _, price in items})

        match currencies:
            case [currency] if currency in ALLOWED_CURRENCIES:
                return currency
            case _:
                raise _error("Os itens precisam usar a mesma moeda (BRL, USD ou EUR).")

    @staticmethod
    def _payment_provider():
        provider = (
            Setup.objects.filter(type=SetupCategory.PAYMENT, is_active=True).values_list("provider", flat=True).first()
        )
        if not provider:
            raise _error("Selecione um gateway de pagamento no Setup.")
        if provider not in settings.PAYMENT_VARIANTS:
            raise _error(f"{provider}: a chave de pagamento nao esta configurada no .env do servidor.")
        return provider

    # ------------------------------------------------------------------
    # Validacoes do checkout
    # ------------------------------------------------------------------

    def _validate_gallery_access(self, gallery, user, code):
        match gallery:
            case Gallery(is_published=False) | Gallery(enable_sales=False):
                raise _error("Esta galeria nao esta disponivel para compra.")

            case Gallery(is_private=True) if not self._can_access_private_gallery(gallery, user, code):
                raise _error("Informe o codigo de acesso desta galeria.")

    @staticmethod
    def _can_access_private_gallery(gallery, user, code):
        return (
            user.is_staff
            or gallery.clients.filter(user=user).exists()
            or check_password(code, gallery.access_code_hash)
        )

    @staticmethod
    def _validate_existing_purchases(client, photos):
        purchases = OrderPhoto.objects.filter(
            order__client=client,
            photo__in=photos,
        )

        if purchases.filter(order__status=OrderStatus.PAID).exists():
            raise _error("Voce ja possui fotos desta selecao. Acesse Minhas fotos.")

        pending = purchases.filter(
            order__status=OrderStatus.PENDING,
            order__expires_at__gt=timezone.now(),
        )

        if pending.exists():
            raise _error("Ja existe uma compra pendente para estas fotos. Continue em Minhas fotos.")

    def _validate_repeated_checkout(self, previous, user, data):
        if previous.client.user_id == user.pk and previous.status == OrderStatus.PAID and previous.total.amount == 0:
            if self._selection_changed(previous, data):
                raise _error("A seleção mudou. Inicie um novo pedido.")
            return
        match previous:
            case Order(client=Client(user_id=owner_id)) if owner_id != user.pk:
                raise _error("Identificador de compra invalido.")

            case Order(status=order_status, expires_at=expires_at) if (
                order_status != OrderStatus.PENDING or expires_at <= timezone.now()
            ):
                raise _error("Este pedido ja foi finalizado ou expirou.")

        if self._selection_changed(previous, data):
            raise _error("A selecao mudou. Inicie um novo pedido.")

    @staticmethod
    def _selection_changed(previous, data):
        gallery_ids = list(
            previous.items.exclude(gallery=None).values_list(
                "gallery_id",
                flat=True,
            )
        )

        photo_ids = set(
            previous.items.exclude(photo=None).values_list(
                "photo_id",
                flat=True,
            )
        )

        expected_gallery_ids = [data["gallery_id"]] if data.get("gallery_id") else []

        return gallery_ids != expected_gallery_ids or photo_ids != set(data["photo_ids"])

    # ------------------------------------------------------------------
    # Pagamento
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_gateway_checkout(order, gallery_slug):
        if order.is_paid:
            return
        if order.checkout_url:
            return
        try:
            reference, url = create_checkout(order, gallery_slug)
        except PaymentError as exc:
            raise _error(str(exc)) from exc

        order.payment_reference = reference
        order.checkout_url = url
        order.save(
            update_fields=[
                "payment_reference",
                "checkout_url",
                "updated_at",
            ]
        )

    def refresh_payment(self, order):
        if not order.payment_reference:
            return

        new_status = self._resolve_status(order, payment_status(order))
        if new_status == order.status:
            return

        if new_status == OrderStatus.PAID and not order.paid_at:
            order.paid_at = timezone.now()

        order.status = new_status
        order.save(
            update_fields=[
                "status",
                "paid_at",
                "updated_at",
            ]
        )

    @staticmethod
    def _resolve_status(order, gateway_status):
        match gateway_status:
            case "pending" if order.status == OrderStatus.PAID:
                return order.status
            case "pending" if order.expires_at and order.expires_at <= timezone.now():
                return OrderStatus.EXPIRED
            case _:
                return gateway_status

    @staticmethod
    def mark_as_paid(order):
        if order.status != OrderStatus.PENDING:
            raise _error("Somente pedidos pendentes podem ser confirmados.")

        payment = get_order_payment(order)
        payment.change_status(PaymentStatus.CONFIRMED)
        order.refresh_from_db()
