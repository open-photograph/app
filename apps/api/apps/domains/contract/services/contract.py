import re

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.integrations.signature.base import SignatureProviderError
from apps.integrations.signature.credentials import get_signature_environment
from apps.integrations.signature.registry import get_signature_provider

from ..models import Contract, ContractStatus

AUTOMATIC_VARIABLES = ("cliente.nome", "cliente.email", "contrato.titulo", "data")


def variable_name(value):
    variable = value.strip()
    # Older editor content may contain autolinks inside a placeholder.
    autolink = re.fullmatch(r"\[([^\[\]]+)\]\(https?://\1/?\)", variable)
    return autolink.group(1).strip() if autolink else variable


def extract_variables(content):
    return list(
        dict.fromkeys(
            variable_name(match.group(1))
            for match in re.finditer(r"\{\{([^{}\r\n]+)\}\}", content)
            if variable_name(match.group(1))
        )
    )


def render_content(content, *, client, title, variables=None):
    names = extract_variables(content)
    supplied = variables or {}
    extra = set(supplied) - set(names)
    if extra:
        raise ValidationError({"variables": "Envie valores apenas para as variáveis presentes no template."})
    values = {
        "cliente.nome": client.name,
        "cliente.email": client.email,
        "contrato.titulo": title,
        "data": timezone.localdate().strftime("%d/%m/%Y"),
        **supplied,
    }
    missing = {name: f'Preencha a variável "{name}" do template.' for name in names if not values.get(name, "").strip()}
    if missing:
        raise ValidationError({"variables": missing})

    def replace(match):
        variable = variable_name(match.group(1))
        if not variable:
            raise ValidationError({"content": "Use um nome entre as chaves da variável."})
        # Keep substituted values literal in the Markdown document, including user-provided markup.
        return re.sub(r"([\\`*_{}\[\]()<>#+.!|~-])", r"\\\1", values[variable])

    return re.sub(r"\{\{([^{}\r\n]+)\}\}", replace, content)


def apply_document(contract, document):
    signed_at = parse_datetime(document.signed_at) if document.signed_at else None
    if signed_at and timezone.is_naive(signed_at):
        signed_at = timezone.make_aware(signed_at)
    with transaction.atomic():
        current = Contract.objects.select_for_update().get(pk=contract.pk)
        current.provider_document_id = document.document_id
        if document.signing_url:
            current.signing_url = document.signing_url
        # A delayed pending response must not undo a previously confirmed signature.
        if current.status != ContractStatus.SIGNED:
            current.status = ContractStatus.SIGNED if document.status == "signed" else ContractStatus.PENDING
        if signed_at:
            current.signed_at = signed_at
        current.last_synced_at = timezone.now()
        current.last_error = ""
        current.save(
            update_fields=[
                "provider_document_id",
                "signing_url",
                "status",
                "signed_at",
                "last_synced_at",
                "last_error",
                "updated_at",
            ]
        )
    contract.refresh_from_db()


def generate_link(contract_id):
    with transaction.atomic():
        contract = Contract.objects.select_for_update().select_related("signature_provider").get(pk=contract_id)
        if contract.signing_url:
            return contract
        if contract.status != ContractStatus.DRAFT:
            raise ValidationError("Verifique o documento no provider antes de gerar outro link.")
        if not contract.signature_provider.is_active:
            raise ValidationError("Ative a configuração do provider antes de gerar o link.")
        contract.provider_environment = get_signature_environment()
        provider = get_signature_provider(contract.signature_provider, environment=contract.provider_environment)
        contract.status = ContractStatus.GENERATING
        contract.last_error = ""
        contract.save(update_fields=["status", "provider_environment", "last_error", "updated_at"])
    try:
        document = provider.create_document(
            title=contract.title,
            content=contract.content,
            signer_name=contract.signer_name,
            signer_email=contract.signer_email,
            external_id=contract.id,
        )
    except SignatureProviderError as error:
        contract.status = ContractStatus.UNCERTAIN if error.uncertain else ContractStatus.DRAFT
        contract.last_error = str(error)
        contract.save(update_fields=["status", "provider_environment", "last_error", "updated_at"])
        raise ValidationError(str(error)) from error
    apply_document(contract, document)
    return contract


def sync_document(contract):
    if not contract.provider_document_id:
        raise ValidationError("Este contrato ainda não possui documento no provider.")
    provider = get_signature_provider(contract.signature_provider, environment=contract.provider_environment)
    document = provider.get_document(contract.provider_document_id)
    if document.document_id != contract.provider_document_id:
        raise ValidationError("O provider retornou um documento diferente do contrato.")
    apply_document(contract, document)
    return document


def recover_document(contract, document_id):
    if contract.status not in {ContractStatus.UNCERTAIN, ContractStatus.GENERATING}:
        raise ValidationError("A recuperação só está disponível para criações não confirmadas.")
    provider = get_signature_provider(contract.signature_provider, environment=contract.provider_environment)
    document = provider.get_document(document_id)
    if document.document_id != document_id or document.external_id != str(contract.id) or not document.signing_url:
        raise ValidationError("O documento não pertence a este contrato ou não possui link de assinatura.")
    apply_document(contract, document)
    return contract
