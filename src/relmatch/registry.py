from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

ComparatorFunc = Callable[[Any, Any, Dict[str, Any] | None, Dict[str, Any] | None], Tuple[float, Dict[str, Any]]]


class ComparatorRegistry:
    def __init__(self) -> None:
        self._name_to_comparator: dict[str, ComparatorFunc] = {}
        self._name_to_description: dict[str, str] = {}

    def register(self, name: str, func: ComparatorFunc, description: str | None = None) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Comparator name cannot be empty")
        self._name_to_comparator[normalized] = func
        if description:
            self._name_to_description[normalized] = description

    def get(self, name: str) -> ComparatorFunc:
        normalized = name.strip().lower()
        try:
            return self._name_to_comparator[normalized]
        except KeyError as exc:
            available = ", ".join(sorted(self._name_to_comparator))
            raise KeyError(f"Comparator '{name}' not found. Available: {available}") from exc

    def describe(self, name: str) -> str | None:
        return self._name_to_description.get(name.strip().lower())

    def names(self) -> list[str]:
        return sorted(self._name_to_comparator.keys())

    def evaluate(
        self,
        name: str,
        left_value: Any,
        right_value: Any,
        context: Dict[str, Any] | None = None,
        params: Dict[str, Any] | None = None,
    ) -> Tuple[float, Dict[str, Any]]:
        comparator = self.get(name)
        return comparator(left_value, right_value, context, params)


# Default registry with built-in comparators populated in comparators.py
default_registry = ComparatorRegistry()
