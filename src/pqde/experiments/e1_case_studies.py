"""E1 -- case studies (Section 5.2).

For every pair: what the two queries already say (sizes, constraint shares,
how Q' / Q_Sigma was obtained), the view stage (exact top-tau by Use, the
privately retained views and their exact ranks), and the released
explanations of one eps = 1, k = 5 run, with the exact (non-private)
histograms next to the noisy ones so that statements in the text can be
checked against both.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import explain
from ..baselines import exact_top_views
from ..pairs import pair_cache, resolve_pair
from .common import out_dir, params_from, run_metadata, stable_key, write_csv, write_json


def _view_ranking(cache) -> pd.DataFrame:
    use = cache.use
    order = np.argsort(-use, kind="stable")
    rank = np.empty_like(order)
    rank[order] = np.arange(1, len(order) + 1)
    return pd.DataFrame({
        "rank": rank, "view": [cache.view_label(i) for i in range(cache.n_views)], "use": use,
        "coverage": cache.cov, "representativeness": cache.rep, "|p(D)|": cache.m.astype(int),
        "|Q1(p(D))|": cache.s1.astype(int), "|Q2(p(D))|": cache.s2.astype(int),
    }).sort_values("rank")


def _query_attr_views(pair, ranking: pd.DataFrame) -> list[dict]:
    """Ranks of the single-atom views on attributes mentioned by Q1/Q2."""
    from ..query import parse

    attrs = set()
    for sql in (pair.q1_sql, pair.q2_sql):
        if not sql.startswith("Q_Sigma("):
            attrs |= parse(sql).attributes()
    rows = []
    for _, r in ranking.iterrows():
        v = r["view"]
        if " AND " in v:
            continue
        if any(v.startswith(a + "=") or v.startswith(a + " IN") for a in attrs):
            rows.append({"view": v, "rank": int(r["rank"]), "use": float(r["use"]),
                         "coverage": float(r["coverage"]), "representativeness": float(r["representativeness"])})
    return rows


def run_pair(pair_id: str, cfg: dict, base=None, subdir: str = "e1") -> dict:
    d = cfg["defaults"]
    params = params_from(d)
    pair = resolve_pair(pair_id)
    cache = pair_cache(pair_id)
    res = explain(cache, params, rng=np.random.default_rng([cfg["e1"].get("run_seed", 7), stable_key(pair_id)]))
    ranking = _view_ranking(cache)
    rank_series = pd.Series(ranking["rank"].to_numpy(), index=ranking.index)
    exact_top = exact_top_views(cache, res.tau)
    retained = [int(v) for v in res.retained]
    atom_counts = Counter(a for v in retained for a in cache.view_label(v).split(" AND "))
    k = params.k
    b = 2 * k / res.eps_H  # Laplace scale per bin
    sigma_diff = 2 * b  # std of the difference of two independent Laplace(b): sqrt(2 * 2 b^2)
    expl = [e.to_dict() for e in res.explanations]
    for e in expl:
        nd = np.asarray(e["noisy_h1"]) - np.asarray(e["noisy_h2"])
        ed = np.asarray(e["exact_h1"]) - np.asarray(e["exact_h2"])
        e["bins_clearing_2sigma"] = [bn for bn, x in zip(e["bins"], nd) if abs(x) >= 2 * sigma_diff]
        e["exact_share_q1"] = (np.asarray(e["exact_h1"]) / max(1, sum(e["exact_h1"]))).round(4).tolist()
        e["exact_share_q2"] = (np.asarray(e["exact_h2"]) / max(1, sum(e["exact_h2"]))).round(4).tolist()
        e["noisy_total_q1"], e["noisy_total_q2"] = float(np.sum(e["noisy_h1"])), float(np.sum(e["noisy_h2"]))
        e["exact_total_q1"], e["exact_total_q2"] = int(np.sum(e["exact_h1"])), int(np.sum(e["exact_h2"]))
        e["exact_abs_diff_total"] = int(np.abs(ed).sum())
    report = {
        "pair": pair.summary(),
        "parameters": {"k": k, "lambda": params.lam, "epsilon": params.epsilon, "eps_P": res.eps_P,
                       "eps_S": res.eps_S, "eps_H": res.eps_H, "tau": res.tau, "gamma": res.gamma,
                       "gamma_R": res.gamma_R, "|P|": cache.n_views, "|Attrs|": len(cache.explain_attrs),
                       "Delta_Use": res.use_sensitivity, "laplace_scale_per_bin": b,
                       "sigma_of_released_difference": sigma_diff},
        "view_stage": {
            "exact_top_tau": [{"rank": i + 1, "view": cache.view_label(v), "use": float(cache.use[v]),
                               "coverage": float(cache.cov[v]), "representativeness": float(cache.rep[v])}
                              for i, v in enumerate(exact_top)],
            "retained": [{"noisy_rank": i + 1, "view": cache.view_label(v), "exact_rank": int(rank_series[v]),
                          "use": float(cache.use[v]), "coverage": float(cache.cov[v]),
                          "representativeness": float(cache.rep[v])} for i, v in enumerate(retained)],
            "overlap_with_exact_top_tau": len(set(retained) & set(int(x) for x in exact_top)) / max(1, res.tau),
            "retained_atom_counts": dict(atom_counts.most_common()),
            "query_attribute_views": _query_attr_views(pair, ranking),
        },
        "explanations": expl,
        "timings": res.timings,
        "note": "exact_* fields are NOT differentially private; they are reported only to check the text.",
    }
    od = out_dir(f"{subdir}/{pair_id}", base)
    write_json(report, od / "report.json")
    write_csv(ranking, od / "views_by_use.csv")
    syn = " [SYNTHETIC DATA]" if pair.dataset.meta.get("synthetic") else ""
    title = (f"{pair_id} ({pair.dataset.name}{syn}): released DP explanations "
             f"(eps = {params.epsilon:g}, k = {k}; paired release)")
    q2n = "Q_Sigma" if pair.kind == "cqa" else ("Q2" if pair.kind == "contrast" else "Q'")
    q1n = "Q1" if pair.kind == "contrast" else "Q"
    plotting.plot_explanations(expl, title, od / "explanations", q1_name=q1n, q2_name=q2n)
    if expl:
        plotting.plot_release_leaves(expl[0], sigma_diff, od / "release_leaves",
                                     f"{pair_id}: first explanation, per-bin |H1 - H2| of the release")
    return report


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    pairs = pairs or cfg["e1"]["pairs"]
    summary = []
    for pid in pairs:
        rep = run_pair(pid, cfg, base)
        p = rep["pair"]
        summary.append({
            "pair": pid, "dataset": p["dataset"], "synthetic": p["synthetic_data"], "Q1": p["Q1"], "Q2": p["Q2"],
            "|Q1|": p["|Q1|"], "|Q2|": p["|Q2|"], "tau": rep["parameters"]["tau"],
            "gamma": round(rep["parameters"]["gamma"], 2), "|P|": rep["parameters"]["|P|"],
            "view_overlap": rep["view_stage"]["overlap_with_exact_top_tau"],
            "explanations": " | ".join(f"{e['view']} :: {e['attr']}" for e in rep["explanations"]),
        })
    df = pd.DataFrame(summary)
    od = out_dir("e1", base)
    write_csv(df, od / "summary.csv")
    write_json(run_metadata(cfg, experiment="e1", pairs=pairs), od / "metadata.json")
    return {"summary": df}
