"""Refinement pairs for new datasets: our ERICA-style search, then two feasibility checks.

For each dataset named on the command line (with a `refinement` entry in configs/pair_search.yaml)
this runs the candidate search and scoring of `pqde.experiments.pair_search` (only for these
datasets) and, for the best candidates:

* the DP visibility check of the earlier pair search (`dp_check`);
* the accuracy of the view stage alone at the default eps_P = eps/3: the overlap of the tau views
  it retains with the exact top-tau by Use (Figure "view stage"), over 20 runs.

Outputs: results/pair_search/refinement_<dataset>.csv (all candidates) and
results/pair_search/shortlist_<dataset>.csv (the checked ones).  Nothing is added to
configs/pairs.yaml: the pairs are chosen from the shortlist by hand, after approval.

Usage: python scripts/search_refinement_pairs.py compas law meps [--top 12]
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import yaml

from pqde.baselines import exact_top_views
from pqde.data import CONFIG_DIR, load_dataset
from pqde.experiments.common import experiments_config, make_params, out_dir, write_csv
from pqde.experiments.pair_search import _score_refinement
from pqde.algorithm import select_views
from pqde.query import parse
from pqde.refinement import Constraint
from pqde.search import dp_check, hidden_attributes, refinement_candidates
from pqde.stats import build_cache

ap = argparse.ArgumentParser()
ap.add_argument("datasets", nargs="+")
ap.add_argument("--top", type=int, default=12)
ap.add_argument("--view-trials", type=int, default=20)
args = ap.parse_args()

space = yaml.safe_load(open(CONFIG_DIR / "pair_search.yaml"))["refinement"]
d = experiments_config()["defaults"]
od = out_dir("pair_search")
for name in args.datasets:
    spec = space[name]
    ds = load_dataset(name)
    print(f"{name}: N = {ds.N}, searching ...", flush=True)
    cands = refinement_candidates(ds, spec["atoms"], spec["constraints"], min_size=spec["min_size"],
                                  max_size=spec["max_size"], agg=spec.get("agg"), proxies=spec.get("proxies"))
    if cands.empty:
        print(f"{name}: no candidate")
        continue
    y_sd = float(pd.to_numeric(ds.raw[spec["agg"]], errors="coerce").std())
    cands["score"] = _score_refinement(cands, y_sd)
    cands = cands.sort_values("score", ascending=False).reset_index(drop=True)
    cands.insert(0, "dataset", name)
    write_csv(cands, od / f"refinement_{name}.csv")
    short = []
    for _, r in cands.head(args.top).iterrows():
        c = next(Constraint.from_dict(x) for x in spec["constraints"] if Constraint.from_dict(x).describe() == r.constraint)
        q1, q2 = parse(r.Q1).evaluate(ds.raw), parse(r.Q2).evaluate(ds.raw)
        chk = dp_check(ds, q1, q2, hidden_attributes(ds, [r.Q1, r.Q2], c, spec.get("proxies")), trials=8)
        cache = build_cache(ds, q1, q2)
        p = make_params(d, cache.n_views, len(cache.explain_attrs))
        exact = set(int(v) for v in exact_top_views(cache, p.tau))
        eps_P = p.budgets()[0]
        ov = [len(set(int(v) for v in select_views(cache, p.tau, eps_P, np.random.default_rng([7, t]))[0]) & exact) / p.tau
              for t in range(args.view_trials)]
        short.append({**r.to_dict(), **chk, "n_Q1": int(q1.sum()), "n_Q2": int(q2.sum()),
                      "n_both": int((q1 & q2).sum()), "view_overlap": float(np.mean(ov)), "tau": p.tau})
        print(f"  {r.Q1}  ->  {r.Q2}   [{r.constraint}]  |Q1|={int(q1.sum())} |Q2|={int(q2.sum())} "
              f"view overlap {np.mean(ov):.2f}", flush=True)
    write_csv(pd.DataFrame(short), od / f"shortlist_{name}.csv")
