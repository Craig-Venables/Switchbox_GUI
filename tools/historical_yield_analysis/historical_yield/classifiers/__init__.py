"""Classifier package."""

from .base import ClassifierProvider, get_classifier, list_classifiers, register_classifier
from .manual_excel import ManualExcelClassifier

__all__ = [
    "ClassifierProvider",
    "ManualExcelClassifier",
    "get_classifier",
    "list_classifiers",
    "register_classifier",
]
