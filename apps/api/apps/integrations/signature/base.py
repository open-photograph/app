from abc import ABC, abstractmethod
from dataclasses import dataclass


class SignatureProviderError(Exception):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


@dataclass(frozen=True)
class SignatureDocument:
    document_id: str
    status: str
    signing_url: str = ""
    signed_at: str | None = None
    signed_file: str = ""
    external_id: str = ""


class BaseSignatureProvider(ABC):
    @abstractmethod
    def create_document(self, *, title, content, signer_name, signer_email, external_id) -> SignatureDocument: ...

    @abstractmethod
    def get_document(self, document_id) -> SignatureDocument: ...
