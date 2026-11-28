"""How many output tuples the explained views hold, per method, at the defaults (reviewer question B.2).

For the 36 quality pairs: PEEQ (E2 at eps = 1, 40 trials), SingleStage and Random (E8 at eps = 1, 40 trials)
and OPT (the brute force at the default gamma).  For every explanation, the output tuples of its view,
|Q1(p(D))| + |Q2(p(D))|, as a count and as a share of |Q1(D)| + |Q2(D)|.  No new runs: the selections are
read from the stored results and the view sizes recomputed from the data.

Usage: python scripts/view_sizes.py OUT_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pqde.pairs import resolve_pair  # noqa: E402
from pqde.stats import build_cache  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
EXCLUDE = {"C4", "R6"}

tr = pd.read_csv("results/e2/raw/trials.csv", low_memory=False)
tr = tr[(tr.sweep == "epsilon") & (tr.epsilon == 1.0)][["pair", "dataset", "trial", "selections"]].assign(method="PEEQ")
co = pd.read_csv("results/e8/raw/competitors.csv", low_memory=False)
co = co[co.epsilon == 1.0][["pair", "dataset", "trial", "method", "selections"]]
bf = pd.read_csv("results/rescored/bf.csv")[["pair", "dataset", "BF"]].rename(columns={"BF": "selections"})
bf = bf.assign(method="OPT", trial=0)
rel = pd.concat([tr, co, bf], ignore_index=True)
rel = rel[~rel.pair.isin(EXCLUDE)]

rows = []
for pid, g in rel.groupby("pair"):
    p = resolve_pair(pid)
    c = build_cache(p.dataset, p.q1, p.q2, None, mode="grouped", rep="general", hist="lazy")
    lab = {c.view_label(i): i for i in range(c.n_views)}
    tot = int(p.q1.sum()) + int(p.q2.sum())
    for r in g.itertuples():
        for view, attr in json.loads(r.selections):
            i = lab[view]
            n = int(c.s1[i] + c.s2[i])
            rows.append({"pair": pid, "dataset": r.dataset, "method": r.method, "trial": r.trial, "view": view,
                         "attr": attr, "out_tuples": n, "out_share": n / tot, "cov": n / c.N})
    print(pid, flush=True)
d = pd.DataFrame(rows)
d.to_csv(out / "explained_views.csv", index=False)

# per method: the explanations of every pair weighted equally (mean over a pair's explanations first)
summ = []
for m, g in d.groupby("method"):
    per = g.groupby("pair").agg(med=("out_tuples", "median"), small1=("out_share", lambda s: float((s < 0.01).mean())),
                                small50=("out_tuples", lambda s: float((s < 50).mean())), cov=("cov", "mean"))
    summ.append({"method": m, "pairs": len(per), "median_out_tuples(median over pairs)": float(per.med.median()),
                 "share<1% of outputs": float(per.small1.mean()), "share<50 tuples": float(per.small50.mean()),
                 "mean cov": float(per["cov"].mean())})
s = pd.DataFrame(summ)
s.to_csv(out / "summary.csv", index=False)
print(s.to_string(index=False, float_format=lambda v: f"{v:.3g}"))
