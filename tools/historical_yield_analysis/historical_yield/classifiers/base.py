"""Classifier provider protocol and registry."""

from __future__ import annotations

from typing import Dict, Optional, Protocol, runtime_checkable

from ..models import ClassificationResult, SampleMeta


@runtime_checkable
class ClassifierProvider(Protocol):
    """Pluggable classifier interface.

    Version 1 uses ManualExcelClassifier. A future automatic classifier can
    implement the same classify() contract and register under a new id.
    """

    classifier_id: str
    classifier_version: str

    def classify(
        self,
        source_path: str,
        sample: SampleMeta,
        *,
        success_categories: Optional[list[str]] = None,
    ) -> ClassificationResult:
        ...


_REGISTRY: Dict[str, ClassifierProvider] = {}


def register_classifier(provider: ClassifierProvider) -> ClassifierProvider:
    _REGISTRY[provider.classifier_id] = provider
    return provider


def get_classifier(classifier_id: str) -> ClassifierProvider:
    if classifier_id not in _REGISTRY:
        # Lazy import default providers
        from . import manual_excel  # noqa: F401

        if classifier_id not in _REGISTRY:
            known = ", ".join(sorted(_REGISTRY)) or "(none)"
            raise KeyError(f"Unknown classifier {classifier_id!r}. Known: {known}")
    return _REGISTRY[classifier_id]


def list_classifiers() -> list[str]:
    from . import manual_excel  # noqa: F401

    return sorted(_REGISTRY)
