from urllib.parse import quote, urlparse

import httpx

from ...base import BaseSignatureProvider, SignatureDocument, SignatureProviderError


class ZapSignProvider(BaseSignatureProvider):
    def __init__(self, *, token, environment):
        self.token = token
        self.base_url = (
            "https://sandbox.api.zapsign.com.br/api/v1/"
            if environment == "sandbox"
            else "https://api.zapsign.com.br/api/v1/"
        )

    def _request(self, method, path, **kwargs):
        try:
            response = httpx.request(
                method,
                self.base_url + path,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=30,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            message = (
                "A ZapSign recusou a requisição. Verifique o token, o ambiente e o plano API."
                if status < 500
                else "A ZapSign está indisponível. Verifique o documento no provider antes de tentar novamente."
            )
            raise SignatureProviderError(message, uncertain=method == "POST" and status >= 500) from error
        except (httpx.RequestError, ValueError) as error:
            raise SignatureProviderError(
                "Não foi possível confirmar a resposta da ZapSign. Verifique o documento no provider.",
                uncertain=method == "POST",
            ) from error

    def _parse(self, payload, *, creating=False):
        try:
            document_id = payload["token"]
            status = payload["status"]
            signers = payload.get("signers", [])
            signing_url = signers[0].get("sign_url", "") if signers else ""
            if not signing_url and signers and signers[0].get("token"):
                host = "sandbox.app.zapsign.com.br" if "sandbox.api" in self.base_url else "app.zapsign.com.br"
                signing_url = f"https://{host}/verificar/{quote(signers[0]['token'], safe='')}"
            signed_at = signers[0].get("signed_at") if signers else None
            signed_file = payload.get("signed_file") or ""
            if not isinstance(document_id, str) or not document_id or status not in {"pending", "signed"}:
                raise ValueError
            if creating and (not signing_url or urlparse(signing_url).scheme != "https"):
                raise ValueError
            return SignatureDocument(
                document_id, status, signing_url, signed_at, signed_file, str(payload.get("external_id") or "")
            )
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
            raise SignatureProviderError(
                "Resposta inesperada da ZapSign. Verifique o documento no provider.", uncertain=creating
            ) from error

    def create_document(self, *, title, content, signer_name, signer_email, external_id):
        payload = self._request(
            "POST",
            "docs/",
            json={
                "name": title,
                "markdown_text": content,
                "lang": "pt-br",
                "external_id": str(external_id),
                "disable_signer_emails": True,
                "signers": [
                    {
                        "name": signer_name,
                        "email": signer_email,
                        "lock_name": True,
                        "lock_email": True,
                        "auth_mode": "assinaturaTela",
                        "send_automatic_email": False,
                        "send_automatic_whatsapp": False,
                    }
                ],
            },
        )
        return self._parse(payload, creating=True)

    def get_document(self, document_id):
        return self._parse(self._request("GET", f"docs/{quote(document_id, safe='')}/"))
