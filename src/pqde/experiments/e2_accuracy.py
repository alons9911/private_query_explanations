"""E2 -- accuracy of the released explanations vs. the privacy budget (Section 5.3.1).

Every pair, every eps of the grid, ``trials`` private runs; all other parameters
at their defaults.  Metrics against B1, B2, B3: ApproxRatio (Table 3, Fig. 6),
Jaccard, precision@k, attribute precision@k and view Jaccard of the released
set; plus the error of the released histograms.

Raw data: ``results/e2/raw/trials.csv`` (one row per private run, with the
released set) and ``raw/baselines.csv``.  ``pqde plot e2`` rebuilds every figure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .accuracy import accuracy_rows, plot_all, summarise
from .common import out_dir, read_raw, run_metadata, to_markdown, write_csv, write_json, write_raw

EXP = "e2"


def table3(summary: pd.DataFrame, epsilons: list[float], order: list[str]) -> pd.DataFrame:
    rows = []
    for pid in order:
        sub = summary[summary.pair == pid]
        row = {"pair": pid}
        for eps in epsilons:
            s = sub[np.isclose(sub.value, eps)]
            for metric in ("ratio", "precision_at_k", "jaccard"):
                for b in ("B1", "B2", "B3"):
                    col = f"{metric}_{b}_mean"
                    row[f"eps={eps:g} {metric} {b}"] = round(float(s[col].iloc[0]), 3) if len(s) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    summary = summarise(read_raw(EXP, "trials", base))
    write_csv(summary, od / "summary.csv")
    plot_all(summary, cfg, od, "value", "privacy budget eps", True, "eps")
    t3 = table3(summary, [float(x) for x in cfg[EXP]["table_epsilons"]], list(dict.fromkeys(summary.pair)))
    write_csv(t3, od / "table3.csv")
    cols = ["pair"] + [c for c in t3.columns if " ratio " in c]
    (od / "table3_approx_ratio.md").write_text(to_markdown(t3[cols]))
    cols = ["pair"] + [c for c in t3.columns if " precision_at_k " in c or " jaccard " in c]
    (od / "table_set_metrics.md").write_text(to_markdown(t3[cols]))


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False, trials: int | None = None) -> dict:
    pairs = pairs or cfg["pairs"]
    trials = trials or (3 if quick else int(cfg["defaults"]["trials"]))
    eps = [float(x) for x in cfg[EXP]["epsilons"]]
    rows, brows = [], []
    for pid in pairs:
        r, b = accuracy_rows(pid, cfg, "epsilon", eps, trials)
        rows += r
        brows += b
        df = pd.DataFrame(r)
        one = df[np.isclose(df.value, 1.0)]
        if len(one):
            print(f"  E2 {pid}: eps=1  ratio B2 {one.ratio_B2.mean():.3f}  P@k B2 {one.precision_at_k_B2.mean():.3f}"
                  f"  Jaccard B2 {one.jaccard_B2.mean():.3f}")
    write_raw(pd.DataFrame(rows), EXP, "trials", base)
    write_raw(pd.DataFrame(brows), EXP, "baselines", base)
    write_json(run_metadata(cfg, experiment=EXP, pairs=pairs, trials=trials), out_dir(EXP, base) / "metadata.json")
    plot(cfg, base)
    return {}
