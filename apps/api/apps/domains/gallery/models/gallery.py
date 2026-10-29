import uuid

from django.db import models
from django.utils import timezone
from djmoney.models.fields import MoneyField

from ...client.models import Client


class GalleryTheme(models.TextChoices):
    MASONRY = "masonry", "Pinterest / Masonry"
    INSTAGRAM = "instagram", "Instagram / Feed"
    CLASSIC = "classic", "Classic"
    FEATURED = "featured", "Featured"
    CAROUSEL = "carousel", "Carousel"


class GalleryAccessType(models.TextChoices):
    PUBLIC = "public", "Pública"
    UNLISTED = "unlisted", "Não listada"
    PRIVATE = "private", "Privada"


class GalleryTag(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(
        max_length=100,
        unique=True,
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
    )

    def __str__(self) -> str:
        return self.title


class Gallery(models.Model):
    included_photo_mode = models.CharField(
        max_length=20,
        choices=[
            ("none", "Sem fotos incluídas"),
            ("all", "Todas as fotos incluídas"),
            ("photographer", "Escolhidas pelo fotógrafo"),
            ("client", "Franquia por cliente"),
        ],
        default="none",
    )
    included_photo_limit = models.PositiveIntegerField(default=0)

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    clients = models.ManyToManyField(
        to=Client,
        related_name="galleries",
        blank=True,
    )

    tags = models.ManyToManyField(
        to=GalleryTag,
        related_name="galleries",
        blank=True,
    )

    name = models.CharField(
        max_length=255,
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    theme = models.CharField(
        max_length=20,
        choices=GalleryTheme.choices,
        default=GalleryTheme.MASONRY,
    )

    access_type = models.CharField(
        max_length=20,
        choices=GalleryAccessType.choices,
        default=GalleryAccessType.PUBLIC,
    )

    access_code_hash = models.CharField(
        max_length=255,
        blank=True,
    )

    is_published = models.BooleanField(
        default=False,
    )

    allow_downloads = models.BooleanField(
        default=True,
    )

    allow_likes = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=False)
    allow_selection = models.BooleanField(default=False)

    # -------------------------------------------------------------------------
    # Commerce
    # -------------------------------------------------------------------------
    enable_sales = models.BooleanField(
        default=False,
        help_text="Habilita a venda desta galeria.",
    )

    allow_individual_purchase = models.BooleanField(
        default=False,
        help_text="Permite que o cliente compre fotos individualmente.",
    )

    gallery_price = MoneyField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency="USD",
        help_text="Preço da galeria inteira. Deixe em branco para não vender o pacote completo.",
    )

    default_photo_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Preço individual padrão na moeda da galeria. Fotos com preço próprio prevalecem.",
    )

    # -------------------------------------------------------------------------
    # Watermark
    # -------------------------------------------------------------------------
    watermark_enabled = models.BooleanField(
        default=False,
        help_text="Aplica marca d'água nas previews públicas desta galeria.",
    )

    watermark_asset = models.ForeignKey(
        to="commerce.WatermarkAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="galleries",
        help_text="Configuração de marca d'água usada nesta galeria. Se vazio, usa a padrão.",
    )

    source_folder_id = models.CharField(
        max_length=255,
        blank=True,
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "access_type"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def individual_sales_enabled(self):
        return self.enable_sales and (self.allow_individual_purchase or self.included_photo_mode == "client")

    @property
    def is_public(self) -> bool:
        return self.is_published and self.access_type == GalleryAccessType.PUBLIC

    @property
    def is_private(self) -> bool:
        return self.access_type == GalleryAccessType.PRIVATE

    def publish(self) -> None:
        if not self.is_published:
            self.is_published = True
            self.published_at = timezone.now()

            self.save(
                update_fields=[
                    "is_published",
                    "published_at",
                    "updated_at",
                ]
            )

    def unpublish(self) -> None:
        if self.is_published:
            self.is_published = False
            self.save(
                update_fields=[
                    "is_published",
                    "updated_at",
                ]
            )
