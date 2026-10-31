"""Query refinement under output constraints (Definitions 2.4-2.5), ERICA-style.

The paper obtains ``Q'`` for the refinement pairs by running ERICA (Li et al.,
VLDB 2023) on ``Q`` and a representation constraint.  This module is a
compact re-implementation of that search for conjunctive queries:

* every atomic condition may be kept, have its constant changed (numerical:
  any candidate threshold; categorical ``=``/``IN``: add or remove up to
  ``max_set_edits`` values), or be dropped;
* a refinement must satisfy every constraint (cardinality or proportional);
* among the satisfying refinements the one with the smallest predicate
  distance is returned (ties: smallest Jaccard distance between outputs).

The predicate distance follows ERICA's predicate-based measure: for a numeric
condition ``|c - c'| / range(A)``, for a categorical one the Jaccard distance
of the value sets, and 1 for a dropped condition.

The framework itself treats ``Q'`` as a black box (Section 2.2); this module
only *produces* the pairs A3, T2, T3 whose refined queries the paper leaves TBD.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

import numpy as np
import pandas as pd

from .query import And, Atom, Predicate, TrueP, conjuncts, parse


@dataclass(frozen=True)
class Constraint:
    """Output constraint on a group of tuples (Definition 2.4).

    The group is either ``attr IN values`` (``values`` a tuple; a single value is
    the equality constraint ``G = g``) or an arbitrary predicate ``where``.
    Cardinality constraint: ``min_count <= |{t in T : t in group}| <= max_count``;
    proportional constraint: the same with the fraction of ``|T|`` (``min_share`` /
    ``max_share``).
    """

    attr: str | None = None
    values: tuple = ()
    min_share: float | None = None
    max_share: float | None = None
    min_count: int | None = None
    max_count: int | None = None
    where: str | None = None

    @staticmethod
    def from_dict(d: dict) -> "Constraint":
        if "where" in d:
            return Constraint(None, (), d.get("min_share"), d.get("max_share"), d.get("min_count"),
                              d.get("max_count"), d["where"])
        v = d["value"] if "value" in d else d["values"]
        v = tuple(v) if isinstance(v, (list, tuple)) else (v,)
        return Constraint(d["attr"], v, d.get("min_share"), d.get("max_share"), d.get("min_count"), d.get("max_count"))

    def group_mask(self, df: pd.DataFrame) -> np.ndarray:
        if self.where is not None:
            return parse(self.where).evaluate(df)
        return Atom(self.attr, "IN", self.values).evaluate(df)

    def share(self, df: pd.DataFrame, mask: np.ndarray) -> float:
        n = int(mask.sum())
        return float("nan") if n == 0 else float((self.group_mask(df) & mask).sum() / n)

    def satisfied_counts(self, group_count: np.ndarray, size: np.ndarray) -> np.ndarray:
        ok = size > 0
        with np.errstate(divide="ignore", invalid="ignore"):
            share = np.where(size > 0, group_count / np.maximum(size, 1), 0.0)
        if self.min_share is not None:
            ok &= share >= self.min_share
        if self.max_share is not None:
            ok &= share <= self.max_share
        if self.min_count is not None:
            ok &= group_count >= self.min_count
        if self.max_count is not None:
            ok &= group_count <= self.max_count
        return ok

    def group_sql(self) -> str:
        if self.where is not None:
            return self.where
        if len(self.values) == 1:
            return Atom(self.attr, "=", self.values[0]).to_sql()
        return Atom(self.attr, "IN", self.values).to_sql()

    def describe(self) -> str:
        parts = []
        if self.min_share is not None:
            parts.append(f">= {self.min_share:.0%}")
        if self.max_share is not None:
            parts.append(f"<= {self.max_share:.0%}")
        if self.min_count is not None:
            parts.append(f">= {self.min_count} tuples")
        if self.max_count is not None:
            parts.append(f"<= {self.max_count} tuples")
        return f"{' and '.join(parts)} with {self.group_sql()}"


@dataclass
class _Option:
    pred: Predicate  # TrueP() when dropped
    distance: float
    mask: np.ndarray


def _numeric_thresholds(x: np.ndarray, max_candidates: int) -> np.ndarray:
    u = np.unique(x[~np.isnan(x)])
    if len(u) <= max_candidates:
        return u
    return np.unique(np.quantile(x[~np.isnan(x)], np.linspace(0, 1, max_candidates)))


def _atom_options(atom: Atom, df: pd.DataFrame, max_set_edits: int, max_thresholds: int, allow_drop: bool,
                  max_domain: int = 60) -> list[_Option]:
    opts = [_Option(atom, 0.0, atom.evaluate(df))]
    if allow_drop:
        opts.append(_Option(TrueP(), 1.0, np.ones(len(df), dtype=bool)))
    if atom.op in ("<", "<=", ">", ">="):
        x = pd.to_numeric(df[atom.attr], errors="coerce").to_numpy(dtype=float)
        lo, hi = np.nanmin(x), np.nanmax(x)
        rng = (hi - lo) or 1.0
        c0 = float(atom.value)
        for c in _numeric_thresholds(x, max_thresholds):
            c = float(c)
            if c == c0:
                continue
            c = int(c) if c.is_integer() else c
            a = Atom(atom.attr, atom.op, c)
            opts.append(_Option(a, abs(c - c0) / rng, a.evaluate(df)))
    elif atom.op in ("=", "IN"):
        cur = set(map(str, atom.values))
        col = df[atom.attr].dropna()
        numeric_col = pd.api.types.is_numeric_dtype(col)
        domain = [str(v) for v in col.astype(str).value_counts().index[:max_domain]]
        full = set(map(str, col.astype(str).unique()))
        outside = [v for v in domain if v not in cur]
        seen = set()
        for r_add in range(0, max_set_edits + 1):
            for r_rem in range(0, max_set_edits + 1 - r_add):
                if r_add == r_rem == 0:
                    continue
                for add in combinations(outside, r_add):
                    for rem in combinations(sorted(cur), r_rem):
                        new = (cur - set(rem)) | set(add)
                        if not new or frozenset(new) in seen or new >= full:
                            continue  # empty, already seen, or equivalent to dropping the condition
                        seen.add(frozenset(new))
                        vals = tuple(sorted(new))
                        if numeric_col:
                            vals = tuple(int(float(v)) if float(v).is_integer() else float(v) for v in vals)
                        a = Atom(atom.attr, "=", vals[0]) if len(vals) == 1 else Atom(atom.attr, "IN", vals)
                        dist = len(cur ^ new) / len(cur | new)
                        opts.append(_Option(a, dist, a.evaluate(df)))
    return opts


@dataclass
class RefinementResult:
    original: Predicate
    refined: Predicate | None
    distance: float
    output_jaccard_distance: float
    original_share: dict
    refined_share: dict
    n_evaluated: int
    original_size: int
    refined_size: int

    def to_dict(self) -> dict:
        return {
            "original": self.original.to_sql(),
            "refined": None if self.refined is None else self.refined.to_sql(),
            "predicate_distance": self.distance,
            "output_jaccard_distance": self.output_jaccard_distance,
            "original_share": self.original_share,
            "refined_share": self.refined_share,
            "original_size": self.original_size,
            "refined_size": self.refined_size,
            "n_evaluated": self.n_evaluated,
        }


def refine(query: str | Predicate, constraints: list[Constraint], df: pd.DataFrame, *, max_set_edits: int = 2,
           max_thresholds: int = 60, allow_drop: bool = True, min_size: int = 1, max_changed: int | None = None
           ) -> RefinementResult:
    """Minimal-distance refinement of a conjunctive query satisfying all constraints."""
    q = parse(query)
    atoms = conjuncts(q)
    if not all(isinstance(a, Atom) for a in atoms):
        raise ValueError("refinement supports conjunctions of atomic conditions only")
    options = [_atom_options(a, df, max_set_edits, max_thresholds, allow_drop) for a in atoms]
    groups = [c.group_mask(df) for c in constraints]
    q_mask = q.evaluate(df)
    best = None
    n_eval = 0
    for combo in product(*[range(len(o)) for o in options]):
        changed = sum(1 for c in combo if c != 0)
        if changed == 0 or (max_changed is not None and changed > max_changed):
            continue
        n_eval += 1
        dist = sum(options[i][c].distance for i, c in enumerate(combo))
        if best is not None and dist > best[0]:
            continue
        mask = np.ones(len(df), dtype=bool)
        for i, c in enumerate(combo):
            mask &= options[i][c].mask
        size = int(mask.sum())
        if size < min_size:
            continue
        ok = all(con.satisfied_counts(np.array([(g & mask).sum()]), np.array([size]))[0]
                 for con, g in zip(constraints, groups))
        if not ok:
            continue
        inter = int((mask & q_mask).sum())
        union = int((mask | q_mask).sum())
        jd = 1 - inter / union if union else 0.0
        key = (dist, jd)
        if best is None or key < best[:2]:
            best = (dist, jd, combo, mask)
    shares0 = {c.describe(): c.share(df, q_mask) for c in constraints}
    if best is None:
        return RefinementResult(q, None, float("inf"), float("nan"), shares0, {}, n_eval, int(q_mask.sum()), 0)
    dist, jd, combo, mask = best
    refined = And([options[i][c].pred for i, c in enumerate(combo)])
    parts = conjuncts(refined)
    refined = TrueP() if not parts else (parts[0] if len(parts) == 1 else refined)
    shares1 = {c.describe(): c.share(df, mask) for c in constraints}
    return RefinementResult(q, refined, dist, jd, shares0, shares1, n_eval, int(q_mask.sum()), int(mask.sum()))
