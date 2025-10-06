from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import yaml


class Cardinality(str, Enum):
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"


class FieldComparatorConfig(BaseModel):
    left_field: str = Field(..., description="Field name on the left record")
    right_field: str = Field(..., description="Field name on the right record")
    comparator: str = Field(..., description="Registered comparator name")
    weight: float = Field(1.0, ge=0.0, description="Weight used in weighted aggregation")
    params: Dict[str, Any] | None = Field(default=None, description="Comparator parameters")
    must: bool = Field(False, description="If True, this field must meet threshold")
    threshold: float | None = Field(
        default=None,
        description="Optional per-field minimum score (0..1). If set and not met, the field fails.",
    )

    @field_validator("threshold")
    @classmethod
    def _validate_threshold(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not (0.0 <= v <= 1.0):
            raise ValueError("threshold must be between 0 and 1")
        return v


class Rule(BaseModel):
    name: str
    description: str | None = None
    priority: int = Field(100, description="Lower value means higher priority")
    cardinality: Cardinality = Field(Cardinality.ONE_TO_MANY)
    match_threshold: float = Field(0.8, ge=0.0, le=1.0)
    stop_on_first_rule_match: bool = Field(
        default=True,
        description=(
            "When True, if a pair meets this rule's threshold, do not evaluate further rules for the pair"
        ),
    )
    fields: List[FieldComparatorConfig]

    @field_validator("fields")
    @classmethod
    def _validate_fields_non_empty(cls, v: List[FieldComparatorConfig]) -> List[FieldComparatorConfig]:
        if not v:
            raise ValueError("Rule must define at least one field comparator")
        total_weight = sum(fc.weight for fc in v)
        if total_weight <= 0:
            raise ValueError("Sum of weights must be > 0")
        return v


class RuleSet(BaseModel):
    rules: List[Rule]

    @field_validator("rules")
    @classmethod
    def _validate_rules_non_empty(cls, v: List[Rule]) -> List[Rule]:
        if not v:
            raise ValueError("RuleSet must contain at least one rule")
        return sorted(v, key=lambda r: (r.priority, r.name))

    @classmethod
    def from_yaml(cls, yaml_text: str) -> "RuleSet":
        raw = yaml.safe_load(yaml_text)
        if not isinstance(raw, dict) or "rules" not in raw:
            raise ValueError("Rules YAML must be a mapping with a 'rules' key")
        return cls.model_validate(raw)

    @classmethod
    def from_yaml_file(cls, path: str) -> "RuleSet":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_yaml(f.read())


# Output models for matching/explainability

class FieldScore(BaseModel):
    left_field: str
    right_field: str
    comparator: str
    weight: float
    score: float
    passed: bool
    details: Dict[str, Any] | None = None


class PairScore(BaseModel):
    left_id: str
    right_id: str
    rule_name: str
    total_score: float
    matched: bool
    field_scores: List[FieldScore]
    weight_sum: float


class EngineResult(BaseModel):
    cardinality: Cardinality
    indexed_by: str = Field(description="Either 'left' or 'right' depending on cardinality")
    matches_index: Dict[str, List[PairScore]] = Field(
        default_factory=dict, description="Mapping of index id to list of PairScore"
    )
    unmatched_left_ids: List[str] = Field(default_factory=list)
    unmatched_right_ids: List[str] = Field(default_factory=list)
