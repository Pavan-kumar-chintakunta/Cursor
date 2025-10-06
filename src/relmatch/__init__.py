from .engine import MatchingEngine
from .models import (
    Rule,
    RuleSet,
    FieldComparatorConfig,
    Cardinality,
)
from .registry import ComparatorRegistry, default_registry

# Ensure built-in comparators are registered on package import
from . import comparators as _comparators  # noqa: F401

__all__ = [
    "MatchingEngine",
    "Rule",
    "RuleSet",
    "FieldComparatorConfig",
    "Cardinality",
    "ComparatorRegistry",
    "default_registry",
]
