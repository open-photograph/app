from rest_framework import serializers

from ..models import GallerySelection, PhotoComment


class LikeInputSerializer(serializers.Serializer):
    photo_id = serializers.UUIDField()
    liked = serializers.BooleanField()


class CommentInputSerializer(serializers.Serializer):
    photo_id = serializers.UUIDField()
    text = serializers.CharField(max_length=2000)


class SelectionInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    photo_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=1000)


class PhotoCommentSerializer(serializers.ModelSerializer):
    photo_name = serializers.CharField(source="photo.name", read_only=True)

    class Meta:
        model = PhotoComment
        fields = ["id", "photo", "photo_name", "name", "text", "created_at"]


class SelectionPhotoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class GallerySelectionSerializer(serializers.ModelSerializer):
    photos = SelectionPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = GallerySelection
        fields = ["id", "name", "email", "message", "photos", "created_at"]
