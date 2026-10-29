import uuid

from django.db import models
from djmoney.models.fields import MoneyField

from apps.domains.client.models import Client
from apps.domains.gallery.models import Gallery, Photo


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Aguardando pagamento"
    PAID = "paid", "Pago"
    FAILED = "failed", "Falhou"
    REFUNDED = "refunded", "Reembolsado"
    EXPIRED = "expired", "Expirado"


class OrderItemType(models.TextChoices):
    GALLERY = "gallery", "Galeria completa"
    PHOTO = "photo", "Foto avulsa"


class Order(models.Model):
    """
    Representa uma compra feita por um cliente.

    O provider usado na compra vem da configuracao de ambiente e fica
    registrado no pedido para preservar o historico. As chaves sao lidas
    exclusivamente pelo django-payments a partir de PAYMENT_VARIANTS.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    request_id = models.UUIDField(null=True, blank=True, unique=True)

    client = models.ForeignKey(
        to=Client,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    # Snapshot do provider ativo no ambiente no momento do checkout.
    # Ex: "mercado_pago", "stripe".
    payment_provider = models.CharField(
        max_length=50,
        help_text="Provider de pagamento usado nesta ordem (snapshot no momento da criação).",
    )

    # ID externo da transação na gateway (Stripe PaymentIntent ID,
    # Mercado Pago preference_id, etc.)
    payment_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Identificador da transação no gateway de pagamento.",
    )

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )

    total = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency="USD",
        help_text="Valor total da ordem.",
    )

    # URL de checkout gerada pelo gateway. Expira conforme regras do provider.
    checkout_url = models.URLField(
        max_length=2048,
        blank=True,
        help_text="URL de redirecionamento para o gateway de pagamento.",
    )

    # URL assinada para download após pagamento aprovado.
    download_url = models.URLField(
        max_length=2048,
        blank=True,
        help_text="URL temporária para download após pagamento aprovado.",
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiração do pedido pendente. Após este prazo o status muda para 'expired'.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payment_reference"]),
        ]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self) -> str:
        return f"Order {self.id} — {self.client} [{self.status}]"

    @property
    def is_paid(self) -> bool:
        return self.status == OrderStatus.PAID


class OrderItem(models.Model):
    """
    Item de um pedido. Pode ser uma galeria inteira ou uma foto avulsa.

    O preço é armazenado como snapshot do momento da compra para preservar
    o histórico mesmo que o preço do produto seja alterado depois.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    order = models.ForeignKey(
        to=Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    item_type = models.CharField(
        max_length=10,
        choices=OrderItemType.choices,
    )

    # Apenas um dos dois será preenchido, dependendo do item_type.
    gallery = models.ForeignKey(
        to=Gallery,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
    )

    photo = models.ForeignKey(
        to=Photo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_items",
    )

    # Snapshot do preço no momento da compra.
    unit_price = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency="USD",
        help_text="Preço unitário no momento da compra.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item do pedido"
        verbose_name_plural = "Itens do pedido"
        constraints = [
            # Um item do tipo gallery deve ter gallery preenchida
            models.CheckConstraint(
                name="order_item_gallery_requires_gallery_fk",
                condition=~models.Q(item_type="gallery") | models.Q(gallery__isnull=False),
            ),
            # Um item do tipo photo deve ter photo preenchida
            models.CheckConstraint(
                name="order_item_photo_requires_photo_fk",
                condition=~models.Q(item_type="photo") | models.Q(photo__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        if self.item_type == OrderItemType.GALLERY:
            return f"Galeria: {self.gallery}"
        return f"Foto: {self.photo}"


class OrderPhoto(models.Model):
    """Originals included in the purchase at checkout time."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_photos")
    photo = models.ForeignKey(Photo, on_delete=models.PROTECT, related_name="purchases")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "photo"], name="unique_order_photo")]

    def __str__(self):
        return f"{self.order_id}: {self.photo_id}"
