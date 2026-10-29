from django.db import transaction
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from ..models import WatermarkAsset
from ..serializers.watermark import WatermarkAssetSerializer


class WatermarkAssetViewSet(viewsets.ModelViewSet):
    """
    CRUD de configurações de marca d'água.

    Apenas administradores podem gerenciar WatermarkAssets.
    """

    queryset = WatermarkAsset.objects.all()
    serializer_class = WatermarkAssetSerializer
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def perform_create(self, serializer):
        if serializer.validated_data.get("is_default"):
            WatermarkAsset.objects.filter(is_default=True).update(is_default=False)
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        if serializer.validated_data.get("is_default"):
            WatermarkAsset.objects.filter(is_default=True).exclude(pk=serializer.instance.pk).update(is_default=False)
        serializer.save()
