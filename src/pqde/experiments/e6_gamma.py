"""E6 -- accuracy vs. the smoothing constant gamma.

gamma = gamma_mult * Eq. (12) (gamma_mult = 0 is the unsmoothed HD in the
selection utility), eps and every other parameter at their defaults.  Same
metrics and raw-data layout as E2: ``results/e6/raw/trials.csv``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .accuracy import accuracy_rows, plot_all, summarise
from .common import out_dir, read_raw, run_metadata, to_markdown, write_csv, write_json, write_raw

EXP = "e6"


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    summary = summarise(read_raw(EXP, "trials", base))
    write_csv(summary, od / "summary.csv")
    plot_all(summary, cfg, od, "value", "gamma / gamma_Eq.(12)", True, "gamma")
    piv = summary.pivot_table(index="pair", columns="value", values="ratio_B2_mean", sort=False).reset_index()
    piv.columns = ["pair"] + [f"x{c:g}" for c in piv.columns[1:]]
    (od / "ratio_B2_by_gamma.md").write_text(to_markdown(piv))


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False, trials: int | None = None) -> dict:
    pairs = pairs or cfg["pairs"]
    trials = trials or (3 if quick else int(cfg["defaults"]["trials"]))
    mults = [float(x) for x in cfg[EXP]["gamma_mults"]]
    rows, brows = [], []
    for pid in pairs:
        r, b = accuracy_rows(pid, cfg, "gamma_mult", mults, trials)
        rows += r
        brows += b
        df = pd.DataFrame(r).groupby("value").ratio_B2.mean()
        print(f"  E6 {pid}: ratio vs B2 by gamma_mult " + " ".join(f"{k:g}:{v:.2f}" for k, v in df.items()))
    write_raw(pd.DataFrame(rows), EXP, "trials", base)
    write_raw(pd.DataFrame(brows), EXP, "baselines", base)
    write_json(run_metadata(cfg, experiment=EXP, pairs=pairs, trials=trials), out_dir(EXP, base) / "metadata.json")
    plot(cfg, base)
    return {}
