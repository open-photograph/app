from rest_framework import serializers

from ..models import WatermarkAsset


class WatermarkAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = WatermarkAsset
        fields = [
            "id",
            "name",
            "style",
            "text",
            "text_color",
            "text_opacity",
            "font_size_ratio",
            "rotation_angle",
            "tile_spacing",
            "logo",
            "logo_opacity",
            "logo_size_ratio",
            "logo_position",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
