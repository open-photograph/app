from .base import SignatureProviderError
from .credentials import get_signature_environment
from .manifest import SignatureProviderManifest
from .providers.zapsign.manifest import manifest as zapsign_manifest


class SignatureProviderRegistry:
    def __init__(self):
        self.providers: dict[str, SignatureProviderManifest] = {}

    def register(self, manifest):
        if manifest.value in self.providers:
            raise ValueError(f"Signature provider already registered: {manifest.value}")
        self.providers[manifest.value] = manifest

    def get(self, value):
        manifest = self.providers.get(value)
        if manifest is None:
            raise SignatureProviderError("Provider de assinatura não disponível.")
        return manifest

    def choices(self):
        return [(manifest.value, manifest.label) for manifest in self.providers.values()]

    def catalog(self):
        return [manifest.catalog_entry() for manifest in self.providers.values()]


signature_provider_registry = SignatureProviderRegistry()
signature_provider_registry.register(zapsign_manifest)


def get_signature_provider(configuration, *, environment=None):
    manifest = signature_provider_registry.get(configuration.provider)
    return manifest.factory(environment or get_signature_environment())
