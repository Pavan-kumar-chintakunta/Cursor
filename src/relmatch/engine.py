from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .models import (
    Cardinality,
    Rule,
    RuleSet,
    FieldScore,
    PairScore,
    EngineResult,
)
from .registry import ComparatorRegistry, default_registry


class MatchingEngine:
    def __init__(
        self,
        registry: ComparatorRegistry | None = None,
    ) -> None:
        self.registry = registry or default_registry

    def _score_pair(self, left: Dict[str, Any], right: Dict[str, Any], rule: Rule) -> PairScore:
        field_scores: List[FieldScore] = []
        total_weight = sum(fc.weight for fc in rule.fields)
        weighted_sum = 0.0
        all_must_pass = True
        for fc in rule.fields:
            left_value = left.get(fc.left_field)
            right_value = right.get(fc.right_field)
            score, details = self.registry.evaluate(
                name=fc.comparator,
                left_value=left_value,
                right_value=right_value,
                context={"left": left, "right": right, "rule": rule.model_dump()},
                params=fc.params or {},
            )
            passed = (score >= (fc.threshold if fc.threshold is not None else 0.0))
            if fc.must and not passed:
                all_must_pass = False
            weighted_sum += score * fc.weight
            field_scores.append(
                FieldScore(
                    left_field=fc.left_field,
                    right_field=fc.right_field,
                    comparator=fc.comparator,
                    weight=fc.weight,
                    score=score,
                    passed=passed,
                    details=details,
                )
            )
        total_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        matched = all_must_pass and total_score >= rule.match_threshold
        return PairScore(
            left_id=str(left.get("id", "<no-id>")),
            right_id=str(right.get("id", "<no-id>")),
            rule_name=rule.name,
            total_score=total_score,
            matched=matched,
            field_scores=field_scores,
            weight_sum=total_weight,
        )

    def _evaluate_rules_for_pair(
        self, left: Dict[str, Any], right: Dict[str, Any], rules: List[Rule]
    ) -> PairScore:
        best: PairScore | None = None
        for rule in rules:
            pair_score = self._score_pair(left, right, rule)
            if pair_score.matched:
                # Prefer the first matching rule due to sorted by priority
                return pair_score
            # Track best score (optional)
            if best is None or pair_score.total_score > best.total_score:
                best = pair_score
        # If none matched, return the best scoring pair (not matched)
        return best or self._score_pair(left, right, rules[0])

    def match(
        self,
        left_records: Iterable[Dict[str, Any]],
        right_records: Iterable[Dict[str, Any]],
        ruleset: RuleSet,
        cardinality: Cardinality,
        *,
        left_id_field: str = "id",
        right_id_field: str = "id",
        top_k: int | None = None,
    ) -> EngineResult:
        # Prepare lists to allow multi-pass
        left_list = list(left_records)
        right_list = list(right_records)
        rules = ruleset.rules

        # Index by left or right depending on cardinality
        index_side = "left" if cardinality == Cardinality.ONE_TO_MANY else "right"
        result = EngineResult(cardinality=cardinality, indexed_by=index_side)

        # Build map id->record
        left_map: Dict[str, Dict[str, Any]] = {str(r.get(left_id_field)): r for r in left_list}
        right_map: Dict[str, Dict[str, Any]] = {str(r.get(right_id_field)): r for r in right_list}

        # For each index-side record, evaluate against all of the other side
        if index_side == "left":
            for left in left_list:
                left_id = str(left.get(left_id_field))
                scores: List[PairScore] = []
                for right in right_list:
                    scores.append(self._evaluate_rules_for_pair(left, right, rules))
                # Filter only matches
                matches = [s for s in scores if s.matched]
                if not matches:
                    result.unmatched_left_ids.append(left_id)
                    continue
                # Sort by score desc, then rule priority/lex
                matches.sort(key=lambda s: (-s.total_score, s.rule_name))
                if top_k is not None:
                    matches = matches[:top_k]
                result.matches_index[left_id] = matches
            # Unmatched right ids are those never appearing in right_id in any match
            matched_right_ids = {s.right_id for lst in result.matches_index.values() for s in lst}
            result.unmatched_right_ids = [rid for rid in right_map.keys() if rid not in matched_right_ids]
        else:
            for right in right_list:
                right_id = str(right.get(right_id_field))
                scores = []
                for left in left_list:
                    scores.append(self._evaluate_rules_for_pair(left, right, rules))
                matches = [s for s in scores if s.matched]
                if not matches:
                    result.unmatched_right_ids.append(right_id)
                    continue
                matches.sort(key=lambda s: (-s.total_score, s.rule_name))
                if top_k is not None:
                    matches = matches[:top_k]
                result.matches_index[right_id] = matches
            matched_left_ids = {s.left_id for lst in result.matches_index.values() for s in lst}
            result.unmatched_left_ids = [lid for lid in left_map.keys() if lid not in matched_left_ids]

        return result
