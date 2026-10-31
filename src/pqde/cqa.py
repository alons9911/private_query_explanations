"""Consistent query answering for selection queries (Definitions 2.6-2.7).

Repairs are maximal consistent subsets of ``D``.  For denial constraints the
conflict hypergraph (Chomicki, Marcinkowski & Staworko, CIKM 2004) has one
hyperedge per minimal set of tuples that jointly violate a constraint; for
functional dependencies ``X -> Y`` the hyperedges are the pairs of tuples
that agree on ``X`` and disagree on ``Y``.

A tuple belongs to every repair iff it lies on no hyperedge: if it lies on an
edge ``{t, t'}``, the consistent set ``{t'}`` extends to a repair that omits
``t``.  For a selection query the consistent answer is therefore

    Q_Sigma(D) = Q(D) minus the tuples of the conflict hypergraph.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .query import Predicate, parse


@dataclass
class ConflictHypergraph:
    n_tuples: int
    in_conflict: np.ndarray  # bool per tuple: lies on at least one hyperedge
    n_edges: int
    per_fd: dict  # "X->Y" -> number of tuples involved / edges

    @property
    def n_conflicting(self) -> int:
        return int(self.in_conflict.sum())


def _key(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    if len(cols) == 1:
        return df[cols[0]].astype("string").fillna("<NULL>")
    return df[cols].astype("string").fillna("<NULL>").agg("\x1f".join, axis=1)


def conflict_hypergraph(df: pd.DataFrame, fds: list[tuple[list[str] | str, list[str] | str]]) -> ConflictHypergraph:
    """Conflict hypergraph of a set of functional dependencies ``X -> Y``."""
    in_conflict = np.zeros(len(df), dtype=bool)
    n_edges = 0
    per_fd = {}
    for lhs, rhs in fds:
        lhs = [lhs] if isinstance(lhs, str) else list(lhs)
        rhs = [rhs] if isinstance(rhs, str) else list(rhs)
        x = _key(df, lhs).to_numpy()
        y = _key(df, rhs).to_numpy()
        frame = pd.DataFrame({"x": x, "y": y})
        # edges: pairs agreeing on X and disagreeing on Y = C(n_x, 2) - sum_y C(n_xy, 2)
        nx = frame.groupby("x").size()
        nxy = frame.groupby(["x", "y"]).size()
        e = int((nx * (nx - 1) // 2).sum() - (nxy * (nxy - 1) // 2).sum())
        n_distinct = frame.groupby("x")["y"].nunique()
        bad = set(n_distinct.index[n_distinct > 1])
        mask = frame["x"].isin(bad).to_numpy()
        in_conflict |= mask
        n_edges += e
        per_fd[f"{'+'.join(lhs)}->{'+'.join(rhs)}"] = {"tuples": int(mask.sum()), "edges": e}
    return ConflictHypergraph(len(df), in_conflict, n_edges, per_fd)


def consistent_answer(query: str | Predicate, df: pd.DataFrame, graph: ConflictHypergraph) -> tuple[np.ndarray, np.ndarray]:
    """``(Q(D), Q_Sigma(D))`` as boolean masks."""
    q = parse(query).evaluate(df)
    return q, q & ~graph.in_conflict


def choose_cqa_selection(df: pd.DataFrame, graph: ConflictHypergraph, attr: str, other_attrs: list[str], *,
                         min_drop: float = 0.10, max_drop: float = 0.90, min_size: int = 20) -> dict | None:
    """The single-predicate selection on ``attr`` used for H2/H3 (Section 5.1, query pairs).

    Among selections ``attr = v`` whose consistent answer drops between
    ``min_drop`` and ``max_drop`` of ``Q(D)``, return the one whose dropped tuples
    are spread most unevenly over the other attributes, measured as the largest
    total variation distance between the distribution of the dropped tuples and
    that of ``Q(D)`` over any other attribute.
    """
    best = None
    for v, n in df[attr].astype("string").value_counts().items():
        if n < min_size:
            continue
        q = (df[attr].astype("string") == v).fillna(False).to_numpy()
        drop = q & graph.in_conflict
        frac = drop.sum() / q.sum()
        if not (min_drop <= frac <= max_drop):
            continue
        unevenness, where = 0.0, None
        for a in other_attrs:
            col = df[a].astype("string").fillna("<NULL>")
            p_q = col[q].value_counts(normalize=True)
            p_d = col[drop].value_counts(normalize=True)
            idx = p_q.index.union(p_d.index)
            t = 0.5 * np.abs(p_q.reindex(idx, fill_value=0) - p_d.reindex(idx, fill_value=0)).sum()
            if t > unevenness:
                unevenness, where = float(t), a
        cand = {"attr": attr, "value": str(v), "size": int(q.sum()), "dropped": int(drop.sum()),
                "drop_fraction": float(frac), "unevenness_tvd": unevenness, "most_uneven_attr": where}
        if best is None or cand["unevenness_tvd"] > best["unevenness_tvd"]:
            best = cand
    return best
