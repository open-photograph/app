from django.conf import settings
from django.db import models


class IncludedPhoto(models.Model):
    """Permanent original access granted from a client's gallery allowance."""

    gallery = models.ForeignKey("gallery.Gallery", on_delete=models.CASCADE, related_name="included_choices")
    photo = models.ForeignKey("gallery.Photo", on_delete=models.PROTECT, related_name="included_choices")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="included_photos")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "photo"], name="unique_user_included_photo")]

    def __str__(self):
        return f"{self.user_id}: {self.photo_id}"
