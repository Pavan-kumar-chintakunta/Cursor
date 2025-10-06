from __future__ import annotations

from pathlib import Path
import json

from relmatch.engine import MatchingEngine
from relmatch.models import Cardinality, RuleSet


def test_examples_roundtrip():
    rules = RuleSet.from_yaml_file("examples/rules.yaml")
    engine = MatchingEngine()

    # Load CSV via CLI loader equivalents
    import csv

    left = [dict(r) for r in csv.DictReader(Path("examples/left_customers.csv").open("r", encoding="utf-8"))]
    right = [dict(r) for r in csv.DictReader(Path("examples/right_accounts.csv").open("r", encoding="utf-8"))]

    # Left indexed (one-to-many)
    res_left = engine.match(left, right, rules, Cardinality.ONE_TO_MANY, top_k=1)

    # Expect at least the email exact rule to match L1->R10
    l1_matches = res_left.matches_index.get("L1")
    assert l1_matches and l1_matches[0].right_id == "R10" and l1_matches[0].matched

    # Right indexed (many-to-one)
    res_right = engine.match(left, right, rules, Cardinality.MANY_TO_ONE, top_k=1)
    r10_matches = res_right.matches_index.get("R10")
    assert r10_matches and r10_matches[0].left_id == "L1" and r10_matches[0].matched
