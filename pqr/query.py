from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class Op(str, Enum):
    EQ = "=="
    NEQ = "!="
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="
    IN = "in"


@dataclass(frozen=True)
class Condition:
    """
    A single predicate over a row (tuple).

    Notes:
    - Categorical predicates are typically `EQ`/`IN`.
    - Numeric predicates can use comparisons.
    """

    attr: str
    op: Op
    value: Any

    def matches(self, row: Mapping[str, Any]) -> bool:
        v = row.get(self.attr)
        if self.op == Op.EQ:
            return v == self.value
        if self.op == Op.NEQ:
            return v != self.value
        if self.op == Op.LT:
            return v < self.value
        if self.op == Op.LTE:
            return v <= self.value
        if self.op == Op.GT:
            return v > self.value
        if self.op == Op.GTE:
            return v >= self.value
        if self.op == Op.IN:
            return v in self.value
        raise ValueError(f"Unsupported op: {self.op}")


@dataclass(frozen=True)
class Query:
    """
    Minimal SPJ-style selection query for an in-memory table.

    This implementation models the “selection predicates” part used by the
    paper’s pseudocode (views are also predicates). Projection/join are out of
    scope for the draft and for this repo.
    """

    conditions: tuple[Condition, ...] = ()

    def where(self, *conds: Condition) -> "Query":
        return Query(self.conditions + tuple(conds))

    def apply(self, rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        if not self.conditions:
            return list(rows)
        out: list[Mapping[str, Any]] = []
        for r in rows:
            if all(c.matches(r) for c in self.conditions):
                out.append(r)
        return out

    def __call__(self, rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return self.apply(rows)


def active_domain(rows: Iterable[Mapping[str, Any]], attr: str) -> list[Any]:
    """
    Returns the (sorted, if possible) active domain values for attr.
    """

    vals = {r.get(attr) for r in rows}
    try:
        return sorted(vals)  # type: ignore[type-var]
    except TypeError:
        return list(vals)

