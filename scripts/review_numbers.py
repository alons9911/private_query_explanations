"""Numbers for the third review of Section 5, computed from stored selections (no private run).

Writes results/rescored/review_numbers.csv (one row per pair) and results/rescored/coverage_tau.csv:
coverage (mean Cov of the explained views) of BF, of PrivExpl at the defaults and of PrivExpl at each
tau of E8; the best HD_gamma (default gamma) among the candidates of the exact top-tau views; output sizes;
the median support of a bin among the explained candidates of PrivExpl at the defaults.

Usage: python scripts/review_numbers.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pqde.baselines import exact_top_views
from pqde.experiments.common import default_cache, experiments_config, make_params

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rescored"
cfg = experiments_config()
d = cfg["defaults"]
bf = pd.read_csv(OUT / "bf.csv").set_index("pair")
e2 = pd.read_csv(ROOT / "results/e2/raw/trials.csv")
e2 = e2[np.isclose(e2.epsilon, 1.0)]
tau = pd.read_csv(ROOT / "results/e8/raw/tau.csv")
rows, trows = [], []
for pid in bf.index:
    c = default_cache(pid, d)
    p = make_params(d, c.n_views, len(c.explain_attrs))
    lab = {c.view_label(v): v for v in range(c.n_views)}
    cov = c.cov

    def mcov(sel_json: str) -> float:
        return float(np.mean([cov[lab[v]] for v, _ in json.loads(sel_json)]))

    top = exact_top_views(c, p.tau)
    best = float(np.nanmax(c.hd_matrix(float(p.gamma), top)))
    supp = []
    for s in e2[e2.pair == pid].selections:
        for v, a in json.loads(s):
            n, _, _ = c.histograms(lab[v], a)
            supp.extend(n[n > 0].tolist())
    q1, q2 = int(c.q1.sum()), int(c.q2.sum())
    rows.append({"pair": pid, "dataset": c.ds.name, "N": c.N, "q1": q1, "q2": q2,
                 "sym_diff": int((c.q1 ^ c.q2).sum()), "gamma": float(p.gamma),
                 "cov_BF": mcov(bf.loc[pid, "BF"]),
                 "cov_PrivExpl": float(np.mean([mcov(s) for s in e2[e2.pair == pid].selections])),
                 "best_hd_top_tau": best, "median_bin_support": float(np.median(supp))})
    for t, g in tau[tau.pair == pid].groupby("tau"):
        trows.append({"pair": pid, "dataset": c.ds.name, "tau": int(t), "tau_is_all": bool(g.tau_is_all.iloc[0]),
                      "coverage": float(np.mean([mcov(s) for s in g.selections]))})
    print(pid, flush=True)
pd.DataFrame(rows).to_csv(OUT / "review_numbers.csv", index=False)
pd.DataFrame(trows).to_csv(OUT / "coverage_tau.csv", index=False)
