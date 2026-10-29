from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.integrations.signature.registry import signature_provider_registry

from ..models import SignatureProvider
from ..serializers import SignatureProviderSerializer


class SignatureProviderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SignatureProvider.objects.all()
    serializer_class = SignatureProviderSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None

    @action(detail=False, methods=["get"])
    def catalog(self, request):
        return Response({"providers": signature_provider_registry.catalog()})
