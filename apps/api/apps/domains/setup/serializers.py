from rest_framework import serializers

from .models import Setup


class SetupSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if "credentials" in self.initial_data:
            raise serializers.ValidationError({"credentials": "Configure as chaves no .env do servidor."})
        return attrs

    def validate_type(self, value):
        if self.instance and Setup.objects.filter(type=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Ja existe uma configuracao deste tipo.")
        return value

    class Meta:
        model = Setup
        fields = ["id", "name", "type", "provider", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"type": {"validators": []}, "name": {"required": False}}
