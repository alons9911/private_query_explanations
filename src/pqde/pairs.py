"""Query pairs (Table 2): resolve a pair specification into the two populations."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .cqa import choose_cqa_selection, conflict_hypergraph
from .data import CONFIG_DIR, EncodedDataset, load_dataset
from .query import Atom, parse
from .refinement import Constraint, refine
from .stats import StatsCache, build_cache


@dataclass
class QueryPair:
    pair_id: str
    dataset: EncodedDataset
    kind: str
    q1_sql: str
    q2_sql: str
    q1: np.ndarray
    q2: np.ndarray
    constraints: list[Constraint] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def summary(self) -> dict:
        df = self.dataset.raw
        out = {
            "pair": self.pair_id,
            "dataset": self.dataset.name,
            "synthetic_data": bool(self.dataset.meta.get("synthetic", False)),
            "N": self.dataset.N,
            "kind": self.kind,
            "Q1": self.q1_sql,
            "Q2": self.q2_sql,
            "|Q1|": int(self.q1.sum()),
            "|Q2|": int(self.q2.sum()),
            "|Q1 & Q2|": int((self.q1 & self.q2).sum()),
        }
        for c in self.constraints:
            out[f"constraint: {c.describe()}"] = {
                "share_Q1": round(c.share(df, self.q1), 4),
                "share_Q2": round(c.share(df, self.q2), 4),
            }
        out.update(self.info)
        return out

    def cache(self, **kw) -> StatsCache:
        return build_cache(self.dataset, self.q1, self.q2, **kw)


def pairs_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "pairs.yaml") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=32)
def _resolve(pair_id: str, config_path: str | None) -> QueryPair:
    spec = pairs_config(Path(config_path) if config_path else None)[pair_id]
    ds = load_dataset(spec["dataset"])
    df = ds.raw
    kind = spec["kind"]
    constraints = [Constraint.from_dict(c) for c in spec.get("constraints", [])]
    info: dict = {}
    if kind == "cqa":
        graph = conflict_hypergraph(df, [tuple(fd) for fd in ds.meta["fds"]])
        q1spec = spec["q1"]
        if isinstance(q1spec, dict) and "auto" in q1spec:
            attr = q1spec["auto"]
            others = [a for a in ds.explain_attrs if a != attr]
            sel = choose_cqa_selection(df, graph, attr, others)
            if sel is None:
                raise RuntimeError(f"{pair_id}: no selection on {attr} meets the 10%-90% drop rule")
            q1_sql = Atom(attr, "=", sel["value"]).to_sql()
            info["selection_rule"] = sel
        else:
            q1_sql = q1spec
        q1 = parse(q1_sql).evaluate(df)
        q2 = q1 & ~graph.in_conflict
        q2_sql = f"Q_Sigma({q1_sql})"
        info["conflicts"] = {"tuples_in_conflict": graph.n_conflicting, "edges": graph.n_edges, **graph.per_fd}
    else:
        q1_sql = spec["q1"]
        q1 = parse(q1_sql).evaluate(df)
        if spec.get("q2") == "auto":
            if kind != "refinement":
                raise ValueError("q2: auto is only supported for refinement pairs")
            res = refine(q1_sql, constraints, df, **spec.get("refine_options", {}))
            if res.refined is None:
                raise RuntimeError(f"{pair_id}: refinement search found no query satisfying the constraints")
            q2_sql = res.refined.to_sql()
            info["refinement_search"] = res.to_dict()
        else:
            q2_sql = spec["q2"]
        q2 = parse(q2_sql).evaluate(df)
    if "paper" in spec:
        info["paper_reported"] = spec["paper"]
    for key in ("role", "aggregate"):
        if key in spec:
            info[key] = spec[key]
    if "aggregate" in spec:
        y = pd.to_numeric(df[spec["aggregate"]], errors="coerce").to_numpy(dtype=float)
        info["AVG_Q1"] = float(np.nanmean(y[q1])) if q1.any() else float("nan")
        info["AVG_Q2"] = float(np.nanmean(y[q2])) if q2.any() else float("nan")
    return QueryPair(pair_id, ds, kind, q1_sql, q2_sql, q1, q2, constraints, info)


def resolve_pair(pair_id: str, config_path: Path | str | None = None) -> QueryPair:
    """Resolve pair ``pair_id`` of ``configs/pairs.yaml`` (memoised)."""
    return _resolve(pair_id, str(config_path) if config_path else None)


@lru_cache(maxsize=32)
def pair_cache(pair_id: str) -> StatsCache:
    """Statistics cache of a pair with the default views (memoised)."""
    return resolve_pair(pair_id).cache()


ALL_PAIRS = ["A1", "A2", "A3", "T1", "T2", "T3", "S1", "S2", "S3", "H1", "H2", "H3"]
CASE_STUDY_PAIRS = ["R1", "R2", "R3", "R4", "R5", "R6", "C1", "C2", "C3", "C4"]
