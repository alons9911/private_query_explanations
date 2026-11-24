"""ApproxRatio against the single-stage brute force (the optimum over the candidates of ALL views).

For every pair and two evaluation scores -- the unsmoothed F^0 (gamma_eval = 0) and the smoothed
F^gamma (gamma_eval = the pair's default gamma, Eq. (14)) -- the brute-force optimum is computed by
greedy over all candidates, which is exact for any candidate scores (Prop. greedy-exact).  The
private algorithm (E2 runs at eps = 1), SingleStage (E8 runs at eps = 1) and the non-private
variants B1 and B3 are scored against it.  Writes results/e8/bruteforce_reference.csv.

Usage: python scripts/bruteforce_reference.py [pair ...]
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pqde.baselines import b1, b3, greedy, objective
from pqde.experiments.common import experiments_config, make_params
from pqde.experiments.e8_review import _full_cache

cfg = experiments_config()
d = cfg["defaults"]
lam = float(d["lam"])
e2 = pd.read_csv("results/e2/raw/trials.csv")
comp = pd.read_csv("results/e8/raw/competitors.csv")
pairs = sys.argv[1:] or [p for p in cfg["pairs"] if p not in ("C4", "R6")]
rows = []
for pid in pairs:
    c = _full_cache(pid, d)
    params = make_params(d, c.n_views, len(c.explain_attrs))
    lab = {c.view_label(v): v for v in range(c.n_views)}
    sets = {"PrivExpl": [json.loads(s) for s in e2[(e2.pair == pid) & np.isclose(e2.epsilon, 1.0)].selections],
            "SingleStage": [json.loads(s) for s in comp[(comp.pair == pid) & (comp.method == "SingleStage")
                                                        & np.isclose(comp.epsilon, 1.0)].selections]}
    fixed = {"B1": b1(c, params).selections, "B3": b3(c, params, 0.0)}
    for ge_name, ge in (("gamma0", 0.0), ("gammaDefault", float(params.gamma))):
        bf = greedy(c, np.arange(c.n_views), params.k, lam, ge)
        f_bf = objective(c, bf, lam, ge)
        row = {"pair": pid, "dataset": c.ds.name, "eval": ge_name, "gamma_eval": ge, "F_bruteforce": f_bf}
        for name, sels in sets.items():
            vals = [objective(c, [(lab[v], a) for v, a in s], lam, ge) for s in sels]
            row[f"ratio_{name}"] = float(np.mean(vals)) / f_bf if f_bf else np.nan
        for name, sel in fixed.items():
            row[f"ratio_{name}"] = objective(c, sel, lam, ge) / f_bf if f_bf else np.nan
        rows.append(row)
    print(pid, flush=True)
    pd.DataFrame(rows).to_csv("results/e8/bruteforce_reference.csv", index=False)
