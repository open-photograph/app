from rest_framework import serializers

from apps.integrations.signature.credentials import get_signature_environment

from ..models import Contract, SignatureProvider
from ..services.contract import render_content


class ContractSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    provider_name = serializers.CharField(source="signature_provider.name", read_only=True)
    variables = serializers.DictField(
        child=serializers.CharField(max_length=10000, allow_blank=True, trim_whitespace=False),
        write_only=True,
        required=False,
    )
    content = serializers.CharField(max_length=200000, required=False)

    class Meta:
        model = Contract
        fields = [
            "id",
            "title",
            "template",
            "client",
            "client_name",
            "signature_provider",
            "provider_name",
            "provider_environment",
            "content",
            "variables",
            "signer_name",
            "signer_email",
            "status",
            "signing_url",
            "provider_document_id",
            "last_error",
            "last_synced_at",
            "signed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "signature_provider",
            "provider_environment",
            "signer_name",
            "signer_email",
            "status",
            "signing_url",
            "provider_document_id",
            "last_error",
            "last_synced_at",
            "signed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        variables = attrs.pop("variables", {})
        if self.instance is None:
            template = attrs.get("template")
            content = attrs.get("content") or (template.content if template else "")
            if not content.strip():
                raise serializers.ValidationError({"content": "Escreva o contrato ou escolha um template."})
            client = attrs["client"]
            attrs["content"] = render_content(content, client=client, title=attrs["title"], variables=variables)
            attrs["provider_environment"] = get_signature_environment()
            attrs["signer_name"] = client.name
            attrs["signer_email"] = client.email
            provider = SignatureProvider.objects.filter(is_active=True).first()
            if provider is None:
                raise serializers.ValidationError(
                    "Configure um serviço de assinatura ativo em Configurações → Assinaturas."
                )
            attrs["signature_provider"] = provider
        else:
            if variables and "content" not in attrs:
                raise serializers.ValidationError({"variables": "Envie o conteúdo para substituir as variáveis."})
            client = attrs.get("client", self.instance.client)
            if "client" in attrs:
                attrs["signer_name"] = client.name
                attrs["signer_email"] = client.email
            if "content" in attrs:
                attrs["content"] = render_content(
                    attrs["content"], client=client, title=attrs.get("title", self.instance.title), variables=variables
                )
        return attrs
