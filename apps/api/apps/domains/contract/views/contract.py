from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.integrations.signature.base import SignatureProviderError

from ..models import Contract, ContractStatus
from ..serializers import ContractSerializer
from ..services.contract import generate_link, recover_document, sync_document


class ContractViewSet(ModelViewSet):
    queryset = Contract.objects.select_related("client", "template", "signature_provider")
    serializer_class = ContractSerializer
    permission_classes = [IsAdminUser]
    search_fields = ["title", "signer_name", "signer_email"]

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            self.queryset = self.queryset.select_for_update(of=("self",))
            return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        if serializer.instance.status != ContractStatus.DRAFT:
            raise ValidationError("Somente rascunhos podem ser alterados.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            self.queryset = self.queryset.select_for_update(of=("self",))
            return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.status != ContractStatus.DRAFT:
            raise ValidationError("Somente rascunhos podem ser excluídos.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="generate-link")
    def generate(self, request, pk=None):
        self.get_object()
        try:
            contract = generate_link(pk)
        except SignatureProviderError as error:
            raise ValidationError(str(error)) from error
        return Response(self.get_serializer(contract).data)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        contract = self.get_object()
        try:
            sync_document(contract)
        except SignatureProviderError as error:
            raise ValidationError(str(error)) from error
        return Response(self.get_serializer(contract).data)

    @action(detail=True, methods=["get"], url_path="signed-file")
    def signed_file(self, request, pk=None):
        contract = self.get_object()
        try:
            document = sync_document(contract)
        except SignatureProviderError as error:
            raise ValidationError(str(error)) from error
        if document.status != "signed" or not document.signed_file:
            raise ValidationError("O documento assinado ainda não está disponível.")
        # Provider download URLs may expire; obtain a fresh URL for each request.
        return Response({"url": document.signed_file})

    @action(detail=True, methods=["post"])
    def recover(self, request, pk=None):
        contract = self.get_object()
        document_id = serializers.CharField(max_length=255).run_validation(request.data.get("document_id"))
        try:
            recover_document(contract, document_id)
        except SignatureProviderError as error:
            raise ValidationError(str(error)) from error
        return Response(self.get_serializer(contract).data)
