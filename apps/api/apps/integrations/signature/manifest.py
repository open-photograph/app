from collections.abc import Callable
from dataclasses import dataclass

from .base import BaseSignatureProvider


@dataclass(frozen=True)
class SignatureProviderManifest:
    value: str
    label: str
    docs_url: str
    factory: Callable[[str], BaseSignatureProvider]

    def catalog_entry(self):
        return {"value": self.value, "label": self.label, "docs_url": self.docs_url}
