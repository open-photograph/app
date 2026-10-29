from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.domains.client.models import Client
from apps.integrations.signature.base import SignatureDocument, SignatureProviderError

from ..models import Contract, ContractTemplate, SignatureProvider


@override_settings(DEBUG=True, CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class ContractTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="contracts-admin", is_staff=True)
        self.buyer = get_user_model().objects.create_user(username="contracts-buyer")
        self.customer = Client.objects.create(name="Ana Silva", email="ana@example.com")
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.template = ContractTemplate.objects.create(
            name="Ensaio", content="# {{ contrato.titulo }}\n\nCliente: {{ cliente.nome }} / {{ cliente.email }}"
        )
        response = self.api.post(
            "/api/signature-providers/",
            {
                "name": "ZapSign teste",
                "provider": "zapsign",
                "environment": "sandbox",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.configuration = SignatureProvider.objects.get(pk=response.data["id"])

    def create_contract(self):
        response = self.api.post(
            "/api/contracts/",
            {
                "title": "Ensaio de família",
                "template": str(self.template.pk),
                "client": str(self.customer.pk),
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        return Contract.objects.get(pk=response.data["id"])

    def test_provider_selection_does_not_require_or_expose_credentials(self):
        response = self.api.get("/api/signature-providers/")
        self.assertEqual(set(response.data[0]), {"id", "name", "provider", "environment", "is_active"})
        self.assertNotIn("encrypted_token", {field.name for field in SignatureProvider._meta.fields})
        response = self.api.patch(f"/api/signature-providers/{self.configuration.pk}/", {"name": "Renamed"})
        self.assertEqual(response.status_code, 200)

    def test_credentials_are_rejected_on_create_and_update(self):
        for field in ("api_token", "encrypted_token", "credentials"):
            response = self.api.post(
                "/api/signature-providers/",
                {
                    "name": "Provider",
                    "provider": "zapsign",
                    "environment": "production",
                    field: "do-not-save",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400)
            response = self.api.patch(
                f"/api/signature-providers/{self.configuration.pk}/", {field: "do-not-save"}, format="json"
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(SignatureProvider.objects.count(), 1)

    @override_settings(ZAPSIGN_SANDBOX_API_TOKEN="", ZAPSIGN_API_TOKEN="")
    def test_missing_environment_token_keeps_draft_and_does_not_call_provider(self):
        contract = self.create_contract()
        with patch("apps.integrations.signature.providers.zapsign.provider.httpx.request") as request:
            response = self.api.post(f"/api/contracts/{contract.pk}/generate-link/")
        self.assertEqual(response.status_code, 400)
        request.assert_not_called()
        contract.refresh_from_db()
        self.assertEqual(contract.status, "draft")

    def test_template_and_signer_are_snapshots(self):
        contract = self.create_contract()
        self.assertIn("Ana Silva", contract.content)
        self.assertNotIn("{{", contract.content)
        self.template.content = "Changed"
        self.template.save()
        self.customer.name = "New name"
        self.customer.save()
        contract.refresh_from_db()
        self.assertIn("Ana Silva", contract.content)
        self.assertEqual(contract.signer_name, "Ana Silva")
        response = self.api.delete(f"/api/contract-templates/{self.template.pk}/")
        self.assertEqual(response.status_code, 204)
        contract.refresh_from_db()
        self.assertIsNone(contract.template)
        self.assertIn("Ana Silva", contract.content)

    def test_unknown_variables_and_inactive_providers_are_rejected(self):
        self.template.content = "{{ desconhecida }}"
        self.template.save()
        payload = {
            "title": "Contrato",
            "template": str(self.template.pk),
            "client": str(self.customer.pk),
            "signature_provider": str(self.configuration.pk),
        }
        self.assertEqual(self.api.post("/api/contracts/", payload).status_code, 400)
        self.template.content = "Texto do contrato"
        self.template.save()
        self.configuration.is_active = False
        self.configuration.save()
        self.assertEqual(self.api.post("/api/contracts/", payload).status_code, 400)
        self.assertEqual(Contract.objects.count(), 0)

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_generate_is_idempotent_and_freezes_contract(self, factory):
        contract = self.create_contract()
        provider = factory.return_value
        provider.create_document.return_value = SignatureDocument(
            "doc-1", "pending", "https://app.zapsign.com.br/verificar/signer-1"
        )
        url = f"/api/contracts/{contract.pk}/"
        first = self.api.post(url + "generate-link/")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["status"], "pending")
        second = self.api.post(url + "generate-link/")
        self.assertEqual(second.data["signing_url"], first.data["signing_url"])
        provider.create_document.assert_called_once()
        self.assertEqual(provider.create_document.call_args.kwargs["signer_email"], "ana@example.com")
        self.assertEqual(self.api.patch(url, {"content": "Alterado"}).status_code, 400)
        self.assertEqual(self.api.delete(url).status_code, 400)

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_ambiguous_creation_cannot_be_retried(self, factory):
        contract = self.create_contract()
        factory.return_value.create_document.side_effect = SignatureProviderError("Timeout", uncertain=True)
        url = f"/api/contracts/{contract.pk}/generate-link/"
        self.assertEqual(self.api.post(url).status_code, 400)
        contract.refresh_from_db()
        self.assertEqual(contract.status, "uncertain")
        self.assertEqual(self.api.post(url).status_code, 400)
        self.assertEqual(factory.return_value.create_document.call_count, 1)

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_definitive_rejection_remains_draft(self, factory):
        contract = self.create_contract()
        factory.return_value.create_document.side_effect = SignatureProviderError("Invalid credential")
        self.assertEqual(self.api.post(f"/api/contracts/{contract.pk}/generate-link/").status_code, 400)
        contract.refresh_from_db()
        self.assertEqual(contract.status, "draft")

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_status_and_signed_file_are_fetched_from_provider(self, factory):
        contract = self.create_contract()
        contract.provider_document_id = "doc-1"
        contract.status = "pending"
        contract.save()
        factory.return_value.get_document.return_value = SignatureDocument(
            "doc-1",
            "signed",
            signed_at="2026-10-27T12:00:00Z",
            signed_file="https://files.example.com/signed.pdf",
        )
        response = self.api.post(f"/api/contracts/{contract.pk}/sync/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "signed")
        self.assertIsNotNone(response.data["signed_at"])
        response = self.api.get(f"/api/contracts/{contract.pk}/signed-file/")
        self.assertEqual(response.data["url"], "https://files.example.com/signed.pdf")
        self.assertEqual(factory.return_value.get_document.call_count, 2)

    def test_name_and_environment_are_automatic(self):
        for debug, environment in ((True, "sandbox"), (False, "production")):
            with self.settings(DEBUG=debug):
                response = self.api.post(
                    "/api/signature-providers/",
                    {
                        "provider": "zapsign",
                        "name": "Ignored",
                        "environment": "invalid",
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["name"], "ZapSign")
                self.assertEqual(response.data["environment"], environment)

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_generated_document_keeps_environment_when_debug_changes(self, factory):
        contract = self.create_contract()
        factory.return_value.create_document.return_value = SignatureDocument(
            "doc-1",
            "pending",
            "https://sandbox.app.zapsign.com.br/verificar/signer-1",
        )
        self.assertEqual(self.api.post(f"/api/contracts/{contract.pk}/generate-link/").status_code, 200)
        self.assertEqual(factory.call_args.kwargs["environment"], "sandbox")
        factory.return_value.get_document.return_value = SignatureDocument("doc-1", "pending")
        with self.settings(DEBUG=False):
            response = self.api.post(f"/api/contracts/{contract.pk}/sync/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider_environment"], "sandbox")
        self.assertEqual(factory.call_args.kwargs["environment"], "sandbox")

    def test_only_staff_can_access_all_contract_resources(self):
        contract = self.create_contract()
        for user in (None, self.buyer):
            self.api.force_authenticate(user)
            for url in (
                "/api/contracts/",
                "/api/contract-templates/",
                "/api/signature-providers/",
                "/api/signature-providers/catalog/",
            ):
                self.assertIn(self.api.get(url).status_code, (401, 403))
            self.assertIn(self.api.post(f"/api/contracts/{contract.pk}/generate-link/").status_code, (401, 403))

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_recover_requires_matching_external_id(self, factory):
        contract = self.create_contract()
        contract.status = "uncertain"
        contract.save()
        provider = factory.return_value
        provider.get_document.return_value = SignatureDocument(
            "doc-1", "pending", "https://app.zapsign.com.br/verificar/signer-1", external_id="another-contract"
        )
        url = f"/api/contracts/{contract.pk}/recover/"
        self.assertEqual(self.api.post(url, {"document_id": "doc-1"}).status_code, 400)
        provider.get_document.return_value = SignatureDocument(
            "doc-1", "pending", "https://app.zapsign.com.br/verificar/signer-1", external_id=str(contract.pk)
        )
        response = self.api.post(url, {"document_id": "doc-1"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["provider_document_id"], "doc-1")
        provider.create_document.assert_not_called()

    @patch("apps.domains.contract.services.contract.get_signature_provider")
    def test_delayed_pending_response_does_not_undo_signature(self, factory):
        contract = self.create_contract()
        contract.status = "signed"
        contract.provider_document_id = "doc-1"
        contract.save()
        factory.return_value.get_document.return_value = SignatureDocument("doc-1", "pending")
        response = self.api.post(f"/api/contracts/{contract.pk}/sync/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "signed")

    def test_registered_provider_is_available_without_contract_changes(self):
        from unittest.mock import Mock

        from apps.integrations.signature.manifest import SignatureProviderManifest
        from apps.integrations.signature.registry import signature_provider_registry

        adapter = Mock()
        adapter.create_document.return_value = SignatureDocument("other-doc", "pending", "https://example.com/sign/1")
        factory = Mock(return_value=adapter)
        manifest = SignatureProviderManifest("other", "Outro serviço", "https://example.com/docs", factory)
        with patch.dict(signature_provider_registry.providers, {"other": manifest}):
            catalog = self.api.get("/api/signature-providers/catalog/")
            self.assertIn(manifest.catalog_entry(), catalog.data["providers"])
            self.assertNotIn("variables", catalog.data)
            response = self.api.post("/api/signature-providers/", {"provider": "other"}, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["name"], "Outro serviço")
            response = self.api.post(
                "/api/contracts/",
                {
                    "title": "Contrato",
                    "template": str(self.template.pk),
                    "client": str(self.customer.pk),
                    "signature_provider": response.data["id"],
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
            response = self.api.post(f"/api/contracts/{response.data['id']}/generate-link/")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["signing_url"], "https://example.com/sign/1")
            factory.assert_called_once_with("sandbox")
            adapter.create_document.assert_called_once()

    def test_template_variables_do_not_depend_on_signature_catalog(self):
        from apps.integrations.signature.registry import signature_provider_registry

        with patch.dict(signature_provider_registry.providers, {}, clear=True):
            response = self.api.get(f"/api/contract-templates/{self.template.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("cliente.nome", response.data["variables"])

    def test_new_contract_uses_active_provider_and_ignores_client_override(self):
        original = self.create_contract()
        response = self.api.post("/api/signature-providers/", {"provider": "zapsign", "is_active": True}, format="json")
        self.assertEqual(response.status_code, 201)
        active_id = response.data["id"]
        self.configuration.refresh_from_db()
        self.assertFalse(self.configuration.is_active)
        self.assertEqual(SignatureProvider.objects.filter(is_active=True).count(), 1)
        response = self.api.post(
            "/api/contracts/",
            {
                "title": "Novo contrato",
                "template": str(self.template.pk),
                "client": str(self.customer.pk),
                "signature_provider": str(self.configuration.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(str(response.data["signature_provider"]), active_id)
        original.refresh_from_db()
        self.assertEqual(original.signature_provider_id, self.configuration.pk)
        response = self.api.patch(f"/api/contracts/{original.pk}/", {"signature_provider": active_id}, format="json")
        self.assertEqual(response.status_code, 200)
        original.refresh_from_db()
        self.assertEqual(original.signature_provider_id, self.configuration.pk)

    def test_creating_contract_without_active_provider_returns_configuration_error(self):
        SignatureProvider.objects.update(is_active=False)
        response = self.api.post(
            "/api/contracts/",
            {
                "title": "Contrato",
                "template": str(self.template.pk),
                "client": str(self.customer.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Assinaturas", str(response.data))
        self.assertEqual(Contract.objects.count(), 0)

    def test_reactivating_configuration_deactivates_previous_provider(self):
        response = self.api.post("/api/signature-providers/", {"provider": "zapsign"}, format="json")
        self.assertEqual(response.status_code, 201)
        other_id = response.data["id"]
        response = self.api.patch(
            f"/api/signature-providers/{self.configuration.pk}/", {"is_active": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SignatureProvider.objects.get(pk=other_id).is_active)
        self.assertEqual(SignatureProvider.objects.filter(is_active=True).get().pk, self.configuration.pk)

    def test_custom_template_fields_are_discovered_and_filled_during_creation(self):
        self.template.content = "Cliente: {{name}}. Serviço: {{ servico }}. {{name}}. {{ cliente.email }}"
        self.template.save()
        response = self.api.get(f"/api/contract-templates/{self.template.pk}/")
        self.assertEqual(response.data["variables"], ["name", "servico", "cliente.email"])
        self.assertEqual(response.data["input_variables"], ["name", "servico"])
        payload = {"title": "Contrato", "client": str(self.customer.pk), "template": str(self.template.pk)}
        response = self.api.post("/api/contracts/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Contract.objects.count(), 0)
        payload["variables"] = {"name": "Maria", "servico": "Ensaio externo"}
        response = self.api.post("/api/contracts/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["content"], r"Cliente: Maria. Serviço: Ensaio externo. Maria. ana@example\.com")
        self.assertNotIn("variables", response.data)
        self.template.content = "Changed {{different}}"
        self.template.save()
        contract = Contract.objects.get(pk=response.data["id"])
        self.assertIn("Maria", contract.content)
        self.assertNotIn("different", contract.content)
