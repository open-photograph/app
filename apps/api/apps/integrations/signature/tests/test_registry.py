from unittest.mock import Mock

from django.test import SimpleTestCase

from ..base import SignatureProviderError
from ..manifest import SignatureProviderManifest
from ..registry import SignatureProviderRegistry


class SignatureRegistryTests(SimpleTestCase):
    def test_manifest_drives_catalog_and_choices(self):
        registry = SignatureProviderRegistry()
        manifest = SignatureProviderManifest("other", "Outro serviço", "https://example.com/docs", Mock())
        registry.register(manifest)
        self.assertEqual(registry.choices(), [("other", "Outro serviço")])
        self.assertEqual(registry.catalog(), [manifest.catalog_entry()])
        self.assertIs(registry.get("other"), manifest)
        self.assertNotIn("factory", registry.catalog()[0])

    def test_duplicate_provider_identifiers_are_rejected(self):
        registry = SignatureProviderRegistry()
        manifest = SignatureProviderManifest("other", "Outro serviço", "https://example.com/docs", Mock())
        registry.register(manifest)
        with self.assertRaises(ValueError):
            registry.register(manifest)

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(SignatureProviderError):
            SignatureProviderRegistry().get("unknown")
