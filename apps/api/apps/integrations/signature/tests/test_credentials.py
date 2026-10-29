from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from ..base import SignatureProviderError
from ..registry import get_signature_provider


class EnvironmentCredentialsTests(SimpleTestCase):
    @override_settings(ZAPSIGN_API_TOKEN="production-secret", ZAPSIGN_SANDBOX_API_TOKEN="sandbox-secret")
    def test_provider_uses_the_selected_environment_token(self):
        for environment, expected in (("sandbox", "sandbox-secret"), ("production", "production-secret")):
            with self.settings(DEBUG=environment == "sandbox"):
                provider = get_signature_provider(SimpleNamespace(provider="zapsign"))
            self.assertEqual(provider.token, expected)

    @override_settings(DEBUG=True, ZAPSIGN_API_TOKEN="production-secret", ZAPSIGN_SANDBOX_API_TOKEN="")
    def test_sandbox_never_falls_back_to_production_credentials(self):
        with self.assertRaises(SignatureProviderError):
            get_signature_provider(SimpleNamespace(provider="zapsign", environment="sandbox"))
