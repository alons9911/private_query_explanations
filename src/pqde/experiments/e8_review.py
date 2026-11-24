"""E8 -- accuracy experiments requested by the review of Section 5.

Every part works on one statistics cache per pair with the histograms of every
view, so that candidates of views outside the retained top-tau can be scored.

* ``optimum``: the optimum over the candidates of *all* views (greedy on the
  unsmoothed HD, which is exact for any candidate set by Prop. greedy-exact),
  next to the optimum over the candidates of the exact top-tau views (B3).
  Their ratio is the cost of the view filter for a non-private method.
* ``competitors``: two private alternatives at every eps of E2, ``trials`` runs each.
  - ``SingleStage``: one private selection over the candidates of all views
    (Algorithm 2 without the view stage): eps_P + eps_S for the selection, gamma
    by Eq. (gamma-rule) with |P||Attrs| candidates, eps_H for the release.
  - ``Random``: k distinct candidates of all views drawn uniformly (no selection
    budget); the whole eps goes to the release.
* ``fixed_gamma``: the eps sweep of E2 with gamma fixed at its default (eps = 1)
  value, so that eps acts on the noise only.
* ``tau``: quality against tau (gamma follows tau through Eq. (gamma-rule)).
* ``lambda``: quality and diversity (distinct attributes and views per release)
  against lambda; F_lambda and both optima use the same lambda.

Every private row carries F (unsmoothed HD), the ratio to B3 at the same setting
and to the unfiltered optimum, precision@k and attribute precision against B3,
the release metrics, and the selections.  Raw data:
``results/e8/raw/{optimum,competitors,fixed_gamma,tau,lambda}.csv``.
"""

from __future__ import annotations

import json
import math
import zlib
from types import SimpleNamespace

import numpy as np
import pandas as pd

from ..algorithm import choose_gamma, explain, find_top_k_explanations
from ..baselines import b1, b3, greedy, objective
from ..metrics import release_metrics, set_metrics
from ..mechanisms import laplace_mechanism
from ..pairs import resolve_pair
from .common import default_cache, make_params, out_dir, run_metadata, spawn_rngs, stable_key, write_json, write_raw

EXP = "e8"
PARTS = ("competitors", "fixed_gamma", "tau", "lambda")


def _labels(cache, sel):
    return [(cache.view_label(v), a) for v, a in sel]


def _full_cache(pair_id: str, d: dict):
    cache = default_cache(pair_id, d)
    cache.ensure_histograms(np.arange(cache.n_views))
    return cache


def optimum_all(cache, k: int, lam: float, ge: float) -> list[tuple[int, str]]:
    """The optimum of F_lambda over the candidates of every view (exact greedy, Prop. greedy-exact)."""
    return greedy(cache, np.arange(cache.n_views), k, lam, ge)


def _release(cache, sel, eps_H: float, k: int, rng) -> list:
    """Release the pair of histograms of each selected candidate as Algorithm 2 does (Laplace 2k/eps_H)."""
    out = []
    for v, a in sel:
        n, h1, h2 = cache.histograms(v, a)
        out.append(SimpleNamespace(view=v, attr=a, exact_h1=h1, exact_h2=h2,
                                   noisy_h1=laplace_mechanism(h1, 2.0, eps_H / k, rng),
                                   noisy_h2=laplace_mechanism(h2, 2.0, eps_H / k, rng)))
    return out


def _random_selection(cache, k: int, rng) -> list[tuple[int, str]]:
    valid = ~np.isnan(cache.hd_matrix(0.0, np.arange(cache.n_views)))
    flat = np.flatnonzero(valid.ravel())
    pick = rng.choice(flat, size=min(k, len(flat)), replace=False)
    na = len(cache.explain_attrs)
    return [(int(f // na), cache.explain_attrs[int(f % na)]) for f in pick]


def _row(cache, sel, expl, k: int, lam: float, ge: float, ref: dict, extra: dict) -> dict:
    F = objective(cache, sel, lam, ge)
    lab = _labels(cache, sel)
    row = {**extra, "F": F}
    for name, (refsel, refF) in ref.items():
        row[f"F_{name}"] = refF
        row[f"ratio_{name}"] = F / refF if refF else np.nan
    m = set_metrics(lab, _labels(cache, ref["B3"][0]), k)
    row["precision_at_k_B3"] = m["precision_at_k"]
    row["attr_precision_B3"] = m["attr_precision"]
    row["distinct_attrs"] = len({a for _, a in sel})
    row["distinct_views"] = len({v for v, _ in sel})
    row.update(release_metrics(expl))
    row["selections"] = json.dumps(lab)
    return row


def run_pair(pair_id: str, cfg: dict, trials: int, parts=PARTS) -> dict[str, list[dict]]:
    d, e = cfg["defaults"], cfg[EXP]
    seed, lam0, ge = int(d["seed"]), float(d["lam"]), float(d.get("gamma_eval", 0.0))
    pair = resolve_pair(pair_id)
    cache = _full_cache(pair_id, d)
    nv, na = cache.n_views, len(cache.explain_attrs)
    base = make_params(d, nv, na)
    k = base.k
    meta = {"pair": pair_id, "dataset": pair.dataset.name, "P": nv, "n_attrs": na}
    out: dict[str, list[dict]] = {p: [] for p in ("optimum", *parts)}

    def optima(lam: float, tau: int):
        s3 = b3(cache, base.with_(lam=lam), ge, tau=tau)
        sa = optimum_all(cache, k, lam, ge)
        return {"B3": (s3, objective(cache, s3, lam, ge)), "OptAll": (sa, objective(cache, sa, lam, ge))}

    ref0 = optima(lam0, base.tau)
    out["optimum"].append({**meta, "k": k, "lam": lam0, "tau": base.tau, "F_B3": ref0["B3"][1],
                           "F_OptAll": ref0["OptAll"][1],
                           "B3": json.dumps(_labels(cache, ref0["B3"][0])),
                           "OptAll": json.dumps(_labels(cache, ref0["OptAll"][0])),
                           "OptAll_views_in_top_tau": int(sum(v in set(cache_top(cache, base.tau))
                                                              for v, _ in ref0["OptAll"][0]))})

    def rngs(tag: str):
        return spawn_rngs(seed, trials, stable_key(pair_id), zlib.crc32(f"e8:{tag}".encode()))  # whole tag

    if "competitors" in parts:
        n_all = int(np.sum(~np.isnan(cache.hd_matrix(0.0, np.arange(nv)))))
        for eps in [float(x) for x in cfg["e2"]["epsilons"]]:
            p = make_params(d, nv, na, epsilon=eps)
            eps_P, eps_S, eps_H = p.budgets()
            g1 = 2.0 * math.log(max(nv * na, 2)) * k / (eps_P + eps_S)
            for t, rng in enumerate(rngs(f"single:{eps}")):
                expl = find_top_k_explanations(cache, np.arange(nv), k=k, lam=lam0, gamma=g1, eps_S=eps_P + eps_S,
                                               eps_H=eps_H, rng=rng)
                sel = [(x.view, x.attr) for x in expl]
                out["competitors"].append(_row(cache, sel, expl, k, lam0, ge, ref0,
                                               {**meta, "method": "SingleStage", "epsilon": eps, "trial": t,
                                                "gamma": g1, "candidates": n_all}))
            for t, rng in enumerate(rngs(f"random:{eps}")):
                sel = _random_selection(cache, k, rng)
                expl = _release(cache, sel, eps, k, rng)
                out["competitors"].append(_row(cache, sel, expl, k, lam0, ge, ref0,
                                               {**meta, "method": "Random", "epsilon": eps, "trial": t,
                                                "gamma": np.nan, "candidates": n_all}))

    if "fixed_gamma" in parts:
        g0 = base.gamma
        for eps in [float(x) for x in cfg["e2"]["epsilons"]]:
            p = make_params(d, nv, na, epsilon=eps, gamma=g0)
            r1 = b1(cache, p).selections
            ref = {**ref0, "B1": (r1, objective(cache, r1, lam0, ge))}
            for t, rng in enumerate(rngs(f"fixed_gamma:{eps}")):
                res = explain(cache, p, rng)
                out["fixed_gamma"].append(_row(cache, res.selections, res.explanations, k, lam0, ge, ref,
                                               {**meta, "epsilon": eps, "trial": t, "gamma": res.gamma,
                                                "tau": res.tau}))

    if "tau" in parts:
        taus = []
        for x in e["taus"]:
            v = nv if x == "all" else int(min(int(x), nv))
            if v not in taus:
                taus.append(v)
        for tau in taus:
            p = make_params(d, nv, na, tau=tau)
            ref = optima(lam0, tau)
            r1 = b1(cache, p).selections
            ref["B1"] = (r1, objective(cache, r1, lam0, ge))
            for t, rng in enumerate(rngs(f"tau:{tau}")):
                res = explain(cache, p, rng)
                out["tau"].append(_row(cache, res.selections, res.explanations, k, lam0, ge, ref,
                                       {**meta, "tau": tau, "tau_is_all": tau == nv, "trial": t,
                                        "gamma": res.gamma}))

    if "lambda" in parts:
        for lam in [float(x) for x in e["lambdas"]]:
            p = make_params(d, nv, na, lam=lam)
            ref = optima(lam, base.tau)
            r1 = b1(cache, p).selections
            ref["B1"] = (r1, objective(cache, r1, lam, ge))
            div = {f"{b}_distinct_attrs": len({a for _, a in s}) for b, (s, _) in ref.items()}
            for t, rng in enumerate(rngs(f"lambda:{lam}")):
                res = explain(cache, p, rng)
                out["lambda"].append(_row(cache, res.selections, res.explanations, k, lam, ge, ref,
                                          {**meta, "lam": lam, "trial": t, "gamma": res.gamma, **div}))
    return out


def cache_top(cache, tau: int) -> np.ndarray:
    from ..baselines import exact_top_views

    return exact_top_views(cache, tau)


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False, trials: int | None = None) -> dict:
    trials = trials or (2 if quick else int(cfg["defaults"]["trials"]))
    parts = tuple(cfg[EXP].get("parts", PARTS))
    acc: dict[str, list[dict]] = {}
    for pid in pairs or cfg["pairs"]:
        res = run_pair(pid, cfg, trials, parts)
        for name, rows in res.items():
            acc.setdefault(name, []).extend(rows)
            write_raw(pd.DataFrame(acc[name]), EXP, name, base)
        o = res["optimum"][0]
        comp = pd.DataFrame(res.get("competitors", []))
        msg = f"  E8 {pid}: F(B3)/F(OptAll) {o['F_B3'] / o['F_OptAll']:.3f}"
        if len(comp):
            c1 = comp[np.isclose(comp.epsilon, 1.0)].groupby("method").ratio_B3.mean()
            msg += "  eps=1 ratio_B3 " + " ".join(f"{m} {v:.2f}" for m, v in c1.items())
        print(msg, flush=True)
    write_json(run_metadata(cfg, experiment=EXP, pairs=pairs or cfg["pairs"], trials=trials, parts=list(parts)),
               out_dir(EXP, base) / "metadata.json")
    return {}
