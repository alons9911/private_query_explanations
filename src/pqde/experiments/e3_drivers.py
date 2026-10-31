"""E3 -- what drives accuracy (Section 5.3.1), on every pair.

(a) margins      gap between the leading round-1 candidates, absolute, relative and
                 in units of the exponential-mechanism resolution 2 Delta ln|C| / eps_i;
                 and the gap at the tau-th view against the top-tau Gumbel scale;
(b) bins         median non-empty bin and the share of bins below gamma (per dataset);
(c) view stage   overlap of the privately retained tau views with the exact
                 top-tau by Use, and the lowest Use retained, as eps_P varies
                 (everything else at the defaults);
(d) split        ApproxRatio vs B2 and precision@k vs B2 under (eps_P, eps_S, eps_H) splits, eps = 1.

The accuracy-vs-gamma experiment is E6.  Raw data: ``results/e3/raw/*.csv``.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import USE_SENSITIVITY_CONST, explain, select_views
from ..baselines import b2, exact_top_views, objective
from ..metrics import set_metrics
from ..pairs import resolve_pair
from .common import (default_cache, make_params, out_dir, pairs_by_dataset, read_raw, run_metadata, spawn_rngs,
                     stable_key, to_markdown, write_csv, write_json, write_raw)

EXP = "e3"


def margins(pid: str, cfg: dict) -> dict:
    d = cfg["defaults"]
    cache = default_cache(pid, d)
    p = make_params(d, cache.n_views, len(cache.explain_attrs))
    eps_P, eps_S, _ = p.budgets()
    rows = exact_top_views(cache, p.tau)
    out = {"pair": pid, "dataset": cache.ds.name, "tau": p.tau, "gamma": p.gamma}
    for name, g in (("smoothed", p.gamma), ("unsmoothed", 0.0)):
        hd = cache.hd_matrix(g, rows).ravel()
        hd = np.sort(hd[~np.isnan(hd)])[::-1]
        gap = float(hd[0] - hd[1]) if len(hd) > 1 else float("nan")
        out.update({f"{name}_u1": float(hd[0]), f"{name}_margin_abs": gap,
                    f"{name}_margin_rel": gap / hd[0] if hd[0] else float("nan"), "n_candidates": len(hd)})
    res = 2 * (1.0 / (1.0 + p.gamma)) * math.log(out["n_candidates"]) / (eps_S / p.k)
    out["em_resolution"] = res
    out["margin_over_resolution"] = out["smoothed_margin_abs"] / res
    use = np.sort(cache.use)[::-1]
    out["use_gap_tau"] = float(use[p.tau - 1] - use[p.tau]) if len(use) > p.tau else float("nan")
    out["use_gumbel_scale"] = 2 * p.tau * (USE_SENSITIVITY_CONST / cache.N) / eps_P
    out["use_gap_over_scale"] = out["use_gap_tau"] / out["use_gumbel_scale"]
    return out


def bin_stats(pid: str, cfg: dict) -> dict:
    d = cfg["defaults"]
    cache = default_cache(pid, d)
    p = make_params(d, cache.n_views, len(cache.explain_attrs))
    cache.ensure_histograms(np.arange(cache.n_views))
    c = np.concatenate([cache.hist[a][0][cache.valid[a]].ravel() for a in cache.explain_attrs])
    c = c[c > 0]
    out = {"dataset": cache.ds.name, "pair": pid, "N": cache.N, "nonempty_bins": int(len(c)),
           "median_nonempty_bin": float(np.median(c)), "gamma_default": p.gamma,
           "share_bins_below_gamma_default": float(np.mean(c < p.gamma))}
    for pc in cfg[EXP]["bin_stat_gamma_percent"]:
        out[f"share_bins_below_gamma_{pc}%N"] = float(np.mean(c < pc / 100 * cache.N))
    return out


def view_stage_rows(pid: str, cfg: dict, trials: int) -> list[dict]:
    d = cfg["defaults"]
    cache = default_cache(pid, d)
    p = make_params(d, cache.n_views, len(cache.explain_attrs))
    exact = exact_top_views(cache, p.tau)
    exact_set = set(int(x) for x in exact)
    use = cache.use
    tau_th = float(use[exact[-1]])
    rows = []
    for eps_P in cfg[EXP]["view_stage_eps_P"]:
        for t, rng in enumerate(spawn_rngs(int(d["seed"]), trials, stable_key(pid), int(eps_P * 1e4))):
            ret, _ = select_views(cache, p.tau, float(eps_P), rng)
            rows.append({"pair": pid, "dataset": cache.ds.name, "eps_P": eps_P, "trial": t, "tau": p.tau,
                         "overlap": len(set(int(x) for x in ret) & exact_set) / p.tau,
                         "lowest_use_over_tau_th": float(use[ret].min()) / tau_th if tau_th else np.nan,
                         "retained": json.dumps([cache.view_label(int(v)) for v in ret])})
    return rows


def split_rows(pid: str, cfg: dict, trials: int) -> list[dict]:
    d = cfg["defaults"]
    cache = default_cache(pid, d)
    base = make_params(d, cache.n_views, len(cache.explain_attrs))
    ref = b2(cache, base)
    F2 = objective(cache, ref, base.lam)
    ref_lab = [(cache.view_label(v), a) for v, a in ref]
    rows = []
    for split in cfg[EXP]["splits"]:
        p = make_params(d, cache.n_views, len(cache.explain_attrs), split=list(split))
        for t, rng in enumerate(spawn_rngs(int(d["seed"]), trials, stable_key(pid), stable_key(str(split)))):
            res = explain(cache, p, rng)
            lab = [(cache.view_label(v), a) for v, a in res.selections]
            rows.append({"pair": pid, "dataset": cache.ds.name, "split": "/".join(f"{x:.2f}" for x in split),
                         "trial": t, "ratio_B2": objective(cache, res.selections, p.lam) / F2 if F2 else np.nan,
                         **{f"{k}_B2": v for k, v in set_metrics(lab, ref_lab, p.k).items()},
                         "selections": json.dumps(lab)})
    return rows


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    v = read_raw(EXP, "view_stage", base)
    vs = v.groupby(["dataset", "pair", "eps_P"], as_index=False, sort=False).agg(
        overlap=("overlap", "mean"), lowest_use_over_tau_th=("lowest_use_over_tau_th", "mean"))
    write_csv(vs, od / "view_stage_summary.csv")
    for ds, sub in vs.groupby("dataset", sort=False):
        plotting.plot_lines(sub, "eps_P", [("overlap", "")], od / f"view_stage_{ds}", hue="pair", logx=True,
                            title=f"{ds}: view stage alone, overlap with the exact top-tau",
                            xlabel="eps_P", ylabel="|P_hat ∩ top-tau| / tau", ylim=(0, 1.05))
    piv = vs.pivot_table(index="eps_P", columns="pair", values="overlap", sort=False).reset_index()
    (od / "view_stage_overlap.md").write_text(to_markdown(piv))
    s = read_raw(EXP, "budget_split", base)
    ss = s.groupby(["pair", "split"], as_index=False, sort=False)[["ratio_B2", "precision_at_k_B2"]].mean()
    write_csv(ss, od / "budget_split_summary.csv")
    for col in ("ratio_B2", "precision_at_k_B2"):
        piv = ss.pivot_table(index="split", columns="pair", values=col, sort=False).reset_index()
        (od / f"budget_split_{col}.md").write_text(to_markdown(piv))


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False, trials: int | None = None) -> dict:
    pairs = pairs or cfg["pairs"]
    trials = trials or (3 if quick else int(cfg["defaults"]["trials"]))
    od = out_dir(EXP, base)
    write_csv(pd.DataFrame([margins(p, cfg) for p in pairs]), od / "margins.csv")
    by_ds = pairs_by_dataset(pairs, cfg.get("datasets"))
    write_csv(pd.DataFrame([bin_stats(pids[0], cfg) for pids in by_ds.values()]), od / "bin_stats.csv")
    vrows, srows = [], []
    for p in pairs:
        vrows += view_stage_rows(p, cfg, trials)
        srows += split_rows(p, cfg, trials)
        print(f"  E3 {p}", flush=True)
    write_raw(pd.DataFrame(vrows), EXP, "view_stage", base)
    write_raw(pd.DataFrame(srows), EXP, "budget_split", base)
    write_json(run_metadata(cfg, experiment=EXP, pairs=pairs, trials=trials), od / "metadata.json")
    plot(cfg, base)
    return {}
