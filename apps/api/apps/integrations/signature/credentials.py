from django.conf import settings

from .base import SignatureProviderError


def get_signature_environment():
    return "sandbox" if settings.DEBUG else "production"


def get_signature_credential(setting_name):
    value = getattr(settings, setting_name, "")
    if not value:
        raise SignatureProviderError("Configure as chaves de assinatura no .env do servidor para o ambiente atual.")
    return value
