from django.contrib.auth.hashers import make_password
from djmoney.contrib.django_rest_framework.fields import MoneyField
from rest_framework import serializers

from ..models import Gallery, GalleryTag
from ..models.gallery import GalleryAccessType


class GalleryTagSerializer(serializers.ModelSerializer):
    gallery_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = GalleryTag
        fields = ["id", "title", "slug", "gallery_count"]
        read_only_fields = ["id"]


class GallerySerializer(serializers.ModelSerializer):
    included_photo_limit = serializers.IntegerField(min_value=0, max_value=10000, required=False)
    access_code = serializers.CharField(write_only=True, required=False, min_length=6, max_length=128)
    gallery_price = MoneyField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = Gallery
        exclude = ["access_code_hash"]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "published_at",
            "last_synced_at",
        ]

    def to_internal_value(self, data):
        # Ignore stale codes from hidden form inputs before field validation.
        access_type = self._get_effective_value(data, "access_type")
        if access_type != GalleryAccessType.PRIVATE and "access_code" in data:
            data = data.copy()
            data.pop("access_code")

        return super().to_internal_value(data)

    def validate(self, attrs):
        self._validate_access(attrs)
        if self._get_effective_value(attrs, "included_photo_mode") == "all":
            attrs["enable_sales"] = False
            attrs["allow_individual_purchase"] = False
        if (
            self._get_effective_value(attrs, "enable_sales")
            and self._get_effective_value(attrs, "included_photo_mode") == "client"
        ):
            attrs["allow_individual_purchase"] = True
            if self._get_effective_value(attrs, "default_photo_price") is None:
                raise serializers.ValidationError(
                    {"default_photo_price": "Defina o preço individual das fotos extras."}
                )
        self._validate_sales(attrs)
        if self._get_effective_value(attrs, "included_photo_mode") != "client":
            attrs["included_photo_limit"] = 0
        if self._get_effective_value(attrs, "included_photo_mode") == "client":
            clients = attrs.get("clients")
            has_clients = (
                bool(clients) if clients is not None else bool(self.instance and self.instance.clients.exists())
            )
            if not has_clients:
                raise serializers.ValidationError({"clients": "Vincule ao menos um cliente para usar a franquia."})
        if (
            self._get_effective_value(attrs, "included_photo_mode") == "client"
            and self._get_effective_value(attrs, "included_photo_limit") < 1
        ):
            raise serializers.ValidationError({"included_photo_limit": "Informe ao menos uma foto incluída."})

        return attrs

    def create(self, validated_data):
        self._hash_access_code(validated_data)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._hash_access_code(validated_data)

        return super().update(instance, validated_data)

    def _get_effective_value(self, attrs, field_name):
        """Resolve submitted values, existing values on update, or model defaults."""
        if field_name in attrs:
            return attrs[field_name]

        if self.instance is not None:
            return getattr(self.instance, field_name)

        return Gallery._meta.get_field(field_name).get_default()

    def _validate_access(self, attrs):
        if self._get_effective_value(attrs, "access_type") != GalleryAccessType.PRIVATE:
            return

        existing_code_hash = getattr(self.instance, "access_code_hash", "")
        if not attrs.get("access_code") and not existing_code_hash:
            raise serializers.ValidationError(
                {"access_code": "Defina um código de acesso com pelo menos 6 caracteres."}
            )

    def _validate_sales(self, attrs):
        individual_price = self._get_effective_value(attrs, "default_photo_price")
        if individual_price is not None and individual_price <= 0:
            raise serializers.ValidationError({"default_photo_price": "O preço deve ser maior que zero."})
        price = self._get_effective_value(attrs, "gallery_price")

        if price is not None and getattr(price, "amount", price) <= 0:
            raise serializers.ValidationError({"gallery_price": "O preço deve ser maior que zero."})

        enable_sales = self._get_effective_value(attrs, "enable_sales")
        allow_individual_purchase = self._get_effective_value(attrs, "allow_individual_purchase")

        if enable_sales and price is None and not allow_individual_purchase:
            raise serializers.ValidationError(
                {"gallery_price": "Informe o preço do pacote ou habilite a venda individual."}
            )

    def _hash_access_code(self, validated_data):
        access_code = validated_data.pop("access_code", None)
        if access_code:
            validated_data["access_code_hash"] = make_password(access_code)
