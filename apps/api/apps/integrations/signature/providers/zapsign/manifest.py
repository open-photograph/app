from ...credentials import get_signature_credential
from ...manifest import SignatureProviderManifest
from .provider import ZapSignProvider


def create_provider(environment):
    setting_name = "ZAPSIGN_SANDBOX_API_TOKEN" if environment == "sandbox" else "ZAPSIGN_API_TOKEN"
    return ZapSignProvider(token=get_signature_credential(setting_name), environment=environment)


manifest = SignatureProviderManifest(
    value="zapsign",
    label="ZapSign",
    docs_url="https://docs.zapsign.com.br/",
    factory=create_provider,
)
