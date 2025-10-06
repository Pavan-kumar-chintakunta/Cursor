from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Iterable, Tuple
import re
from difflib import SequenceMatcher

from .registry import default_registry, ComparatorRegistry


def _to_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return str(value)


def _normalize_text(value: Any, *, case_insensitive: bool = True, strip: bool = True) -> str | None:
    s = _to_string(value)
    if s is None:
        return None
    if strip:
        s = s.strip()
    if case_insensitive:
        s = s.lower()
    return s


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    s = _to_string(value)
    if s is None:
        return None
    s = s.strip()
    # Try ISO formats first
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        pass
    # Try common formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    # As a last resort, try dateutil if available
    try:
        from dateutil import parser as dateutil_parser  # type: ignore

        return dateutil_parser.parse(s).date()
    except Exception:
        return None


# Comparator functions return (score, details)

def cmp_exact(left: Any, right: Any, _context: Dict[str, Any] | None, _params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    return (1.0, {"match": True}) if left == right and left is not None else (0.0, {"match": False})


def cmp_icase_exact(left: Any, right: Any, _context: Dict[str, Any] | None, params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    li = _normalize_text(left, case_insensitive=True)
    ri = _normalize_text(right, case_insensitive=True)
    if li is None or ri is None:
        return 0.0, {"reason": "missing"}
    return (1.0, {"match": True}) if li == ri else (0.0, {"match": False})


def cmp_ratio(left: Any, right: Any, _context: Dict[str, Any] | None, params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    if params is None:
        params = {}
    case_insensitive = bool(params.get("case_insensitive", True))
    li = _normalize_text(left, case_insensitive=case_insensitive)
    ri = _normalize_text(right, case_insensitive=case_insensitive)
    if li is None or ri is None:
        return 0.0, {"reason": "missing"}
    ratio = SequenceMatcher(None, li, ri).ratio()
    return ratio, {"ratio": ratio}


def _tokens(s: str, *, min_token_len: int) -> set[str]:
    # Split on non-alphanumeric and collapse
    raw = re.split(r"[^0-9a-zA-Z]+", s)
    return {t for t in raw if len(t) >= min_token_len}


def cmp_jaccard(left: Any, right: Any, _context: Dict[str, Any] | None, params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    if params is None:
        params = {}
    case_insensitive = bool(params.get("case_insensitive", True))
    min_token_len = int(params.get("min_token_len", 2))
    li = _normalize_text(left, case_insensitive=case_insensitive)
    ri = _normalize_text(right, case_insensitive=case_insensitive)
    if li is None or ri is None:
        return 0.0, {"reason": "missing"}
    lt = _tokens(li, min_token_len=min_token_len)
    rt = _tokens(ri, min_token_len=min_token_len)
    if not lt and not rt:
        return 0.0, {"reason": "no_tokens"}
    intersection = lt & rt
    union = lt | rt
    score = len(intersection) / len(union)
    return score, {"intersection": sorted(intersection), "union_size": len(union)}


def cmp_contains(left: Any, right: Any, _context: Dict[str, Any] | None, params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    if params is None:
        params = {}
    case_insensitive = bool(params.get("case_insensitive", True))
    # direction: 'left_in_right' or 'right_in_left'
    direction = str(params.get("direction", "left_in_right"))
    li = _normalize_text(left, case_insensitive=case_insensitive)
    ri = _normalize_text(right, case_insensitive=case_insensitive)
    if li is None or ri is None:
        return 0.0, {"reason": "missing"}
    if direction == "left_in_right":
        found = li in ri
        return (1.0 if found else 0.0), {"found": found, "direction": direction}
    if direction == "right_in_left":
        found = ri in li
        return (1.0 if found else 0.0), {"found": found, "direction": direction}
    return 0.0, {"reason": "bad_direction", "direction": direction}


def cmp_numeric_distance(left: Any, right: Any, _context: Dict[str, Any] | None, params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    if params is None:
        params = {}
    max_distance = float(params.get("max_distance", 1.0))
    lf = _safe_float(left)
    rf = _safe_float(right)
    if lf is None or rf is None:
        return 0.0, {"reason": "not_numeric"}
    diff = abs(lf - rf)
    score = max(0.0, 1.0 - (diff / max_distance))
    return score, {"difference": diff, "max_distance": max_distance}


def cmp_date_distance_days(left: Any, right: Any, _context: Dict[str, Any] | None, params: Dict[str, Any] | None) -> Tuple[float, Dict[str, Any]]:
    if params is None:
        params = {}
    max_days = int(params.get("max_days", 1))
    ld = _parse_date(left)
    rd = _parse_date(right)
    if ld is None or rd is None:
        return 0.0, {"reason": "not_date"}
    days = abs((ld - rd).days)
    score = max(0.0, 1.0 - (days / max_days))
    return score, {"days": days, "max_days": max_days}


# Register default comparators

def register_default_comparators(registry: ComparatorRegistry) -> None:
    registry.register("exact", cmp_exact, "Exact equality comparison (case sensitive)")
    registry.register("icase_exact", cmp_icase_exact, "Exact equality ignoring case and surrounding spaces")
    registry.register("ratio", cmp_ratio, "SequenceMatcher similarity ratio (0..1)")
    registry.register("jaccard", cmp_jaccard, "Jaccard similarity of token sets")
    registry.register("contains", cmp_contains, "Substring containment with direction and case options")
    registry.register("numeric_distance", cmp_numeric_distance, "Numeric distance scaled to 0..1 by max_distance")
    registry.register("date_distance_days", cmp_date_distance_days, "Date distance in days scaled by max_days")


register_default_comparators(default_registry)
