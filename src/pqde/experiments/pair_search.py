"""Case-study pair search: enumerate refinement and CQA candidates, score them, DP-check the best.

Outputs (``results/pair_search/``):
  refinement_<dataset>.csv   every refinement candidate with its scores
  cqa_<dataset>.csv          every CQA candidate with its scores
  shortlist.csv              the top candidates after the DP visibility check
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..cqa import conflict_hypergraph
from ..data import CONFIG_DIR, load_dataset
from ..query import parse
from ..refinement import Constraint
from ..search import cqa_candidates, dp_check, hidden_attributes, refinement_candidates
from .common import out_dir, write_csv


def _score_refinement(df: pd.DataFrame, y_sd: float) -> pd.Series:
    agg = (df["agg_unexplained"].abs() / y_sd).clip(upper=1.0) if "agg_unexplained" in df else 0.0
    return df["hidden_drift"] + 0.5 * df["group_drift"].fillna(0) + agg.fillna(0)


def _score_cqa(df: pd.DataFrame, y_sd: float) -> pd.Series:
    agg = (df["agg_shift"].abs() / y_sd).clip(upper=1.0) if "agg_shift" in df else 0.0
    return df["unevenness"] + df["hidden_drift"] + agg.fillna(0)


def run(cfg: dict | None = None, pairs=None, base=None, quick: bool = False, top: int = 12, trials: int = 8) -> dict:
    with open(CONFIG_DIR / "pair_search.yaml") as f:
        space = yaml.safe_load(f)
    od = out_dir("pair_search", base)
    short = []
    for name, spec in space["refinement"].items():
        ds = load_dataset(name)
        print(f"  refinement candidates on {name} ...")
        cands = refinement_candidates(ds, spec["atoms"], spec["constraints"], min_size=spec["min_size"],
                                      max_size=spec["max_size"], agg=spec.get("agg"), proxies=spec.get("proxies"))
        y_sd = float(pd.to_numeric(ds.raw[spec["agg"]], errors="coerce").std())
        cands["score"] = _score_refinement(cands, y_sd)
        cands = cands.sort_values("score", ascending=False).reset_index(drop=True)
        cands.insert(0, "dataset", name)
        write_csv(cands, od / f"refinement_{name}.csv")
        for _, r in cands.head(3 if quick else top).iterrows():
            c = next(Constraint.from_dict(x) for x in spec["constraints"] if Constraint.from_dict(x).describe() == r.constraint)
            hidden = hidden_attributes(ds, [r.Q1, r.Q2], c, spec.get("proxies"))
            chk = dp_check(ds, parse(r.Q1).evaluate(ds.raw), parse(r.Q2).evaluate(ds.raw), hidden,
                           trials=2 if quick else trials)
            short.append({"kind": "refinement", **r.to_dict(), **chk})
    for name, spec in space["cqa"].items():
        ds = load_dataset(name)
        graph = conflict_hypergraph(ds.raw, [tuple(fd) for fd in ds.meta["fds"]])
        print(f"  CQA candidates on {name} ({graph.n_conflicting} of {ds.N} tuples in conflict) ...")
        cands = cqa_candidates(ds, graph, spec["atoms"], min_size=spec["min_size"], agg=spec.get("agg"))
        if cands.empty:
            continue
        y_sd = float(pd.to_numeric(ds.raw[spec["agg"]], errors="coerce").std())
        cands["score"] = _score_cqa(cands, y_sd)
        cands = cands.sort_values("score", ascending=False).reset_index(drop=True)
        cands.insert(0, "dataset", name)
        write_csv(cands, od / f"cqa_{name}.csv")
        for _, r in cands.head(3 if quick else top).iterrows():
            q = parse(r.Q1).evaluate(ds.raw)
            chk = dp_check(ds, q, q & ~graph.in_conflict, r.hidden_attrs.split(","), trials=2 if quick else trials)
            short.append({"kind": "cqa", **r.to_dict(), **chk})
    shortlist = pd.DataFrame(short)
    shortlist["final_score"] = shortlist["score"] * shortlist["dp_hidden_rate"]
    write_csv(shortlist, od / "shortlist.csv")
    return {"shortlist": shortlist}
