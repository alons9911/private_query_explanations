"""E3 -- what drives accuracy (Section 5.3.1).

(a) margins      gap between the leading candidates the exponential mechanism
                 must separate, in absolute terms and in units of its
                 resolution 2 * Delta * ln|C| / eps_i;
(b) gamma        ApproxRatio as the smoothing constant moves around Eq. (12);
(c) bins         how gamma compares with the bin counts it competes with
                 (median non-empty bin, share of bins below gamma);
(d) view stage   the view stage in isolation: overlap of the privately retained
                 tau views with the exact top-tau by Use and the lowest Use
                 retained, as a function of eps_P (the experiment the paper
                 lists as TODO);
(e) split        ApproxRatio under different (eps_P, eps_S, eps_H) splits.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import USE_SENSITIVITY_CONST, choose_gamma, choose_tau, explain, select_views
from ..baselines import b1, b2, exact_top_views, objective
from ..pairs import pair_cache, resolve_pair
from .common import out_dir, params_from, run_metadata, spawn_rngs, stable_key, write_csv, write_json


def margins(pair_id: str, cfg: dict) -> dict:
    d = cfg["defaults"]
    params = params_from(d)
    cache = pair_cache(pair_id)
    eps_P, eps_S, eps_H = params.budgets()
    tau = choose_tau(params.k, cache.n_views, params.tau_factor)
    gamma = choose_gamma(tau, len(cache.explain_attrs), params.k, eps_S)
    rows = exact_top_views(cache, tau)
    out = {"pair": pair_id, "tau": tau, "gamma": gamma}
    for name, g in (("smoothed", gamma), ("unsmoothed", 0.0)):
        hd = cache.hd_matrix(g, rows).ravel()
        hd = np.sort(hd[~np.isnan(hd)])[::-1]
        n_c = len(hd)
        gap = float(hd[0] - hd[1]) if n_c > 1 else float("nan")
        out[f"{name}_u1"] = float(hd[0])
        out[f"{name}_u2"] = float(hd[1]) if n_c > 1 else float("nan")
        out[f"{name}_margin_abs"] = gap
        out[f"{name}_margin_rel"] = gap / hd[0] if hd[0] else float("nan")
        out["n_candidates"] = n_c
    # resolution of the exponential mechanism in round 1 (utilities differ by > this to be separated)
    eps_i = eps_S / params.k
    delta = 1.0 / (1.0 + gamma)
    res = 2 * delta * math.log(out["n_candidates"]) / eps_i
    out["em_resolution"] = res
    out["margin_over_resolution"] = out["smoothed_margin_abs"] / res
    # same for the view stage: gap between the tau-th and (tau+1)-th Use vs. the top-tau noise scale
    use = np.sort(cache.use)[::-1]
    use_delta = USE_SENSITIVITY_CONST / cache.N
    out["use_gap_tau"] = float(use[tau - 1] - use[tau]) if len(use) > tau else float("nan")
    out["use_gumbel_scale"] = 2 * tau * use_delta / eps_P
    out["use_gap_over_scale"] = out["use_gap_tau"] / out["use_gumbel_scale"]
    return out


def gamma_sweep(pair_id: str, cfg: dict, trials: int) -> pd.DataFrame:
    d = cfg["defaults"]
    e = cfg["e3"]
    cache = pair_cache(pair_id)
    params = params_from(d)
    lam = params.lam
    tau = choose_tau(params.k, cache.n_views, params.tau_factor)
    g0 = choose_gamma(tau, len(cache.explain_attrs), params.k, params.budgets()[1])
    F2 = objective(cache, b2(cache, params), lam)
    settings = [("multiplier", m, m * g0) for m in e["gamma_multipliers"]]
    settings += [("percent_of_N", pc, pc / 100 * cache.N) for pc in e["gamma_percent_of_N"]]
    rows = []
    for kind, val, g in settings:
        p = params.with_(gamma=float(g))
        F1 = objective(cache, b1(cache, p).selections, lam)
        Fs = [objective(cache, explain(cache, p, rng).selections, lam)
              for rng in spawn_rngs(int(d["seed"]), trials, stable_key(pair_id), stable_key(f"{kind}{val}"))]
        rows.append({"pair": pair_id, "setting": kind, "value": val, "gamma": g, "gamma_default": g0,
                     "ratio_B2_mean": np.mean(Fs) / F2, "ratio_B2_std": np.std(Fs) / F2,
                     "B1_ratio_to_B2": F1 / F2, "ratio_B1_mean": np.mean(Fs) / F1 if F1 else np.nan})
    return pd.DataFrame(rows)


def bin_stats(pair_id: str, cfg: dict) -> dict:
    cache = pair_cache(pair_id)
    params = params_from(cfg["defaults"])
    tau = choose_tau(params.k, cache.n_views, params.tau_factor)
    g0 = choose_gamma(tau, len(cache.explain_attrs), params.k, params.budgets()[1])
    counts = []
    for a in cache.explain_attrs:
        n = cache.hist[a][0][cache.valid[a]]
        counts.append(n[n > 0])
    c = np.concatenate(counts)
    out = {"dataset": cache.ds.name, "pair": pair_id, "N": cache.N, "nonempty_bins": int(len(c)),
           "median_nonempty_bin": float(np.median(c)), "gamma_default": g0,
           "share_bins_below_gamma_default": float(np.mean(c < g0))}
    for pc in cfg["e3"]["bin_stat_gamma_percent"]:
        out[f"share_bins_below_gamma_{pc}%N"] = float(np.mean(c < pc / 100 * cache.N))
    return out


def view_stage(pair_id: str, cfg: dict, trials: int) -> pd.DataFrame:
    d = cfg["defaults"]
    cache = pair_cache(pair_id)
    params = params_from(d)
    tau = choose_tau(params.k, cache.n_views, params.tau_factor)
    exact = exact_top_views(cache, tau)
    exact_set = set(int(x) for x in exact)
    use = cache.use
    tau_th = float(use[exact[-1]])
    rows = []
    for eps_P in cfg["e3"]["view_stage_eps_P"]:
        ov, low = [], []
        for rng in spawn_rngs(int(d["seed"]), trials, stable_key(pair_id), int(eps_P * 1e4)):
            ret, _ = select_views(cache, tau, float(eps_P), rng)
            ov.append(len(set(int(x) for x in ret) & exact_set) / tau)
            low.append(float(use[ret].min()) / tau_th if tau_th else np.nan)
        rows.append({"pair": pair_id, "eps_P": eps_P, "overlap_mean": np.mean(ov), "overlap_std": np.std(ov),
                     "lowest_use_retained_over_tau_th_mean": np.mean(low), "tau": tau})
    return pd.DataFrame(rows)


def split_sweep(pair_id: str, cfg: dict, trials: int) -> pd.DataFrame:
    d = cfg["defaults"]
    cache = pair_cache(pair_id)
    rows = []
    base = params_from(d)
    F2 = objective(cache, b2(cache, base), base.lam)
    for split in cfg["e3"]["splits"]:
        p = base.with_(split=tuple(split))
        Fs = [objective(cache, explain(cache, p, rng).selections, p.lam)
              for rng in spawn_rngs(int(d["seed"]), trials, stable_key(pair_id), stable_key(str(split)))]
        rows.append({"pair": pair_id, "split": "/".join(f"{x:.2f}" for x in split),
                     "ratio_B2_mean": np.mean(Fs) / F2, "ratio_B2_std": np.std(Fs) / F2})
    return pd.DataFrame(rows)


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False, trials: int | None = None) -> dict:
    pairs = pairs or cfg["e3"]["pairs"]
    trials = trials or (5 if quick else int(cfg["defaults"]["trials"]))
    od = out_dir("e3", base)
    m = pd.DataFrame([margins(p, cfg) for p in pairs])
    write_csv(m, od / "margins.csv")
    datasets_seen, bins = set(), []
    for p in pairs:
        ds = resolve_pair(p).dataset.name
        if ds not in datasets_seen:
            datasets_seen.add(ds)
            bins.append(bin_stats(p, cfg))
    write_csv(pd.DataFrame(bins), od / "bin_stats.csv")
    g = pd.concat([gamma_sweep(p, cfg, trials) for p in pairs], ignore_index=True)
    write_csv(g, od / "gamma_sweep.csv")
    v = pd.concat([view_stage(p, cfg, trials) for p in pairs], ignore_index=True)
    write_csv(v, od / "view_stage.csv")
    s = pd.concat([split_sweep(p, cfg, trials) for p in pairs], ignore_index=True)
    write_csv(s, od / "budget_split.csv")
    write_json(run_metadata(cfg, experiment="e3", pairs=pairs, trials=trials), od / "metadata.json")
    gm = g[g.setting == "multiplier"]
    plotting.plot_lines(gm, "value", [("ratio_B2_mean", "")], od / "gamma_multiplier", hue="pair", logx=True,
                        title="ApproxRatio vs B2 as gamma moves around Eq. (12) (eps = 1)",
                        xlabel="gamma / gamma_Eq.(12)", ylabel="ApproxRatio vs B2", ylim=(0, 1.05))
    gp = g[g.setting == "percent_of_N"]
    plotting.plot_lines(gp, "value", [("ratio_B2_mean", "")], od / "gamma_percent_N", hue="pair",
                        title="ApproxRatio vs B2 with gamma as % of N (eps = 1)", xlabel="gamma as % of N",
                        ylabel="ApproxRatio vs B2", ylim=(0, 1.05))
    plotting.plot_lines(v, "eps_P", [("overlap_mean", "")], od / "view_stage_overlap", hue="pair", logx=True,
                        title="View stage alone: overlap of retained views with exact top-tau",
                        xlabel="eps_P", ylabel="|P_hat ∩ top-tau| / tau", ylim=(0, 1.05))
    return {"margins": m, "gamma": g, "view_stage": v, "split": s, "bins": pd.DataFrame(bins)}
