import uuid

from django.conf import settings
from django.db import models
from djmoney.models.fields import MoneyField
from djmoney.money import Money

from .gallery import Gallery


class PhotoStatus(models.TextChoices):
    PROCESSING = "processing", "Processando"
    READY = "ready", "Pronta"
    FAILED = "failed", "Falhou"


class PhotoDownloadPolicy(models.TextChoices):
    INHERIT = "inherit", "Seguir a galeria"
    ALLOW = "allow", "Permitir"
    DENY = "deny", "Bloquear"


class Photo(models.Model):
    is_included = models.BooleanField(default=False)
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    source_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_gallery_photos",
    )

    gallery = models.ForeignKey(
        to=Gallery,
        related_name="photos",
        on_delete=models.CASCADE,
    )

    name = models.CharField(max_length=255)

    source_file_id = models.CharField(
        max_length=255,
        blank=True,
    )

    thumbnail = models.ImageField(
        upload_to="photos/thumbnails/",
        null=True,
        blank=True,
    )

    preview = models.ImageField(
        upload_to="photos/previews/",
        null=True,
        blank=True,
    )

    width = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    height = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="Tamanho original em bytes",
    )

    mime_type = models.CharField(
        max_length=100,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=PhotoStatus.choices,
        default=PhotoStatus.PROCESSING,
    )

    position = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Controla se a foto aparece e pode receber interacoes na galeria publica.",
    )

    download_policy = models.CharField(
        max_length=10,
        choices=PhotoDownloadPolicy.choices,
        default=PhotoDownloadPolicy.INHERIT,
        help_text="Permissão de download gratuito da prévia. Não altera o acesso a originais comprados.",
    )

    # -------------------------------------------------------------------------
    # Commerce
    # -------------------------------------------------------------------------
    price = MoneyField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency="USD",
        help_text="Preço individual. Válido apenas se allow_individual_purchase estiver ativo na galeria.",
    )

    # -------------------------------------------------------------------------
    # Watermark
    # -------------------------------------------------------------------------
    watermarked_preview = models.ImageField(
        upload_to="photos/watermarked/",
        null=True,
        blank=True,
        help_text="Preview com marca d'água anti-IA. Gerado automaticamente quando watermark_enabled=True na galeria.",
    )

    taken_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                name="unique_gallery_source_photo",
                fields=["gallery", "source_file_id"],
                condition=~models.Q(source_file_id=""),
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def effective_price(self):
        if self.gallery.included_photo_mode == "all":
            return None
        if self.gallery.included_photo_mode == "photographer" and self.is_included:
            return None
        if self.price is not None:
            return self.price
        if self.gallery.default_photo_price is not None:
            return Money(self.gallery.default_photo_price, self.gallery.gallery_price_currency)
        return None

    @property
    def download_allowed(self):
        if self.download_policy == PhotoDownloadPolicy.INHERIT:
            return self.gallery.allow_downloads
        return self.download_policy == PhotoDownloadPolicy.ALLOW

    @property
    def public_preview(self):
        return self.watermarked_preview if self.gallery.watermark_enabled else self.preview

    @property
    def can_download(self):
        return bool(
            self.gallery.is_published
            and self.is_active
            and self.status == PhotoStatus.READY
            and self.download_allowed
            and self.public_preview
        )


class PhotoExif(models.Model):
    photo = models.OneToOneField(
        to=Photo,
        on_delete=models.CASCADE,
        related_name="exif",
        primary_key=True,
    )

    camera_make = models.CharField(
        max_length=100,
        blank=True,
    )

    camera_model = models.CharField(
        max_length=150,
        blank=True,
    )

    lens_model = models.CharField(
        max_length=150,
        blank=True,
    )

    iso = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    aperture = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Abertura em f-stop. Exemplo: 1.80",
    )

    shutter_speed = models.CharField(
        max_length=30,
        blank=True,
        help_text="Tempo de exposição. Exemplo: 1/250",
    )

    focal_length = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Distância focal em milímetros",
    )

    exposure_compensation = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    flash_fired = models.BooleanField(
        null=True,
        blank=True,
    )

    software = models.CharField(
        max_length=150,
        blank=True,
    )

    captured_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Metadados EXIF"
        verbose_name_plural = "Metadados EXIF"

    def __str__(self) -> str:
        return f"EXIF - {self.photo.name}"
