"""Rescore every accuracy experiment against the single-stage brute force, with the default gamma.

Evaluation (decided 2026-11-24): the score is F_lambda with HD_gamma at a FIXED gamma, the pair's
default (Eq. (14) at the default parameters, ~150), whatever gamma the run itself used; the
reference is the brute force BF, the best set of k candidates over the candidates of ALL views,
computed exactly by greedy (Prop. greedy-exact), with the same lambda and the same explanation
attributes as the run.  For every stored selection this writes the score, the ApproxRatio against
BF and attribute@k against BF.  No private run is repeated: the selections are the ones stored in
the raw CSVs.

Outputs (results/rescored/): e2.csv, e2_b1.csv, e3.csv, e6.csv, e6_b1.csv, e7.csv, e7g.csv,
e8_competitors.csv, e8_fixed_gamma.csv, e8_tau.csv, e8_lambda.csv, chance.csv, bf.csv.

Usage: python scripts/rescore_bruteforce.py [pair ...]
       RESCORE_BASE=results_erica python scripts/rescore_bruteforce.py EA1 ...   (raw CSVs read from
       RESCORE_BASE instead of results/, outputs written to RESCORE_BASE/rescored/)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from pqde.baselines import exact_top_views, greedy, objective
from pqde.experiments.common import experiments_config, make_params, stable_key, stats_route
from pqde.experiments.e7_attributes import _restrict, attribute_pool
from pqde.experiments.e8_review import _full_cache
from pqde.pairs import resolve_pair
from pqde.stats import build_cache

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("RESCORE_BASE", "results")
OUT = ROOT / BASE / "rescored"
OUT.mkdir(parents=True, exist_ok=True)
cfg = experiments_config()
d = cfg["defaults"]
K, LAM0 = int(d["k"]), float(d["lam"])


def attr_at_k(sel, ref, k=K) -> float:
    a, b = Counter(x for _, x in sel), Counter(x for _, x in ref)
    return sum((a & b).values()) / k


def read(path: str) -> pd.DataFrame:
    p = ROOT / BASE / path.removeprefix("results/")
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


SRC = {"e2": read("results/e2/raw/trials.csv"), "e2_b1": read("results/e2/raw/baselines.csv"),
       "e3": read("results/e3/raw/budget_split.csv"), "e6": read("results/e6/raw/trials.csv"),
       "e6_b1": read("results/e6/raw/baselines.csv"), "e7": read("results/e7/raw/trials.csv"),
       "e7g": read("results/e7/raw/trials_fixed_gamma.csv"),
       "e8_competitors": read("results/e8/raw/competitors.csv"),
       "e8_fixed_gamma": read("results/e8/raw/fixed_gamma.csv"), "e8_tau": read("results/e8/raw/tau.csv"),
       "e8_lambda": read("results/e8/raw/lambda.csv")}
KEEP = ["pair", "dataset", "sweep", "value", "split", "trial", "order", "attrs", "epsilon", "method", "tau",
        "tau_is_all", "lam", "gamma"]


def sel_of(row) -> list:
    return json.loads(row["selections"] if "selections" in row and isinstance(row.get("selections"), str)
                      else row["selection"] if "selection" in row and isinstance(row.get("selection"), str)
                      else "[]")


pairs = sys.argv[1:] or [p for p in cfg["pairs"] if p not in ("C4", "R6")]
acc: dict[str, list] = {k: [] for k in SRC}
acc["chance"], acc["bf"] = [], []
for pid in pairs:
    c = _full_cache(pid, d)
    ge = float(make_params(d, c.n_views, len(c.explain_attrs)).gamma)  # the pair's default gamma, fixed
    lab = {c.view_label(v): v for v in range(c.n_views)}
    allv = np.arange(c.n_views)
    bf_cache: dict = {}

    def bf(cache, lam: float, key) -> tuple[list, float]:
        if key not in bf_cache:
            s = greedy(cache, allv, K, lam, ge)
            bf_cache[key] = (s, objective(cache, s, lam, ge))
        return bf_cache[key]

    def score(cache, sel_lab, lam, key) -> dict:
        sel = [(lab[v], a) for v, a in sel_lab]
        ref, f_ref = bf(cache, lam, key)
        f = objective(cache, sel, lam, ge)
        return {"F_eval": f, "F_BF": f_ref, "ratio_BF": f / f_ref if f_ref else np.nan,
                "attr_at_k_BF": attr_at_k(sel, ref), "gamma_eval": ge}

    ref0, f0 = bf(c, LAM0, ("default", LAM0))
    acc["bf"].append({"pair": pid, "dataset": c.ds.name, "gamma_eval": ge, "F_BF": f0,
                      "BF": json.dumps([(c.view_label(v), a) for v, a in ref0])})
    # chance level of attribute@k: k candidates drawn uniformly from all candidates
    valid = np.flatnonzero(~np.isnan(c.hd_matrix(0.0, allv)).ravel())
    rng = np.random.default_rng([int(d["seed"]), stable_key(pid), 99])
    na = len(c.explain_attrs)
    draws = [attr_at_k([(int(f // na), c.explain_attrs[int(f % na)]) for f in rng.choice(valid, K, replace=False)], ref0)
             for _ in range(2000)]
    acc["chance"].append({"pair": pid, "dataset": c.ds.name, "chance_attr_at_k": float(np.mean(draws))})
    for name in ("e2", "e2_b1", "e3", "e6", "e6_b1", "e8_competitors", "e8_fixed_gamma", "e8_tau", "e8_lambda"):
        df = SRC[name]
        if df.empty:
            continue
        sub = df[df.pair == pid]
        if name.endswith("_b1"):
            sub = sub[sub.method == "B1"]
        for _, r in sub.iterrows():
            lam = float(r["lam"]) if "lam" in r and pd.notna(r.get("lam")) else LAM0
            out = {k: r[k] for k in KEEP if k in r}
            out.update(score(c, sel_of(r), lam, ("default", lam)))
            acc[name].append(out)
    # E7: explanation attributes vary; reference over the same attributes
    pair = resolve_pair(pid)
    pool = attribute_pool(pair)
    big = None
    for name in ("e7", "e7g"):
        df = SRC[name]
        if df.empty or not (df.pair == pid).any():
            continue
        if big is None:
            big = build_cache(replace(pair.dataset, explain_attrs=pool), pair.q1, pair.q2, **stats_route(d))
            big.ensure_histograms(np.arange(big.n_views))
            blab = {big.view_label(v): v for v in range(big.n_views)}
        for _, r in df[df.pair == pid].iterrows():
            attrs = tuple(json.loads(r["attrs"]))
            cr = _restrict(big, list(attrs))
            key = ("attrs", attrs)
            if key not in bf_cache:
                s = greedy(cr, np.arange(cr.n_views), K, LAM0, ge)
                bf_cache[key] = (s, objective(cr, s, LAM0, ge))
            ref, f_ref = bf_cache[key]
            sel = [(blab[v], a) for v, a in sel_of(r)]
            f = objective(cr, sel, LAM0, ge)
            out = {k: r[k] for k in KEEP if k in r}
            out.update({"F_eval": f, "F_BF": f_ref, "ratio_BF": f / f_ref if f_ref else np.nan,
                        "attr_at_k_BF": attr_at_k(sel, ref), "gamma_eval": ge, "n_attrs": len(attrs)})
            acc[name].append(out)
    for name, rows in acc.items():
        if rows:
            new = pd.DataFrame(rows)
            f = OUT / f"{name}.csv"
            if f.exists():  # keep the rows of the pairs not rescored in this run
                old = pd.read_csv(f)
                new = pd.concat([old[~old["pair"].isin(set(pairs))], new], ignore_index=True)
            new.to_csv(f, index=False)
    print(pid, flush=True)
