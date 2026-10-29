import uuid

from django.conf import settings
from django.db import models


class PhotoLike(models.Model):
    photo = models.ForeignKey("gallery.Photo", on_delete=models.CASCADE, related_name="likes")
    visitor = models.UUIDField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["photo", "visitor"], name="unique_photo_visitor_like"),
            models.UniqueConstraint(fields=["photo", "user"], name="unique_photo_user_like"),
        ]

    def __str__(self):
        return f"{self.photo_id} · {self.visitor}"


class PhotoComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    photo = models.ForeignKey("gallery.Photo", on_delete=models.CASCADE, related_name="comments")
    visitor = models.UUIDField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=120)
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.name} · {self.photo_id}"


class GallerySelection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gallery = models.ForeignKey("gallery.Gallery", on_delete=models.CASCADE, related_name="selections")
    visitor = models.UUIDField()
    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField(max_length=2000, blank=True)
    photos = models.ManyToManyField("gallery.Photo", related_name="selections")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} · {self.gallery_id}"
