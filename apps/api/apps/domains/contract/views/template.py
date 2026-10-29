from rest_framework.permissions import IsAdminUser
from rest_framework.viewsets import ModelViewSet

from ..models import ContractTemplate
from ..serializers import ContractTemplateSerializer


class ContractTemplateViewSet(ModelViewSet):
    queryset = ContractTemplate.objects.all()
    serializer_class = ContractTemplateSerializer
    permission_classes = [IsAdminUser]
    search_fields = ["name"]
