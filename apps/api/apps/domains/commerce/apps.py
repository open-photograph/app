from django.apps import AppConfig


class CommerceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.domains.commerce"
    verbose_name = "Commerce"

    def ready(self):
        from . import signals  # noqa: F401
