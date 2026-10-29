import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

User = get_user_model()


class Client(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        to=User,
        on_delete=models.SET_NULL,
        related_name="client_profile",
        null=True,
        blank=True,
        help_text="Conta de acesso vinculada a este cliente.",
    )

    name = models.CharField(max_length=255)

    email = models.EmailField(
        unique=True,
        db_index=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Número com DDD. Ex: +55 11 91234-5678",
    )

    notes = models.TextField(
        blank=True,
        help_text="Observações internas sobre o cliente.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        ordering = ["name"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name
