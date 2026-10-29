from django.http import HttpResponse
from PIL import Image
from rest_framework import serializers
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.domains.commerce.models import WatermarkAsset
from apps.domains.commerce.serializers.watermark import WatermarkAssetSerializer

from ..utils import render_preview
from ..models import PreviewSettings


class WatermarkPreviewSerializer(WatermarkAssetSerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    style = serializers.ChoiceField(choices=["text_diagonal", "image_overlay", "combined"])
    text = serializers.CharField(max_length=200, allow_blank=True, default="")
    logo_position = serializers.ChoiceField(choices=["top_left", "top_right", "bottom_left", "bottom_right", "center"])
    text_color = serializers.RegexField(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
    text_opacity = serializers.FloatField(min_value=0, max_value=1)
    font_size_ratio = serializers.FloatField(min_value=0.001, max_value=1)
    rotation_angle = serializers.IntegerField(min_value=-360, max_value=360)
    tile_spacing = serializers.IntegerField(min_value=10, max_value=2000)
    logo_opacity = serializers.FloatField(min_value=0, max_value=1)
    logo_size_ratio = serializers.FloatField(min_value=0.001, max_value=1)

    class Meta(WatermarkAssetSerializer.Meta):
        fields = [
            "name",
            "style",
            "text",
            "text_color",
            "text_opacity",
            "font_size_ratio",
            "rotation_angle",
            "tile_spacing",
            "logo_opacity",
            "logo_size_ratio",
            "logo_position",
        ]


class ImagePreviewSerializer(serializers.Serializer):
    image = serializers.ImageField()
    logo = serializers.ImageField(required=False)
    watermark = serializers.JSONField(required=False)
    asset_id = serializers.PrimaryKeyRelatedField(queryset=WatermarkAsset.objects.all(), required=False)
    remove_logo = serializers.BooleanField(default=False)
    quality = serializers.IntegerField(min_value=40, max_value=100, required=False)
    max_size = serializers.IntegerField(min_value=800, max_value=4096, required=False)

    def validate_image(self, value):
        if value.size > 20 * 1024 * 1024 or value.image.width * value.image.height > 24_000_000:
            raise serializers.ValidationError("Use uma foto de até 20 MB e 24 megapixels.")
        return value

    def validate_logo(self, value):
        return self.validate_image(value)

    def validate_watermark(self, value):
        serializer = WatermarkPreviewSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class ImagePreviewView(APIView):
    """Process an explicitly uploaded sample without saving images or settings."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = ImagePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        defaults = PreviewSettings.current()
        settings = {
            "quality": values.get("quality", defaults.quality),
            "maxSize": values.get("max_size", defaults.max_size),
        }
        if "watermark" in values:
            settings["watermark"] = values["watermark"]
        try:
            logo = values["logo"].read() if values.get("logo") else None
            asset = values.get("asset_id")
            if logo is None and asset and asset.logo and not values["remove_logo"]:
                with asset.logo.open("rb") as logo_file:
                    logo = logo_file.read()
            encoded, width, height = render_preview(values["image"].read(), settings, logo)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            raise serializers.ValidationError({"image": "Não foi possível processar a foto ou o logo."}) from error
        response = HttpResponse(encoded, content_type="image/webp")
        response["Cache-Control"] = "no-store"
        response["X-Image-Width"] = str(width)
        response["X-Image-Height"] = str(height)
        return response
