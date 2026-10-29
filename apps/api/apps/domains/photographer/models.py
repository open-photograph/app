from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Photographer(models.Model):
    user = models.OneToOneField(
        to=User,
        on_delete=models.PROTECT,
        related_name="photographer",
    )

    def __str__(self):
        return self.user
