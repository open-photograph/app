from rest_framework import serializers


class GoogleDriveFolderSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    mime_type = serializers.CharField()
    path = serializers.CharField()


class GoogleDriveFileSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    parent_id = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
