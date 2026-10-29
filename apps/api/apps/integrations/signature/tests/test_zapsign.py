from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from ..base import SignatureProviderError
from ..providers.zapsign.provider import ZapSignProvider


class ZapSignTests(SimpleTestCase):
    @patch("apps.integrations.signature.providers.zapsign.provider.httpx.request")
    def test_create_uses_markdown_bearer_and_no_automatic_messages(self, request):
        request.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://example.com"),
            json={
                "token": "doc-1",
                "status": "pending",
                "signers": [{"sign_url": "https://sandbox.app.zapsign.com.br/verificar/signer-1"}],
            },
        )
        provider = ZapSignProvider(token="secret", environment="sandbox")
        document = provider.create_document(
            title="Contrato",
            content="**Cláusula**",
            signer_name="Ana",
            signer_email="ana@example.com",
            external_id="contract-1",
        )
        self.assertEqual(document.document_id, "doc-1")
        args, kwargs = request.call_args
        self.assertEqual(args, ("POST", "https://sandbox.api.zapsign.com.br/api/v1/docs/"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["json"]["markdown_text"], "**Cláusula**")
        self.assertEqual(kwargs["json"]["external_id"], "contract-1")
        self.assertFalse(kwargs["json"]["signers"][0]["send_automatic_email"])
        self.assertFalse(kwargs["json"]["signers"][0]["send_automatic_whatsapp"])

    @patch("apps.integrations.signature.providers.zapsign.provider.httpx.request")
    def test_timeout_and_server_errors_are_ambiguous(self, request):
        provider = ZapSignProvider(token="secret", environment="production")
        for failure in (
            httpx.ReadTimeout("timeout"),
            httpx.HTTPStatusError(
                "failed", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(503)
            ),
        ):
            request.side_effect = failure
            with self.assertRaises(SignatureProviderError) as caught:
                provider.create_document(
                    title="x", content="x", signer_name="Ana", signer_email="ana@example.com", external_id="1"
                )
            self.assertTrue(caught.exception.uncertain)

    def test_invalid_creation_response_is_ambiguous(self):
        with self.assertRaises(SignatureProviderError) as caught:
            ZapSignProvider(token="secret", environment="sandbox")._parse(
                {"token": "x", "status": "pending", "signers": []}, creating=True
            )
        self.assertTrue(caught.exception.uncertain)
