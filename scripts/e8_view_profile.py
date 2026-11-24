"""Profile of the views behind each selection of E8 (results/e8/view_profile.csv).

For every pair and every selection set -- B3 (filtered optimum), OptAll (optimum over all
views), the private algorithm (E2 runs at eps = 1) and SingleStage (E8 runs at eps = 1) --
the mean over its explanations of: view size m = |p(D)|, coverage (|Q1(p(D))| + |Q2(p(D))|) / N,
rank of the view by Use (1 = best), whether the candidate is one-sided (one output has no
tuple in the view), and the set's score F^0 (unsmoothed) and F^gamma (smoothed with the
pair's default gamma), so that the two can be compared.

Usage: python scripts/e8_view_profile.py [pair ...]   (default: every pair of E8)
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pqde.baselines import objective
from pqde.experiments.common import experiments_config, make_params
from pqde.experiments.e8_review import _full_cache

cfg = experiments_config()
d = cfg["defaults"]
opt = pd.read_csv("results/e8/raw/optimum.csv").set_index("pair")
comp = pd.read_csv("results/e8/raw/competitors.csv")
e2 = pd.read_csv("results/e2/raw/trials.csv")
pairs = sys.argv[1:] or list(opt.index)
rows = []
for pid in pairs:
    c = _full_cache(pid, d)
    gamma = make_params(d, c.n_views, len(c.explain_attrs)).gamma
    lab = {c.view_label(v): v for v in range(c.n_views)}
    rank = np.empty(c.n_views, int)
    rank[np.argsort(-c.use, kind="stable")] = np.arange(1, c.n_views + 1)

    def profile(sel_json: str) -> dict:
        sel = [(lab[v], a) for v, a in json.loads(sel_json)]
        m, cov, rk, one = [], [], [], []
        for v, a in sel:
            n, h1, h2 = c.histograms(v, a)
            m.append(n.sum())
            cov.append((h1.sum() + h2.sum()) / c.N)
            rk.append(rank[v])
            one.append(float(min(h1.sum(), h2.sum()) == 0))
        return {"m": np.mean(m), "coverage": np.mean(cov), "use_rank": np.median(rk), "one_sided": np.mean(one),
                "F0": objective(c, sel, float(d["lam"]), 0.0), "Fgamma": objective(c, sel, float(d["lam"]), gamma)}

    sets = {"B3": [opt.loc[pid, "B3"]], "OptAll": [opt.loc[pid, "OptAll"]],
            "PrivExpl": list(e2[(e2.pair == pid) & np.isclose(e2.epsilon, 1.0)].selections),
            "SingleStage": list(comp[(comp.pair == pid) & (comp.method == "SingleStage")
                                     & np.isclose(comp.epsilon, 1.0)].selections)}
    for name, sels in sets.items():
        prof = pd.DataFrame([profile(s) for s in sels]).mean()
        rows.append({"pair": pid, "dataset": opt.loc[pid, "dataset"], "set": name, "runs": len(sels), "gamma": gamma,
                     **prof.to_dict()})
    print(pid, flush=True)
    pd.DataFrame(rows).to_csv("results/e8/view_profile.csv", index=False)
