"""Shared data models for historical yield analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# Canonical normalized classification labels used throughout analysis/plots.
CANONICAL_CATEGORIES = (
    "memristive",
    "ohmic",
    "capacitive",
    "conductive",
    "non_conductive",
    "mem_capacitive",
    "intermittent",
    "other",
    "unknown",
)

# Display labels for plots / CSV exports.
CATEGORY_DISPLAY = {
    "memristive": "Memristive",
    "ohmic": "Ohmic",
    "capacitive": "Capacitive",
    "conductive": "Conductive",
    "non_conductive": "Non-Conductive",
    "mem_capacitive": "Mem-Capacitive",
    "intermittent": "Intermittent",
    "other": "Other",
    "unknown": "Unknown",
}


@dataclass
class SampleMeta:
    sample_id: str  # e.g. D95
    sample_number: int  # 95
    sample_name: str  # full stem / folder name
    concentration_raw: Optional[str] = None
    concentration_mgml: Optional[float] = None  # Stock -> 0.0
    is_stock: bool = False
    bottom_electrode: Optional[str] = None
    polymer: Optional[str] = None
    polymer_percent: Optional[float] = None
    top_electrode: Optional[str] = None
    solution_tag: Optional[str] = None  # e.g. s3
    material_hint: Optional[str] = None  # from parent folders if available


@dataclass
class DeviceClassification:
    section: str
    device_number: int
    raw_classification: Optional[str]
    normalized_classification: str
    is_classified: bool
    is_yield_success: bool
    memristor_strength: Optional[str] = None
    current_range: Optional[str] = None
    resistance_value: Optional[str] = None
    n_sweeps: Optional[str] = None
    retention: Optional[str] = None
    endurance: Optional[str] = None
    volatile: Optional[str] = None
    current_state: Optional[str] = None
    date_measured: Optional[str] = None
    notes: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbookImportResult:
    source_path: str
    root_name: str
    root_priority: int
    sample: SampleMeta
    fingerprint: str
    file_size: int
    mtime_ns: int
    status: str  # ok | malformed | skipped | duplicate_rejected | parse_error
    devices: List[DeviceClassification] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_header: Optional[str] = None
    classifier_id: str = "manual_excel"
    classifier_version: str = "1"
    accepted: bool = True
    duplicate_of: Optional[str] = None

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "root_name": self.root_name,
            "root_priority": self.root_priority,
            "sample_id": self.sample.sample_id,
            "sample_name": self.sample.sample_name,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "accepted": self.accepted,
            "duplicate_of": self.duplicate_of,
            "n_devices": len(self.devices),
            "n_classified": sum(1 for d in self.devices if d.is_classified),
            "n_yield_success": sum(1 for d in self.devices if d.is_yield_success),
            "warnings": list(self.warnings),
            "schema_header": self.schema_header,
            "classifier_id": self.classifier_id,
            "classifier_version": self.classifier_version,
        }


@dataclass
class ClassificationResult:
    """Normalized result shared by all classifier providers."""

    classifier_id: str
    classifier_version: str
    sample: SampleMeta
    devices: List[DeviceClassification]
    warnings: List[str] = field(default_factory=list)
    schema_header: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SampleYieldSummary:
    sample_id: str
    sample_number: int
    sample_name: str
    n_device_rows: int
    n_classified: int
    n_blank: int
    n_memristive: int
    n_ohmic: int
    n_capacitive: int
    n_conductive: int
    n_non_conductive: int
    n_mem_capacitive: int
    n_intermittent: int
    n_other: int
    strict_yield: float  # memristive / classified (0 if no classified)
    composition: Dict[str, float]  # fraction of classified
    concentration_mgml: Optional[float]
    is_stock: bool
    polymer: Optional[str]
    bottom_electrode: Optional[str]
    top_electrode: Optional[str]
    source_path: str
    root_name: str
    warnings: List[str] = field(default_factory=list)
