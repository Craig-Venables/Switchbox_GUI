"""Manual Excel classification provider (version 1)."""

from __future__ import annotations

from typing import Optional

from ..models import ClassificationResult, SampleMeta
from ..workbook import load_workbook_devices
from .base import register_classifier


class ManualExcelClassifier:
    classifier_id = "manual_excel"
    classifier_version = "1"

    def classify(
        self,
        source_path: str,
        sample: SampleMeta,
        *,
        success_categories: Optional[list[str]] = None,
    ) -> ClassificationResult:
        devices, warnings, schema_header = load_workbook_devices(
            source_path, success_categories=success_categories
        )
        return ClassificationResult(
            classifier_id=self.classifier_id,
            classifier_version=self.classifier_version,
            sample=sample,
            devices=devices,
            warnings=warnings,
            schema_header=schema_header,
        )


register_classifier(ManualExcelClassifier())
