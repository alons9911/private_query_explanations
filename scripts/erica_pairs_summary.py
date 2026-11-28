"""Quality on Erica's own pairs (EA*, EC*, EH*), kept apart from the paper's pairs.

Reads results_erica/rescored/ (scripts/rescore_bruteforce.py with RESCORE_BASE=results_erica) and writes
results/erica_pairs/summary.csv: per pair |Q1|, |Q2|, the tuples the refinement changes, and at eps = 1
the ApproxRatio against OPT of PEEQ, NonPrivate, SingleStage and Random, attribute@k and its chance level;
plus PEEQ's ApproxRatio against eps.

Usage: python scripts/erica_pairs_summary.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

from pqde.pairs import resolve_pair

R = Path("results_erica/rescored")
OUT = Path("results/erica_pairs")
OUT.mkdir(parents=True, exist_ok=True)
e2 = pd.read_csv(R / "e2.csv")
b1 = pd.read_csv(R / "e2_b1.csv")
comp = pd.read_csv(R / "e8_competitors.csv")
ch = pd.read_csv(R / "chance.csv").set_index("pair").chance_attr_at_k
rows = []
for pid in dict.fromkeys(e2.pair):
    p = resolve_pair(pid)
    one = lambda d: d[(d.pair == pid) & np.isclose(d.epsilon, 1)]
    c = one(comp)
    rows.append({"pair": pid, "dataset": p.dataset.name, "N": p.dataset.N, "n_q1": int(p.q1.sum()),
                 "n_q2": int(p.q2.sum()), "changed": int((p.q1 ^ p.q2).sum()),
                 "PEEQ": one(e2).ratio_BF.mean(),
                 "NonPrivate": b1[(b1.pair == pid) & np.isclose(b1.value, 1)].ratio_BF.mean(),
                 "SingleStage": c[c.method == "SingleStage"].ratio_BF.mean(),
                 "Random": c[c.method == "Random"].ratio_BF.mean(),
                 "attr_at_k": one(e2).attr_at_k_BF.mean(), "chance": ch.get(pid, np.nan),
                 **{f"PEEQ_eps{e:g}": e2[(e2.pair == pid) & np.isclose(e2.epsilon, e)].ratio_BF.mean()
                    for e in sorted(e2.epsilon.unique())}})
t = pd.DataFrame(rows)
t.to_csv(OUT / "summary.csv", index=False)
pd.set_option("display.width", 250)
print(t.drop(columns=[c for c in t if c.startswith("PEEQ_eps")]).round(2).to_string(index=False))
print()
print(t[["pair"] + [c for c in t if c.startswith("PEEQ_eps")]].round(2).to_string(index=False))
