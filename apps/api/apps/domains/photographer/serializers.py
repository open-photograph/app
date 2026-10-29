from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Photographer

User = get_user_model()


class PhotographerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Photographer
        fields = (
            "email",
            "password",
        )

    def validate(self, attrs):
        if Photographer.objects.exists():
            raise serializers.ValidationError("O fotógrafo já foi configurado.")

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.pop("email")
        password = validated_data.pop("password")

        user = User.objects.create_superuser(
            username="admin",
            email=email,
            password=password,
        )

        return Photographer.objects.create(
            user=user,
            **validated_data,
        )
