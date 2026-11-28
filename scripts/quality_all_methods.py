"""Table 2 with every method: ApproxRatio, attribute@k and coverage against OPT at the defaults.

PEEQ, SingleStage and Random come from the stored runs (results/rescored, results/e8/view_profile.csv,
the same numbers as Table 2); OptPEEQ releases what PEEQ releases (identity check), so it repeats PEEQ.
The deterministic methods are recomputed per pair on the statistics cache, with HD at the pair's default
gamma: NonPrivate (b1), TopTauExhaustive (the optimum over the retained views; the pruned search returns
the same optimum, tie-breaking aside), TopK/FullExhaustive (the optimum over all views) and OPT.  Random's
coverage is its expectation: the mean Cov over all candidates.  Writes results/rescored/quality_all.csv
and paper/sections/quality_all_table.tex (appendix; copy in docs/table2_all_methods.tex).

Usage: python scripts/quality_all_methods.py
"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, "src")
from pqde.baselines import b1, b2, objective, opt_all  # noqa: E402
from pqde.experiments.common import make_params  # noqa: E402
from pqde.pairs import resolve_pair  # noqa: E402
from pqde.runner import ORIGINAL_ROUTE  # noqa: E402
from pqde.stats import build_cache  # noqa: E402
from pqde.views import enumerate_views  # noqa: E402

cfg = yaml.safe_load(open("configs/experiments.yaml"))
d, PAIRS = cfg["defaults"], list(cfg["pairs"])
ORDER = ["adult", "acsincome", "tax", "compas", "law", "meps"]
TITLE = {"adult": "Adult", "acsincome": "ACSIncome", "tax": "Tax", "compas": "COMPAS", "law": "Law Students", "meps": "MEPS"}
R = Path("results/rescored")


def attr_at_k(sel, ref, k):
    a, b = Counter(x for _, x in sel), Counter(x for _, x in ref)
    return sum((a & b).values()) / k


rows = []
for pid in PAIRS:
    p = resolve_pair(pid)
    nv = len(enumerate_views(p.dataset))
    prm = make_params(d, nv, len(p.dataset.explain_attrs))
    g, k, lam = prm.gamma, prm.k, prm.lam
    c = build_cache(p.dataset, p.q1, p.q2, **ORIGINAL_ROUTE)
    cov = c.cov
    opt = opt_all(c, prm, g)
    f_opt = objective(c, opt, lam, g)
    sets = {"NonPrivate": b1(c, prm).selections, "TopTauExhaustive": b2(c, prm, g),
            "ExhaustiveAll": b2(c, prm, g, pool="all"), "OPT": opt}
    row = {"pair": pid, "dataset": p.dataset.name}
    for m, sel in sets.items():
        row[f"ratio_{m}"] = objective(c, sel, lam, g) / f_opt
        row[f"attr_{m}"] = attr_at_k(sel, opt, k)
        row[f"cov_{m}"] = float(np.mean([cov[v] for v, _ in sel]))
        row[f"same_as_OPT_{m}"] = sorted(sel) == sorted(opt)
    valid = np.stack([c.valid[a] for a in c.explain_attrs], axis=1)   # views x attrs candidates
    row["cov_Random"] = float((cov[:, None] * valid).sum() / valid.sum())
    rows.append(row)
    print(pid, {kk: round(v, 3) for kk, v in row.items() if kk.startswith("ratio")}, flush=True)
Q = pd.DataFrame(rows)

# stored runs: PEEQ, SingleStage, Random (as chapter_numbers.py)
e2 = pd.read_csv(R / "e2.csv"); e2 = e2[e2.pair.isin(PAIRS) & np.isclose(e2.epsilon, 1)]
comp = pd.read_csv(R / "e8_competitors.csv"); comp = comp[comp.pair.isin(PAIRS) & np.isclose(comp.epsilon, 1)]
rn = pd.read_csv(R / "review_numbers.csv").set_index("pair")
vp = pd.read_csv("results/e8/view_profile.csv")
ch = pd.read_csv(R / "chance.csv").set_index("pair").chance_attr_at_k
Q = Q.set_index("pair")
Q["ratio_PEEQ"] = e2.groupby("pair").ratio_BF.mean()
Q["attr_PEEQ"] = e2.groupby("pair").attr_at_k_BF.mean()
Q["cov_PEEQ"] = rn.cov_PrivExpl
for m in ("SingleStage", "Random"):
    x = comp[comp.method == m]
    Q[f"ratio_{m}"] = x.groupby("pair").ratio_BF.mean()
    Q[f"attr_{m}"] = x.groupby("pair").attr_at_k_BF.mean()
Q["cov_SingleStage"] = vp[vp.set == "SingleStage"].set_index("pair").coverage
Q["chance"] = ch
Q.to_csv(R / "quality_all.csv")
M = ["PEEQ", "OptPEEQ", "NonPrivate", "TopTauExhaustive", "SingleStage", "Random", "OPT", "TopKExhaustive", "FullExhaustive"]
SRC = {"OptPEEQ": "PEEQ", "TopKExhaustive": "ExhaustiveAll", "FullExhaustive": "ExhaustiveAll"}
by = Q.groupby("dataset").mean(numeric_only=True).reindex(ORDER)
by.loc["all"] = Q.mean(numeric_only=True)
print("\nsame set as OPT (pairs):", {m: int(Q[f"same_as_OPT_{m}"].sum()) for m in ("NonPrivate", "TopTauExhaustive", "ExhaustiveAll")})
print("TopTauExhaustive vs NonPrivate, max |ratio diff|:", float((Q.ratio_TopTauExhaustive - Q.ratio_NonPrivate).abs().max()),
      " attr diff:", float((Q.attr_TopTauExhaustive - Q.attr_NonPrivate).abs().max()))

macro = {"PEEQ": r"\sys{}", "OptPEEQ": r"\sysopt{}", "NonPrivate": r"\Bone{}", "TopTauExhaustive": r"\Btwo{}",
         "SingleStage": r"\SingleStage{}", "Random": r"\RandomExpl{}", "OPT": r"\BF{}", "TopKExhaustive": r"\TopKExh{}",
         "FullExhaustive": r"\FullExh{}"}


def cell(metric, m, ds):
    col = f"{metric}_{SRC.get(m, m)}"
    if col not in by:
        return "--"
    v = by.loc[ds, col]
    s = f"{v:.2f}"
    if metric == "attr" and m == "PEEQ":
        s += f" ({by.loc[ds, 'chance']:.2f})"
    return s


L = [r"% generated by `python scripts/quality_all_methods.py` -- do not edit (appendix: Table 2 with every method)",
     r"\begin{table*}[t]", r"\centering", r"\scriptsize",
     r"\caption{Quality at the defaults against \BF{}, every method; mean over the pairs of each dataset. "
     r"\sysopt{} releases what \sys{} releases; \Btwo{} reaches the optimum over the retained views and \TopKExh{} and "
     r"\FullExh{} the optimum over all views, computed here once per pair. Attribute@k: chance level in parentheses. "
     r"Coverage: mean $\Cov$ of the explained views (\RandomExpl{}: its expectation).}",
     r"\label{tab:quality-all}",
     r"\setlength{\tabcolsep}{1.6pt}", r"\resizebox{\textwidth}{!}{\begin{tabular}{@{}l" + "c" * 27 + "@{}}", r"\toprule",
     r" & \multicolumn{9}{c}{ApproxRatio} & \multicolumn{9}{c}{Attribute@k} & \multicolumn{9}{c}{Coverage} \\",
     r"\cmidrule(lr){2-10}\cmidrule(lr){11-19}\cmidrule(l){20-28}",
     "Dataset & " + " & ".join(r"\rotatebox{90}{" + macro[m] + "}" for m in M * 3) + r" \\", r"\midrule"]
for ds in ORDER + ["all"]:
    if ds == "all":
        L.append(r"\midrule")
    name = TITLE.get(ds, "All $36$ pairs")
    L.append(name + " & " + " & ".join(cell(met, m, ds) for met in ("ratio", "attr", "cov") for m in M) + r" \\")
L += [r"\bottomrule", r"\end{tabular}}", r"\end{table*}"]
for out in ("paper/sections/quality_all_table.tex", "docs/table2_all_methods.tex"):
    Path(out).write_text("\n".join(L) + "\n")
print("written paper/sections/quality_all_table.tex")
