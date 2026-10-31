"""Shared accuracy machinery for E2 (accuracy vs eps) and E6 (accuracy vs gamma).

For one pair and one swept parameter, every private run is compared with the
three baselines: B2 and B3 do not depend on eps or gamma (gamma_eval = 0, tau
depends on k only) and are computed once; B1 is recomputed at every setting
because it keeps the setting's tau and gamma.

Raw output (one row per private run) carries the selected set and retained
views as JSON, so every metric can be recomputed later without re-running.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import explain
from ..baselines import b1, b2, b3, objective
from ..metrics import SET_METRICS, release_metrics, set_metrics
from ..pairs import resolve_pair
from .common import default_cache, make_params, pairs_by_dataset, spawn_rngs, stable_key

BASELINES = ("B1", "B2", "B3")
METRIC_LABELS = {
    "ratio": "ApproxRatio",
    "jaccard": "Jaccard",
    "precision_at_k": "precision@k",
    "attr_precision": "attribute precision@k",
    "view_jaccard": "view Jaccard",
}


def _labels(cache, sel):
    return [(cache.view_label(v), a) for v, a in sel]


def accuracy_rows(pair_id: str, cfg: dict, sweep: str, values: list[float], trials: int) -> tuple[list[dict], list[dict]]:
    d = cfg["defaults"]
    pair = resolve_pair(pair_id)
    cache = default_cache(pair_id, d)
    n_views, n_attrs = cache.n_views, len(cache.explain_attrs)
    lam, ge = float(d["lam"]), float(d.get("gamma_eval", 0.0))
    base = make_params(d, n_views, n_attrs)
    ref = {"B2": b2(cache, base, ge), "B3": b3(cache, base, ge)}
    ref_F = {b: objective(cache, s, lam, ge) for b, s in ref.items()}
    rows, base_rows = [], []
    for b in ("B2", "B3"):
        base_rows.append({"pair": pair_id, "sweep": sweep, "value": np.nan, "method": b, "F": ref_F[b],
                          "selections": json.dumps(_labels(cache, ref[b]))})
    for val in values:
        params = make_params(d, n_views, n_attrs, **{sweep: val})
        r1 = b1(cache, params)
        ref_v = {**ref, "B1": r1.selections}
        F_v = {**ref_F, "B1": objective(cache, r1.selections, lam, ge)}
        base_rows.append({"pair": pair_id, "sweep": sweep, "value": val, "method": "B1", "F": F_v["B1"],
                          "selections": json.dumps(_labels(cache, r1.selections))})
        ref_lab = {b: _labels(cache, s) for b, s in ref_v.items()}
        for t, rng in enumerate(spawn_rngs(int(d["seed"]), trials, stable_key(pair_id), stable_key(f"{sweep}={val}"))):
            res = explain(cache, params, rng)
            F = objective(cache, res.selections, lam, ge)
            lab = _labels(cache, res.selections)
            row = {"pair": pair_id, "dataset": pair.dataset.name,
                   "synthetic": bool(pair.dataset.meta.get("synthetic", False)), "sweep": sweep, "value": val,
                   "trial": t, "epsilon": params.epsilon, "gamma": res.gamma, "tau": res.tau, "k": params.k, "F": F}
            for bname in BASELINES:
                row[f"F_{bname}"] = F_v[bname]
                row[f"ratio_{bname}"] = F / F_v[bname] if F_v[bname] else np.nan
                for mname, mval in set_metrics(lab, ref_lab[bname], params.k).items():
                    row[f"{mname}_{bname}"] = mval
            row.update(release_metrics(res.explanations))
            row["mechanism_ms"] = res.timings["mechanism_ms"]
            row["selections"] = json.dumps(lab)
            row["retained"] = json.dumps([cache.view_label(v) for v in res.retained])
            rows.append(row)
    return rows, base_rows


def summarise(raw: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [c for c in raw.columns if any(c.startswith(m + "_B") for m in ["ratio", *SET_METRICS])]
    metric_cols += ["hist_rel_l1", "diff_sign_acc", "F", "F_B1", "F_B2", "F_B3", "gamma", "tau", "mechanism_ms"]
    g = raw.groupby(["pair", "dataset", "synthetic", "sweep", "value"], sort=False)
    mean = g[metric_cols].mean().add_suffix("_mean")
    std = g[[c for c in metric_cols if c.startswith(("ratio", *SET_METRICS, "hist", "diff"))]].std().add_suffix("_std")
    out = pd.concat([mean, std], axis=1).reset_index()
    out["trials"] = g.size().to_numpy()
    return out


def plot_all(summary: pd.DataFrame, cfg: dict, od, x: str, xlabel: str, logx: bool, tag: str) -> None:
    pairs = list(dict.fromkeys(summary.pair))
    by_ds = pairs_by_dataset(pairs, cfg.get("datasets"))
    syn = {r.dataset: bool(r.synthetic) for r in summary.itertuples()}
    for metric, label in METRIC_LABELS.items():
        plotting.plot_accuracy_grid(summary, by_ds, metric, label, od / f"{tag}_{metric}_by_pair", xlabel=xlabel,
                                    logx=logx, synthetic=syn)
        plotting.plot_accuracy_datasets(summary, by_ds, metric, label, od / f"{tag}_{metric}_by_dataset",
                                        xlabel=xlabel, logx=logx, synthetic=syn)
    plotting.plot_release_quality(summary, by_ds, od / f"{tag}_release_quality", xlabel=xlabel, logx=logx,
                                  synthetic=syn)
