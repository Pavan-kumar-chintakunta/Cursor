from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .engine import MatchingEngine
from .models import Cardinality, RuleSet


def _load_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # Maybe wrapped object with key like 'items'
        for key in ("items", "data", "records"):
            if key in data and isinstance(data[key], list):
                return list(data[key])
        raise ValueError("JSON must be an array or object with 'items'/'data'/'records' list")
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of objects")
    return list(data)


def _load_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _load_dataset(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    suffix = p.suffix.lower()
    if suffix in (".json", ".ndjson"):
        return _load_json(p)
    if suffix == ".csv":
        return _load_csv(p)
    raise ValueError("Unsupported dataset format. Use .csv or .json")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run relationship matching rules engine")
    parser.add_argument("left", help="Left dataset file (.csv or .json)")
    parser.add_argument("right", help="Right dataset file (.csv or .json)")
    parser.add_argument("rules", help="Rules YAML file")
    parser.add_argument("--cardinality", choices=[c.value for c in Cardinality], default=Cardinality.ONE_TO_MANY.value)
    parser.add_argument("--left-id", default="id")
    parser.add_argument("--right-id", default="id")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--output", default="-", help="Output file path or '-' for stdout")
    parser.add_argument("--format", choices=["json"], default="json")

    args = parser.parse_args(argv)

    left = _load_dataset(args.left)
    right = _load_dataset(args.right)
    ruleset = RuleSet.from_yaml_file(args.rules)

    engine = MatchingEngine()
    result = engine.match(
        left_records=left,
        right_records=right,
        ruleset=ruleset,
        cardinality=Cardinality(args.cardinality),
        left_id_field=args.left_id,
        right_id_field=args.right_id,
        top_k=args.top_k,
    )

    output = json.dumps(result.model_dump(), indent=2)
    if args.output == "-":
        print(output)
    else:
        Path(args.output).write_text(output, encoding="utf-8")
