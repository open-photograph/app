from djmoney.contrib.django_rest_framework.fields import MoneyField
from rest_framework import serializers

from ..models import Photo, PhotoExif


class PhotoExifSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoExif
        fields = [
            "camera_make",
            "camera_model",
            "lens_model",
            "iso",
            "aperture",
            "shutter_speed",
            "focal_length",
            "exposure_compensation",
            "flash_fired",
            "software",
            "captured_at",
        ]


class PhotoSerializer(serializers.ModelSerializer):
    can_download = serializers.BooleanField(read_only=True)
    price = MoneyField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def validate_price(self, value):
        if value is not None and getattr(value, "amount", value) <= 0:
            raise serializers.ValidationError("O preco deve ser maior que zero.")
        return value

    exif = PhotoExifSerializer(read_only=True)

    class Meta:
        model = Photo
        fields = "__all__"
        read_only_fields = [
            "id",
            "source_user",
            "thumbnail",
            "preview",
            "width",
            "height",
            "size",
            "mime_type",
            "status",
            "created_at",
            "updated_at",
            "exif",
        ]


class PublicPhotoSerializer(serializers.ModelSerializer):
    """Explicit public contract; storage origins and administrative fields stay private."""

    preview = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    watermarked_preview = serializers.SerializerMethodField()
    can_download = serializers.BooleanField(read_only=True)
    price = serializers.SerializerMethodField()
    price_currency = serializers.SerializerMethodField()
    can_download_original = serializers.SerializerMethodField()

    def get_can_download_original(self, photo):
        return bool(
            photo.source_file_id
            and photo.source_user_id
            and (
                photo.gallery.included_photo_mode == "all"
                or (photo.gallery.included_photo_mode == "photographer" and photo.is_included)
                or photo.pk in self.context.get("included_ids", set())
            )
        )

    def get_price(self, photo):
        if self.get_can_download_original(photo):
            return None
        return format(photo.effective_price.amount, ".2f") if photo.effective_price is not None else None

    def get_price_currency(self, photo):
        return str(photo.effective_price.currency) if photo.effective_price is not None else photo.price_currency

    def _file_url(self, file):
        if not file:
            return None
        return self.context["request"].build_absolute_uri(file.url)

    def get_preview(self, photo):
        return self._file_url(photo.public_preview)

    def get_thumbnail(self, photo):
        file = photo.watermarked_preview if photo.gallery.watermark_enabled else photo.thumbnail
        return self._file_url(file)

    def get_watermarked_preview(self, photo):
        return self._file_url(photo.watermarked_preview) if photo.gallery.watermark_enabled else None

    class Meta:
        model = Photo
        fields = [
            "id",
            "gallery",
            "name",
            "thumbnail",
            "preview",
            "watermarked_preview",
            "width",
            "height",
            "size",
            "mime_type",
            "status",
            "position",
            "price",
            "price_currency",
            "taken_at",
            "created_at",
            "updated_at",
            "can_download",
            "can_download_original",
        ]
