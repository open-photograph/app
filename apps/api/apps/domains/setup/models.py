from django.db import models


class SetupCategory(models.TextChoices):
    PAYMENT = "payment", "Pagamento"
    STORAGE = "storage", "Armazenamento"


class Setup(models.Model):
    name = models.CharField(max_length=100)

    type = models.CharField(
        max_length=20,
        choices=SetupCategory.choices,
    )

    provider = models.CharField(
        max_length=50,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        app_label = "setup"
        constraints = [
            models.UniqueConstraint(
                fields=["type"],
                name="setup_unique_type",
            ),
        ]

    def __str__(self) -> str:
        return self.name
