from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import PreviewSettings


class PreviewSettingsSerializer(serializers.ModelSerializer):
    quality = serializers.IntegerField(min_value=40, max_value=100)
    max_size = serializers.IntegerField(min_value=800, max_value=4096)

    class Meta:
        model = PreviewSettings
        fields = ["quality", "max_size"]


class PreviewSettingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(PreviewSettingsSerializer(PreviewSettings.current()).data)

    def patch(self, request):
        serializer = PreviewSettingsSerializer(PreviewSettings.current(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def post(self, request):
        from ..tasks import regenerate_previews

        regenerate_previews.enqueue()
        return Response({"detail": "Reprocessamento de prévias enfileirado."}, status=status.HTTP_202_ACCEPTED)
