import uuid

from django.db import models


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    GENERATING = "generating", "Gerando link"
    PENDING = "pending", "Aguardando assinatura"
    SIGNED = "signed", "Assinado"
    UNCERTAIN = "uncertain", "Verificar no provider"


class Contract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    template = models.ForeignKey("contract.ContractTemplate", on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey("client.Client", on_delete=models.PROTECT, related_name="contracts")
    signature_provider = models.ForeignKey(
        "contract.SignatureProvider", on_delete=models.PROTECT, related_name="contracts"
    )
    provider_environment = models.CharField(max_length=20, blank=True, default="")
    content = models.TextField()
    signer_name = models.CharField(max_length=255)
    signer_email = models.EmailField()
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    provider_document_id = models.CharField(max_length=255, blank=True)
    signing_url = models.URLField(max_length=2000, blank=True)
    last_error = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
