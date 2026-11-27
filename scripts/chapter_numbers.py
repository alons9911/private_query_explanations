"""Every number of the experiments chapter (refinement pairs of configs/experiments.yaml), from results/.

Prints Table 2 (quality at the defaults), the rows of Table 3 (one parameter varied) and the numbers
quoted in the text.  Means over the runs of a pair, then over the pairs of a dataset; "all" weights the
pairs equally.

Usage: python scripts/chapter_numbers.py
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import yaml

R = "results/rescored/"
cfg = yaml.safe_load(open("configs/experiments.yaml"))
PAIRS = list(cfg["pairs"])
ORDER = ["adult", "acsincome", "tax", "compas", "law", "meps"]
bf = pd.read_csv(R + "bf.csv")[["pair", "dataset"]]
bf = bf[bf.pair.isin(PAIRS)]
DS = bf.set_index("pair").dataset


def ds(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in ["dataset"] if c in df]).merge(bf, on="pair")
    return df


def per_pair(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("pair")[col].mean()


def by_ds(s: pd.Series) -> pd.Series:
    t = s.groupby(DS.reindex(s.index)).mean().reindex(ORDER)
    t["all"] = s.mean()
    return t


e2 = ds(pd.read_csv(R + "e2.csv"))
e2_1 = e2[np.isclose(e2.epsilon, 1)]
b1 = ds(pd.read_csv(R + "e2_b1.csv"))
b1_1 = b1[np.isclose(b1.value, 1.0)]  # one B1 row per eps of the sweep (gamma follows the rule): take eps = 1
comp = ds(pd.read_csv(R + "e8_competitors.csv"))
comp_1 = comp[np.isclose(comp.epsilon, 1)]
ch = ds(pd.read_csv(R + "chance.csv")).set_index("pair").chance_attr_at_k
rn = pd.read_csv(R + "review_numbers.csv").set_index("pair")
rn = rn[rn.index.isin(PAIRS)]
vp = pd.read_csv("results/e8/view_profile.csv")
vp = vp[vp.pair.isin(PAIRS)]

T = pd.DataFrame({
    "PrivExpl": by_ds(per_pair(e2_1, "ratio_BF")),
    "B1": by_ds(per_pair(b1_1, "ratio_BF")),
    "Single": by_ds(per_pair(comp_1[comp_1.method == "SingleStage"], "ratio_BF")),
    "Random": by_ds(per_pair(comp_1[comp_1.method == "Random"], "ratio_BF")),
    "attr": by_ds(per_pair(e2_1, "attr_at_k_BF")),
    "chance": by_ds(ch[ch.index.isin(PAIRS)]),
    "attr_Single": by_ds(per_pair(comp_1[comp_1.method == "SingleStage"], "attr_at_k_BF")),
    "cov": by_ds(rn.cov_PrivExpl),
    "cov_Single": by_ds(vp[vp.set == "SingleStage"].set_index("pair").coverage),
    "cov_BF": by_ds(rn.cov_BF),
})
print("== Table 2 (quality at the defaults)")
print(T.round(2).to_string())
print("mean of the dataset means (PrivExpl):", round(T.loc[ORDER, "PrivExpl"].mean(), 3))
print("pairs per dataset:", DS.value_counts().reindex(ORDER).to_dict(), "total", len(DS))


def row(df: pd.DataFrame, key: str, col: str = "ratio_BF") -> pd.Series:
    d = df[df.pair.isin(PAIRS)]
    return d.groupby(key).apply(lambda x: x.groupby("pair")[col].mean().mean())


print("\n== Table 3 rows (mean over the pairs)")
t = ds(pd.read_csv(R + "e8_tau.csv"))
t["t"] = np.where(t.tau_is_all.astype(str) == "True", "all", t.tau.astype(int).astype(str))
cols = ["5", "10", "15", "30", "60", "120", "250", "500", "1000"]
per = t.groupby(["pair", "t"]).ratio_BF.mean().unstack()
for c in cols:
    per[c] = per[c].fillna(per["all"]) if c in per else per["all"]
print("tau ApproxRatio:", " & ".join(f"{per[c].mean():.2f}" for c in cols + ["all"]))
print("tau=all by dataset:", per["all"].groupby(DS.reindex(per.index)).mean().reindex(ORDER).round(3).to_dict())
cv = pd.read_csv(R + "coverage_tau.csv")
cv = cv[cv.pair.isin(PAIRS)]
cv["t"] = np.where(cv.tau_is_all.astype(str) == "True", "all", cv.tau.astype(int).astype(str))
pc = cv.groupby(["pair", "t"]).coverage.mean().unstack()
for c in cols:
    pc[c] = pc[c].fillna(pc["all"]) if c in pc else pc["all"]
print("tau coverage:   ", " & ".join(f"{pc[c].mean():.2f}" for c in cols + ["all"]))
e3 = ds(pd.read_csv(R + "e3.csv"))
print("split:", row(e3, "split").round(3).to_dict())
print("eps rule:", " & ".join(f"{v:.2f}" for v in row(e2, "epsilon")))
fg = ds(pd.read_csv(R + "e8_fixed_gamma.csv"))
print("eps fixed gamma:", " & ".join(f"{v:.2f}" for v in row(fg, "epsilon")))
e6 = ds(pd.read_csv(R + "e6.csv"))
print("gamma:", " & ".join(f"{v:.2f}" for v in row(e6, "value")))
lam = ds(pd.read_csv(R + "e8_lambda.csv"))
print("lambda ApproxRatio:", " & ".join(f"{v:.2f}" for v in row(lam, "lam")))
raw_lam = pd.read_csv("results/e8/raw/lambda.csv")
raw_lam = raw_lam[raw_lam.pair.isin(PAIRS)]
print("lambda distinct attrs:", " & ".join(f"{v:.1f}" for v in raw_lam.groupby("lam").apply(lambda x: x.groupby("pair").distinct_attrs.mean().mean())))

print("\n== text numbers")
pp = pd.DataFrame({"priv": per_pair(e2_1, "ratio_BF"), "b1": per_pair(b1_1, "ratio_BF")})
pp["ds"] = DS.reindex(pp.index)
print("PrivExpl per pair (lowest 6):", pp.sort_values("priv").head(6).round(2).to_dict("index"))
print("noise cost (B1 - PrivExpl) largest:", (pp.b1 - pp.priv).sort_values(ascending=False).head(6).round(2).to_dict())
vs = pd.read_csv("results/e3/raw/view_stage.csv")
vs = vs[vs.pair.isin(PAIRS)]
o = vs[np.isclose(vs.eps_P, 1 / 3, atol=1e-3)]
print("view overlap at eps_P=1/3 by dataset:", o.groupby("dataset").overlap.mean().reindex(ORDER).round(2).to_dict())
print("view overlap at eps_P=1/3 lowest pairs:", o.groupby("pair").overlap.mean().sort_values().head(5).round(2).to_dict())
print("view overlap at eps_P=0.1 (all):", round(vs[np.isclose(vs.eps_P, 0.1)].groupby("pair").overlap.mean().mean(), 2))
# precision@k against BF at eps = 1
raw2 = pd.read_csv("results/e2/raw/trials.csv")
raw2 = raw2[np.isclose(raw2.epsilon, 1) & raw2.pair.isin(PAIRS)]
bfs = pd.read_csv(R + "bf.csv").set_index("pair").BF
prec = raw2.assign(p=[len({tuple(x) for x in json.loads(s)} & {tuple(x) for x in json.loads(bfs[pid])}) / 5
                      for s, pid in zip(raw2.selections, raw2.pair)]).groupby("pair").p.mean()
print("precision@k: mean", round(prec.mean(), 2), "by dataset", by_ds(prec).round(2).to_dict())
print("attr below chance:", (T.attr < T.chance).to_dict())
eps_ds = e2[e2.pair.isin(PAIRS)].groupby(["dataset", "epsilon"]).ratio_BF.mean().unstack().round(2)
print("eps by dataset:\n", eps_ds.to_string())
sg = comp[(comp.method == "SingleStage") & comp.pair.isin(PAIRS)].groupby(["dataset", "epsilon"]).ratio_BF.mean().unstack().round(2)
print("SingleStage by eps:\n", sg.to_string())
g_ds = e6[e6.pair.isin(PAIRS)].groupby(["dataset", "value"]).ratio_BF.mean().unstack().round(2)
print("gamma by dataset:\n", g_ds.to_string())
print("median bin support:", rn.groupby(DS.reindex(rn.index)).median_bin_support.median().reindex(ORDER).round(0).to_dict())
print("best HD of exact top-tau (median):", rn.groupby(DS.reindex(rn.index)).best_hd_top_tau.median().reindex(ORDER).round(2).to_dict())
e7 = ds(pd.read_csv(R + "e7.csv"))
e7 = e7[e7.pair.isin(PAIRS)]
a7 = e7.groupby(["dataset", "n_attrs"]).ratio_BF.mean().unstack()
print("E7 ApproxRatio first->last:", {d: (round(a7.loc[d].dropna().iloc[0], 2), round(a7.loc[d].dropna().iloc[-1], 2)) for d in ORDER if d in a7.index})
k7 = e7.groupby(["dataset", "n_attrs"]).attr_at_k_BF.mean().unstack()
print("E7 attribute@k first->last:", {d: (round(k7.loc[d].dropna().iloc[0], 2), round(k7.loc[d].dropna().iloc[-1], 2)) for d in ORDER if d in k7.index})
e7g = ds(pd.read_csv(R + "e7g.csv"))
e7g = e7g[e7g.pair.isin(PAIRS)]
gdiff = (e7g.groupby(["dataset", "n_attrs"]).ratio_BF.mean() - e7.groupby(["dataset", "n_attrs"]).ratio_BF.mean()).abs().max()
print("E7 fixed gamma max |diff|:", round(gdiff, 3))
