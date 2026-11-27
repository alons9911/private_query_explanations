"""Score the pilot pairs (results_pilot/) against OPT, as Table 2 does, plus two noise checks.

Usage: python scripts/erica_pilot_score.py
"""
from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pandas as pd

from pqde.baselines import greedy, objective
from pqde.experiments.common import default_cache, experiments_config, make_params

d = experiments_config()["defaults"]
K, LAM = int(d["k"]), float(d["lam"])
SD = np.sqrt(2) * 2 * K / (1 / 3)  # Laplace(2k/eps_H) per bar at eps = 1: about 42
e2 = pd.read_csv("results_pilot/e2/raw/trials.csv"); e2 = e2[np.isclose(e2.epsilon, 1)]
b1 = pd.read_csv("results_pilot/e2/raw/baselines.csv"); b1 = b1[(b1.method == "B1") & np.isclose(b1.value, 1.0)]
comp = pd.read_csv("results_pilot/e8/raw/competitors.csv"); comp = comp[np.isclose(comp.epsilon, 1)]
vs = pd.read_csv("results_pilot/e3/raw/view_stage.csv"); vs = vs[np.isclose(vs.eps_P, 1 / 3, atol=1e-3)]
rows = []
for pid in e2.pair.unique():
    c = default_cache(pid, d); c.ensure_histograms(np.arange(c.n_views))
    ge = float(make_params(d, c.n_views, len(c.explain_attrs)).gamma)
    lab = {c.view_label(v): v for v in range(c.n_views)}
    opt = greedy(c, np.arange(c.n_views), K, LAM, ge); f_opt = objective(c, opt, LAM, ge)
    def sc(sel_json):
        sel = [(lab[v], a) for v, a in json.loads(sel_json)]
        a, b = Counter(x for _, x in sel), Counter(x for _, x in opt)
        return objective(c, sel, LAM, ge) / f_opt, sum((a & b).values()) / K, float(np.mean([c.cov[v] for v, _ in sel]))
    pe = np.array([sc(s) for s in e2[e2.pair == pid].selections])
    ss = np.array([sc(s) for s in comp[(comp.pair == pid) & (comp.method == "SingleStage")].selections])
    rd = np.array([sc(s) for s in comp[(comp.pair == pid) & (comp.method == "Random")].selections])
    nb = b1[b1.pair == pid]
    nonpriv = sc(nb.selections.iloc[0])[0] if len(nb) and isinstance(nb.selections.iloc[0], str) else np.nan
    # noise checks on the explanations PEEQ selects at eps = 1
    tops, clear = [], []
    for s in e2[e2.pair == pid].selections:
        for v, a in json.loads(s):
            n, h1, h2 = c.histograms(lab[v], a)
            tops.append(max(h1.max(), h2.max())); clear.append(np.abs(h1 - h2).max() >= 2 * np.sqrt(2) * SD)
    rows.append({"pair": pid, "dataset": c.ds.name, "N": c.N, "|Q1|": int(c.q1.sum()), "|Q2|": int(c.q2.sum()),
                 "PEEQ": pe[:, 0].mean(), "NonPrivate": nonpriv, "Single": ss[:, 0].mean(), "Random": rd[:, 0].mean(),
                 "attr@k": pe[:, 1].mean(), "cov": pe[:, 2].mean(), "view_overlap": vs[vs.pair == pid].overlap.mean(),
                 "median_top_bar": float(np.median(tops)), "share_clear": float(np.mean(clear)), "OPT_F": f_opt})
r = pd.DataFrame(rows)
pd.set_option("display.width", 220)
print(r.round(2).to_string(index=False))
print("\nby dataset:"); print(r.groupby("dataset")[["PEEQ", "NonPrivate", "Single", "Random", "attr@k", "view_overlap", "median_top_bar", "share_clear"]].mean().round(2))
print(f"\nnoise s.d. per bar: {SD:.0f}; a 'clear' difference exceeds 2 s.d. of the difference of two bars ({2*np.sqrt(2)*SD:.0f})")
r.to_csv("results/erica_pilot/scores.csv", index=False)
