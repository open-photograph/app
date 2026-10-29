import uuid

from django.db import models


class WatermarkStyle(models.TextChoices):
    """Como a marca d'água é renderizada sobre a imagem."""

    TEXT_DIAGONAL = "text_diagonal", "Texto diagonal repetido"
    IMAGE_OVERLAY = "image_overlay", "Imagem sobreposta (logo)"
    COMBINED = "combined", "Texto diagonal + logo"


class WatermarkAsset(models.Model):
    """
    Configuração de marca d'água de um fotógrafo/estúdio.

    Pode ser apenas texto repetido em grid diagonal, um logo sobreposto,
    ou a combinação dos dois — tornando a imagem resistente a remoção por IA.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=100,
        help_text="Nome interno para identificar esta configuração.",
    )

    style = models.CharField(
        max_length=20,
        choices=WatermarkStyle.choices,
        default=WatermarkStyle.TEXT_DIAGONAL,
    )

    # -------------------------------------------------------------------------
    # Text watermark
    # -------------------------------------------------------------------------
    text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Texto repetido na grade diagonal. Ex: '© João Silva | open-photograph.com'",
    )

    text_color = models.CharField(
        max_length=9,
        default="#FFFFFF",
        help_text="Cor do texto em hex. Ex: #FFFFFF",
    )

    text_opacity = models.FloatField(
        default=0.35,
        help_text="Opacidade do texto entre 0.0 e 1.0.",
    )

    font_size_ratio = models.FloatField(
        default=0.03,
        help_text=("Tamanho da fonte como fração da largura da imagem. Ex: 0.03 = 3% da largura."),
    )

    rotation_angle = models.IntegerField(
        default=-30,
        help_text="Ângulo de rotação do texto em graus. Negativo = sentido anti-horário.",
    )

    tile_spacing = models.IntegerField(
        default=200,
        help_text="Espaçamento em pixels entre repetições do texto na grade.",
    )

    # -------------------------------------------------------------------------
    # Image / logo watermark
    # -------------------------------------------------------------------------
    logo = models.ImageField(
        upload_to="watermarks/logos/",
        null=True,
        blank=True,
        help_text="Logo/imagem sobreposta (PNG com transparência recomendado).",
    )

    logo_opacity = models.FloatField(
        default=0.5,
        help_text="Opacidade do logo entre 0.0 e 1.0.",
    )

    logo_size_ratio = models.FloatField(
        default=0.15,
        help_text="Tamanho do logo como fração da largura da imagem. Ex: 0.15 = 15%.",
    )

    logo_position = models.CharField(
        max_length=20,
        default="bottom_right",
        choices=[
            ("top_left", "Canto superior esquerdo"),
            ("top_right", "Canto superior direito"),
            ("bottom_left", "Canto inferior esquerdo"),
            ("bottom_right", "Canto inferior direito"),
            ("center", "Centro"),
        ],
        help_text="Posição do logo na imagem.",
    )

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    is_default = models.BooleanField(
        default=False,
        help_text="Marca d'água padrão usada quando nenhuma é especificada na galeria.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name = "Marca d'água"
        verbose_name_plural = "Marcas d'água"

    def __str__(self) -> str:
        return self.name
