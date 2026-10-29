from django.db import models


class PreviewSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    quality = models.PositiveSmallIntegerField(default=85)
    max_size = models.PositiveSmallIntegerField(default=1920)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_preview_settings")]

    def __str__(self):
        return "Configuração das prévias"

    @classmethod
    def current(cls):
        return cls.objects.filter(pk=1).first() or cls()
