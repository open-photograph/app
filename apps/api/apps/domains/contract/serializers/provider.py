from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.integrations.signature.credentials import get_signature_environment
from apps.integrations.signature.registry import signature_provider_registry

from ..models import SignatureProvider


class SignatureProviderSerializer(serializers.ModelSerializer):
    environment = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True)
    provider = serializers.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["provider"].choices = signature_provider_registry.choices()

    class Meta:
        model = SignatureProvider
        fields = ["id", "name", "provider", "environment", "is_active"]
        read_only_fields = ["id", "name"]

    def validate(self, attrs):
        for field in ("api_token", "encrypted_token", "credentials"):
            if field in self.initial_data:
                raise serializers.ValidationError({field: "Configure as chaves no .env do servidor."})
        if (
            self.instance
            and self.instance.contracts.exists()
            and attrs.get("provider", self.instance.provider) != self.instance.provider
        ):
            raise serializers.ValidationError({"provider": "Crie outra configuração para mudar o provider."})
        return attrs

    def get_environment(self, instance):
        return get_signature_environment()

    def create(self, validated_data):
        validated_data["name"] = signature_provider_registry.get(validated_data["provider"]).label
        try:
            with transaction.atomic():
                if validated_data.get("is_active", True):
                    SignatureProvider.objects.filter(is_active=True).update(is_active=False)
                return super().create(validated_data)
        except IntegrityError as error:
            raise serializers.ValidationError("A configuração ativa foi alterada. Tente salvar novamente.") from error

    def update(self, instance, validated_data):
        validated_data["name"] = signature_provider_registry.get(
            validated_data.get("provider", instance.provider)
        ).label
        try:
            with transaction.atomic():
                if validated_data.get("is_active", instance.is_active):
                    SignatureProvider.objects.filter(is_active=True).exclude(pk=instance.pk).update(is_active=False)
                return super().update(instance, validated_data)
        except IntegrityError as error:
            raise serializers.ValidationError("A configuração ativa foi alterada. Tente salvar novamente.") from error
