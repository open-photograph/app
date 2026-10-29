from django.db import IntegrityError
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Photographer
from .serializers import PhotographerSerializer


class PhotographerViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = PhotographerSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["post"]

    def get_queryset(self):
        return Photographer.objects.none()

    def create(self, request, *args, **kwargs):
        if Photographer.objects.exists():
            return Response(
                {"detail": "O sistema já foi configurado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "Não foi possível concluir o setup."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"detail": "Fotógrafo criado com sucesso."},
            status=status.HTTP_201_CREATED,
        )
