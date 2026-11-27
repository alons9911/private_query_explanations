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
                  max_domain: int = 60, allow_replace: bool = True) -> list[_Option]:
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
                        if not allow_replace and not (new & cur):
                            continue  # swapping the whole value set is not a refinement of it
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


def _satisfies(mask: np.ndarray, constraints: list[Constraint], groups: list[np.ndarray], min_size: int) -> bool:
    n = int(mask.sum())
    if n < max(min_size, 1):
        return False
    return all(bool(c.satisfied_counts(np.array([(g & mask).sum()]), np.array([n]))[0]) for c, g in zip(constraints, groups))


def _closer_options(a0: Atom, a1: Predicate | None, df: pd.DataFrame) -> list[tuple[bool, Predicate | None, np.ndarray]]:
    """Every condition between the original atom ``a0`` and its refinement ``a1`` (None = dropped), each
    with a flag "strictly closer to a0 than a1" (Erica's domination, per condition), over all data values."""
    n = len(df)
    if a0.op in ("<", "<=", ">", ">="):
        x = pd.to_numeric(df[a0.attr], errors="coerce").to_numpy(dtype=float)
        c0 = float(a0.value)
        if a1 is None:
            c1 = float(np.nanmin(x)) if a0.op in (">", ">=") else float(np.nanmax(x))
        else:
            c1 = float(a1.value)
        lo, hi = sorted((c0, c1))
        vals = sorted(set(np.unique(x[(x >= lo) & (x <= hi) & ~np.isnan(x)]).tolist()) | {c0, c1},
                      key=lambda v: abs(v - c0))
        out = []
        for v in vals:
            if abs(v - c0) > abs(c1 - c0) + 1e-12:
                continue
            strict = abs(v - c0) < abs(c1 - c0) - 1e-12
            if a1 is None and not strict:
                out.append((False, None, np.ones(n, dtype=bool)))
                continue
            v = int(v) if float(v).is_integer() else v
            a = Atom(a0.attr, a0.op, v)
            out.append((strict, a, a.evaluate(df)))
        return out
    cur = set(map(str, a0.values))
    new = set(map(str, a1.values)) if a1 is not None else set(df[a0.attr].dropna().astype(str).unique())
    add, rem = sorted(new - cur), sorted(cur - new)
    col = df[a0.attr].astype(str)
    out = []
    for ra in range(len(add) + 1):
        for rr in range(len(rem) + 1):
            for A_ in combinations(add, ra):
                for R_ in combinations(rem, rr):
                    vals = (cur - set(R_)) | set(A_)
                    if not vals:
                        continue
                    full = (ra, rr) == (len(add), len(rem))
                    pred = None if (full and a1 is None) else (
                        Atom(a0.attr, "=", sorted(vals)[0]) if len(vals) == 1 else Atom(a0.attr, "IN", tuple(sorted(vals))))
                    mask = np.ones(len(df), dtype=bool) if pred is None else col.isin(vals).to_numpy()
                    out.append((not full, pred, mask))
    return out


def dominating_refinements(original: str | Predicate, refined: str | Predicate, constraints: list[Constraint],
                           df: pd.DataFrame, *, min_size: int = 1, limit: int = 200_000) -> int:
    """Number of refinements that dominate ``refined`` in Erica's sense (at least as close to ``original``
    on every condition, strictly closer on one) and still satisfy the constraints, over all data values.
    0 means that ``refined`` is a minimal refinement (Li et al., PVLDB 17(2), 2023, Section 2)."""
    q0 = parse(original)
    a1s = {} if str(refined).strip() == "TRUE" else {a.attr: a for a in conjuncts(parse(refined))}
    opts = [_closer_options(a, a1s.get(a.attr), df) for a in conjuncts(q0)]
    groups = [c.group_mask(df) for c in constraints]
    count = 0
    for i, combo in enumerate(product(*opts)):
        if i >= limit:
            raise RuntimeError("too many dominating candidates to enumerate")
        if not any(s for s, _, _ in combo):
            continue
        mask = np.logical_and.reduce([m for _, _, m in combo])
        count += _satisfies(mask, constraints, groups, min_size)
    return count


def tighten(original: str | Predicate, refined: str | Predicate, constraints: list[Constraint], df: pd.DataFrame,
            *, min_size: int = 1) -> Predicate:
    """Move each changed condition of ``refined`` back towards ``original`` as far as the constraints allow,
    one condition at a time over all data values, until no condition can move.  The grid search of
    :func:`refine` tries at most ``max_thresholds`` thresholds per attribute; this step makes the result
    minimal over every value of the data (checked by :func:`dominating_refinements`)."""
    q0 = parse(original)
    atoms0 = conjuncts(q0)
    cur = {} if str(refined).strip() == "TRUE" else {a.attr: a for a in conjuncts(parse(refined))}
    cur = [cur.get(a.attr) for a in atoms0]  # None = dropped
    groups = [c.group_mask(df) for c in constraints]
    masks = [np.ones(len(df), dtype=bool) if c is None else c.evaluate(df) for c in cur]
    moved = True
    while moved:
        moved = False
        for i, a0 in enumerate(atoms0):
            rest = np.logical_and.reduce([m for j, m in enumerate(masks) if j != i]) if len(masks) > 1 \
                else np.ones(len(df), dtype=bool)
            for strict, pred, m in _closer_options(a0, cur[i], df):  # closest to the original first
                if not strict:
                    break
                if _satisfies(rest & m, constraints, groups, min_size):
                    cur[i], masks[i], moved = pred, m, True
                    break
    parts = [c for c in cur if c is not None]
    return TrueP() if not parts else (parts[0] if len(parts) == 1 else And(parts))


def refine(query: str | Predicate, constraints: list[Constraint], df: pd.DataFrame, *, max_set_edits: int = 2,
           max_thresholds: int = 60, allow_drop: bool = True, min_size: int = 1, max_changed: int | None = None,
           allow_replace: bool = True, exact: bool = True) -> RefinementResult:
    """Minimal-distance refinement of a conjunctive query satisfying all constraints.

    Candidates are scored in blocks: for the last two conditions every
    (option, option) combination is evaluated at once with matrix products of
    the option masks, so a two-condition query costs two small GEMMs.
    """
    q = parse(query)
    atoms = conjuncts(q)
    if not all(isinstance(a, Atom) for a in atoms):
        raise ValueError("refinement supports conjunctions of atomic conditions only")
    options = [_atom_options(a, df, max_set_edits, max_thresholds, allow_drop, allow_replace=allow_replace)
               for a in atoms]
    groups = [c.group_mask(df) for c in constraints]
    q_mask = q.evaluate(df)
    n_q = int(q_mask.sum())
    n = len(df)
    if len(options) == 1:  # pad with a no-op condition so that the block evaluation always has two axes
        options.append([_Option(TrueP(), 0.0, np.ones(n, dtype=bool))])
    head, (oa, ob) = options[:-2], options[-2:]
    A = np.stack([o.mask for o in oa]).astype(np.float32)
    B = np.stack([o.mask for o in ob]).astype(np.float32)
    da = np.array([o.distance for o in oa])
    db = np.array([o.distance for o in ob])
    best = None
    n_eval = 0
    for hcombo in product(*[range(len(o)) for o in head]):
        hmask = np.ones(n, dtype=np.float32)
        hdist = 0.0
        for i, c in enumerate(hcombo):
            hmask *= head[i][c].mask
            hdist += head[i][c].distance
        Bh = B * hmask[None, :]
        size = A @ Bh.T
        inter = A @ (Bh * q_mask[None, :]).T
        ok = size >= max(min_size, 1)
        for con, g in zip(constraints, groups):
            gc = A @ (Bh * g[None, :]).T
            ok &= con.satisfied_counts(gc, size)
        changed = (np.arange(len(oa)) != 0)[:, None].astype(int) + (np.arange(len(ob)) != 0)[None, :].astype(int)
        changed = changed + sum(1 for c in hcombo if c != 0)
        valid = changed > 0
        if max_changed is not None:
            valid &= changed <= max_changed
        n_eval += int(valid.sum())
        ok &= valid
        if not ok.any():
            continue
        dist = hdist + da[:, None] + db[None, :]
        union = size + n_q - inter
        jd = np.where(union > 0, 1 - inter / np.maximum(union, 1), 0.0)
        cand = np.flatnonzero(ok.ravel())
        order = np.lexsort((jd.ravel()[cand], dist.ravel()[cand]))  # by distance, then output Jaccard
        k = cand[order[0]]
        key = (float(dist.ravel()[k]), float(jd.ravel()[k]))
        if best is None or key < best[:2]:
            i, j = divmod(int(k), len(ob))
            best = (key[0], key[1], (*hcombo, i, j))
    shares0 = {c.describe(): c.share(df, q_mask) for c in constraints}
    if best is None:
        return RefinementResult(q, None, float("inf"), float("nan"), shares0, {}, n_eval, n_q, 0)
    dist, jd, combo = best
    mask = np.ones(n, dtype=bool)
    for i, c in enumerate(combo):
        mask &= options[i][c].mask
    refined = And([options[i][c].pred for i, c in enumerate(combo)])
    parts = conjuncts(refined)
    refined = TrueP() if not parts else (parts[0] if len(parts) == 1 else refined)
    if exact:  # the grid may miss a closer threshold: tighten over every data value
        refined = tighten(q, refined, constraints, df, min_size=min_size)
        mask = refined.evaluate(df)
        a1s = {a.attr: a for a in conjuncts(refined)} if not isinstance(refined, TrueP) else {}
        dist = 0.0
        for a0 in atoms:
            a1 = a1s.get(a0.attr)
            if a1 is None:
                dist += 1.0
            elif a0.op in ("<", "<=", ">", ">="):
                x = pd.to_numeric(df[a0.attr], errors="coerce").to_numpy(dtype=float)
                dist += abs(float(a1.value) - float(a0.value)) / ((np.nanmax(x) - np.nanmin(x)) or 1.0)
            else:
                c0, c1 = set(map(str, a0.values)), set(map(str, a1.values))
                dist += len(c0 ^ c1) / len(c0 | c1)
        inter = int((mask & q_mask).sum())
        union = int(mask.sum()) + n_q - inter
        jd = 1 - inter / union if union else 0.0
    shares1 = {c.describe(): c.share(df, mask) for c in constraints}
    return RefinementResult(q, refined, dist, jd, shares0, shares1, n_eval, n_q, int(mask.sum()))
