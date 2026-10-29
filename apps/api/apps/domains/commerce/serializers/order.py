from rest_framework import serializers

from ..models import Order, OrderItem
from .payment import OrderPaymentSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    unit_price = serializers.SerializerMethodField()
    unit_price_currency = serializers.CharField(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "item_type",
            "gallery",
            "photo",
            "unit_price",
            "unit_price_currency",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_unit_price(self, obj: OrderItem) -> str:
        return str(obj.unit_price.amount) if obj.unit_price is not None else None


class OrderSerializer(OrderPaymentSerializer):
    purchase_type = serializers.SerializerMethodField()

    def get_purchase_type(self, obj):
        return "package" if any(item.item_type == "gallery" for item in obj.items.all()) else "individual"

    photos = serializers.SerializerMethodField()

    def get_photos(self, obj):
        return [
            {
                "id": str(item.photo_id),
                "name": item.photo.name,
                "gallery_slug": item.photo.gallery.slug,
                "download_url": f"/api/commerce/orders/{obj.pk}/download/{item.photo_id}/" if obj.is_paid else None,
            }
            for item in obj.order_photos.select_related("photo__gallery").all()
        ]

    items = OrderItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()
    total_currency = serializers.CharField(read_only=True)

    class Meta(OrderPaymentSerializer.Meta):
        fields = [
            "id",
            "client",
            "payment_provider",
            "payment_reference",
            "status",
            "total",
            "total_currency",
            "checkout_url",
            "download_url",
            "paid_at",
            "expires_at",
            "created_at",
            "updated_at",
            "items",
            "photos",
            "purchase_type",
        ]
        read_only_fields = [
            "id",
            *OrderPaymentSerializer.Meta.read_only_fields,
            "download_url",
            "created_at",
            "updated_at",
        ]

    def get_total(self, obj: Order) -> str:
        return str(obj.total.amount) if obj.total is not None else None


class OrderCreateSerializer(serializers.Serializer):
    request_id = serializers.UUIDField()
    gallery_id = serializers.UUIDField(required=False)
    photo_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
        max_length=500,
        write_only=True,
    )
    access_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
        write_only=True,
    )

    def validate(self, attrs):
        if bool(attrs.get("gallery_id")) == bool(attrs.get("photo_ids")):
            raise serializers.ValidationError("Selecione a galeria inteira ou fotos individuais.")

        if len(attrs["photo_ids"]) != len(set(attrs["photo_ids"])):
            raise serializers.ValidationError("Nao repita fotos no mesmo pedido.")

        return attrs
