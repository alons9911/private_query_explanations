"""E2 -- quality of the released explanations vs. the privacy budget (Section 5.3.1).

For every pair and eps in the grid the private algorithm is run ``trials``
times; each released set is scored with ``F_lambda`` (gamma_eval = 0) and
divided by the score of the B1, B2 and B3 sets.  Outputs Table 3 and Figure 6.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import explain
from ..baselines import b1, b2, b3, objective
from ..pairs import pair_cache, resolve_pair
from .common import (Timer, out_dir, params_from, run_metadata, spawn_rngs, stable_key, to_markdown, write_csv,
                     write_json)


def evaluate_pair(pair_id: str, cfg: dict, epsilons: list[float], trials: int) -> tuple[pd.DataFrame, dict]:
    d = cfg["defaults"]
    cache = pair_cache(pair_id)
    lam, ge = float(d["lam"]), float(d.get("gamma_eval", 0.0))
    base_params = params_from(d)
    # B2 and B3 do not depend on eps (tau depends on k only, gamma_eval is fixed)
    with Timer() as t2:
        sel2, info2 = b2(cache, base_params, ge, return_info=True)
    with Timer() as t3:
        sel3 = b3(cache, base_params, ge)
    F2, F3 = objective(cache, sel2, lam, ge), objective(cache, sel3, lam, ge)
    rows = []
    base = {"pair": pair_id, "B2_F": F2, "B3_F": F3}
    for eps in epsilons:
        params = params_from(d, epsilon=eps)
        r1 = b1(cache, params)
        F1 = objective(cache, r1.selections, lam, ge)
        for t, rng in enumerate(spawn_rngs(int(d["seed"]), trials, stable_key(pair_id), int(eps * 1e4))):
            res = explain(cache, params, rng)
            F = objective(cache, res.selections, lam, ge)
            rows.append({
                "pair": pair_id, "epsilon": eps, "trial": t, "F": F, "B1_F": F1, "B2_F": F2, "B3_F": F3,
                "ratio_B1": F / F1 if F1 else np.nan, "ratio_B2": F / F2 if F2 else np.nan,
                "ratio_B3": F / F3 if F3 else np.nan, "gamma": res.gamma, "tau": res.tau,
                "mechanism_ms": res.timings["mechanism_ms"],
                "views_overlap_B3": len({v for v, _ in res.selections} & {v for v, _ in sel3}),
            })
    info = {**base, "B2_pool": info2["pool_size"], "B2_subsets": info2["subsets"], "B2_seconds": t2.seconds,
            "B3_seconds": t3.seconds, "B2_equals_B3": bool(abs(F2 - F3) <= 1e-9 * max(1.0, F2)),
            "B2_set": [(cache.view_label(v), a) for v, a in sel2], "B3_set": [(cache.view_label(v), a) for v, a in sel3]}
    return pd.DataFrame(rows), info


def summarise(trials: pd.DataFrame) -> pd.DataFrame:
    g = trials.groupby(["pair", "epsilon"])
    out = g.agg(
        F_mean=("F", "mean"), F_std=("F", "std"), B1_F=("B1_F", "first"), B2_F=("B2_F", "first"),
        B3_F=("B3_F", "first"), ratio_B1_mean=("ratio_B1", "mean"), ratio_B1_std=("ratio_B1", "std"),
        ratio_B2_mean=("ratio_B2", "mean"), ratio_B2_std=("ratio_B2", "std"), ratio_B3_mean=("ratio_B3", "mean"),
        ratio_B3_std=("ratio_B3", "std"), gamma=("gamma", "first"), tau=("tau", "first"), trials=("F", "size"),
        mechanism_ms_median=("mechanism_ms", "median"),
    ).reset_index()
    return out


def table3(summary: pd.DataFrame, epsilons: list[float], order: list[str] | None = None) -> pd.DataFrame:
    rows = []
    order = order or list(dict.fromkeys(summary.pair))
    for pid in order:
        sub = summary[summary.pair == pid]
        row = {"pair": pid}
        for eps in epsilons:
            s = sub[np.isclose(sub.epsilon, eps)]
            for b in ("B1", "B2", "B3"):
                row[f"eps={eps:g} {b}"] = round(float(s[f"ratio_{b}_mean"].iloc[0]), 3) if len(s) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False, trials: int | None = None) -> dict:
    e = cfg["e2"]
    pairs = pairs or e["pairs"]
    trials = trials or (5 if quick else int(cfg["defaults"]["trials"]))
    epsilons = [float(x) for x in e["epsilons"]]
    all_rows, infos = [], {}
    for pid in pairs:
        df, info = evaluate_pair(pid, cfg, epsilons, trials)
        all_rows.append(df)
        info["synthetic_data"] = bool(resolve_pair(pid).dataset.meta.get("synthetic", False))
        infos[pid] = info
        s = summarise(df)
        r = s[np.isclose(s.epsilon, 1.0)]
        if len(r):
            print(f"  E2 {pid}: eps=1 ratio vs B1/B2/B3 = {r.ratio_B1_mean.iloc[0]:.3f} / "
                  f"{r.ratio_B2_mean.iloc[0]:.3f} / {r.ratio_B3_mean.iloc[0]:.3f}  (B2==B3: {info['B2_equals_B3']})")
    trials_df = pd.concat(all_rows, ignore_index=True)
    summary = summarise(trials_df)
    od = out_dir("e2", base)
    write_csv(trials_df, od / "trials.csv")
    write_csv(summary, od / "summary.csv")
    t3 = table3(summary, [float(x) for x in e["table_epsilons"]], pairs)
    write_csv(t3, od / "table3_approx_ratio.csv")
    (od / "table3_approx_ratio.md").write_text(to_markdown(t3))
    write_json({"baselines": infos, **run_metadata(cfg, experiment="e2", pairs=pairs, trials=trials)},
               od / "metadata.json")
    fig_pairs = [p for p in e.get("figure_pairs", pairs) if p in pairs] or pairs
    titles = {p: f"{p} ({resolve_pair(p).dataset.name})" for p in pairs}
    plotting.plot_approx_ratio(summary, fig_pairs, od / "fig6_approx_ratio", titles)
    plotting.plot_approx_ratio(summary, pairs, od / "approx_ratio_all_pairs", titles)
    return {"summary": summary, "table3": t3}
