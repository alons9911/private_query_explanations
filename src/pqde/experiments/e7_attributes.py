"""E7 -- the number of explanation attributes |Attrs| (running time and accuracy).

Only the explanation attributes vary; the views and the reference attributes stay
fixed, so |P| and the Use pass do not change.  The attributes are the dataset's
explanation attributes plus the usable ones it does not use by default
(``extra_explain_attrs`` in configs/datasets.yaml); contrast pairs keep their
group attribute excluded.

For every pair, ``e7.orders`` random orders of those attributes are drawn (seeded
by the pair); size m keeps the first m attributes of an order, so the sets are
nested within an order and the averages do not depend on which attributes happen
to be kept.  Derived constants follow their rules (gamma depends on |Attrs|).

* ``e7t`` (running time, the runtime pairs): at every m, run r uses order r, all
  methods end to end, ``e7.orders`` runs per point; a method that hits the time
  limit is run ``timeout_repeats`` times at that point and then no more.
* ``e7a`` (accuracy, every pair): one statistics build per pair with all
  attributes; at every m and every order, the baselines B1, B2, B3 on that
  attribute set and ``e7.trials_per_order`` private runs.

Raw data: ``results/e7/raw/runtime.csv`` and ``results/e7/raw/trials.csv``.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd

from ..algorithm import explain
from ..baselines import b1, b2, b3, objective
from ..data import dataset_config
from ..metrics import release_metrics, set_metrics
from ..pairs import resolve_pair
from ..runner import METHODS, time_methods
from ..stats import build_cache
from ..views import enumerate_views
from .accuracy import BASELINES, summarise
from .common import (make_params, out_dir, pairs_by_dataset, run_metadata, spawn_rngs, stable_key, stats_route,
                     write_csv, write_json, write_raw)

EXP = "e7"


def attribute_pool(pair) -> list[str]:
    ds = pair.dataset
    extra = dataset_config(ds.name).get("extra_explain_attrs", []) or []
    view_only = set()  # extra attributes are explanation attributes only
    return list(dict.fromkeys(list(ds.explain_attrs) + [a for a in extra if a not in view_only]))


def attribute_orders(pair_id: str, pool: list[str], n: int, seed: int) -> list[list[str]]:
    rng = np.random.default_rng([seed, stable_key(pair_id), 7])
    return [[pool[i] for i in rng.permutation(len(pool))] for _ in range(n)]


def sizes(pool: list[str], e: dict) -> list[int]:
    return list(range(int(e.get("min_attrs", 2)), len(pool) + 1))


# ----------------------------------------------------------------------------- running time

def run_runtime(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    d, e = cfg["defaults"], cfg[EXP]
    seed, timeout_s = int(d["seed"]), float(d["timeout_s"])
    timeout_reps = int(d.get("timeout_repeats", 3))
    n_orders = 2 if quick else int(e["orders"])
    pids = pairs or cfg.get("runtime_pairs", cfg["pairs"])
    rows = []
    for ds_name, plist in pairs_by_dataset(pids, cfg.get("datasets")).items():
        for pid in plist:
            pair = resolve_pair(pid)
            pool = attribute_pool(pair)
            orders = attribute_orders(pid, pool, n_orders, seed)
            n_views = len(enumerate_views(pair.dataset))
            print(f"  E7t {ds_name}/{pid}: {len(pool)} attributes", flush=True)
            ms = sizes(pool, e)
            for m in (ms if not quick else [ms[0], ms[-1]]):
                n_to: dict = {}
                for r, order in enumerate(orders):
                    methods = tuple(x for x in METHODS if n_to.get(x, 0) < timeout_reps)
                    if not methods:
                        break
                    ds_m = replace(pair.dataset, explain_attrs=order[:m])
                    params = make_params(d, n_views, m)
                    for out in time_methods(ds_m, pair.q1, pair.q2, params, methods=methods, seed=seed, repeat=r,
                                            gamma_eval=float(d["gamma_eval"]), timeout_s=timeout_s):
                        n_to[out.method] = n_to.get(out.method, 0) + int(out.timeout)
                        rows.append({"dataset": ds_name, "pair": pid, "sweep": "n_attrs", "value": m, "order": r,
                                     "attrs": json.dumps(order[:m]), "method": out.method, "repeat": r,
                                     "N": pair.dataset.N, "P": n_views, "k": params.k, "tau": params.tau,
                                     "gamma": params.gamma, "build_s": out.build_s, "mech_s": out.mech_s,
                                     "total_s": out.total_s, "timeout": out.timeout,
                                     "b2_subsets": out.extra.get("subsets", out.extra.get("subsets_total"))})
                print(f"    |Attrs|={m}: " + "  ".join(
                    f"{x} {np.median([w['total_s'] for w in rows if w['pair'] == pid and w['value'] == m and w['method'] == x]):.3g}s"
                    for x in METHODS), flush=True)
                write_raw(pd.DataFrame(rows), EXP, "runtime", base)
    write_json(run_metadata(cfg, experiment="e7t", orders=n_orders, timeout_s=timeout_s),
               out_dir(EXP, base) / "metadata_runtime.json")
    return {}


# ----------------------------------------------------------------------------- accuracy

def _restrict(cache, attrs: list[str]):
    """The cache seen with a subset of its explanation attributes (histograms must be materialised)."""
    c = copy.copy(cache)
    c.explain_attrs = list(attrs)
    c.hist = {a: cache.hist[a] for a in attrs}
    c.valid = {a: cache.valid[a] for a in attrs}
    return c


def _labels(cache, sel):
    return [(cache.view_label(v), a) for v, a in sel]


def accuracy_rows(pair_id: str, cfg: dict, n_orders: int, trials_per_order: int,
                  fixed_gamma: bool = False) -> list[dict]:
    """With ``fixed_gamma``, gamma stays at its Eq. (14) value for the dataset's default number of
    explanation attributes (the gamma of every other experiment) instead of following |Attrs|."""
    d, e = cfg["defaults"], cfg[EXP]
    seed, lam, ge = int(d["seed"]), float(d["lam"]), float(d.get("gamma_eval", 0.0))
    pair = resolve_pair(pair_id)
    pool = attribute_pool(pair)
    full = build_cache(replace(pair.dataset, explain_attrs=pool), pair.q1, pair.q2, **stats_route(d))
    full.ensure_histograms(np.arange(full.n_views))  # every view, so that restricted copies never build any
    over = {}
    if fixed_gamma:
        over["gamma"] = make_params(d, full.n_views, len(pair.dataset.explain_attrs)).gamma
    rows = []
    for r, order in enumerate(attribute_orders(pair_id, pool, n_orders, seed)):
        for m in sizes(pool, e):
            c = _restrict(full, order[:m])
            params = make_params(d, c.n_views, m, **over)
            ref = {"B1": b1(c, params).selections, "B2": b2(c, params, ge), "B3": b3(c, params, ge)}
            ref_F = {b: objective(c, s, lam, ge) for b, s in ref.items()}
            ref_lab = {b: _labels(c, s) for b, s in ref.items()}
            for t, rng in enumerate(spawn_rngs(seed, trials_per_order, stable_key(pair_id), r, m)):
                res = explain(c, params, rng)
                F = objective(c, res.selections, lam, ge)
                lab = _labels(c, res.selections)
                row = {"pair": pair_id, "dataset": pair.dataset.name,
                       "synthetic": bool(pair.dataset.meta.get("synthetic", False)),
                       "sweep": "n_attrs_fixed_gamma" if fixed_gamma else "n_attrs", "value": m,
                       "order": r, "trial": t, "attrs": json.dumps(order[:m]), "epsilon": params.epsilon,
                       "gamma": res.gamma, "tau": res.tau, "k": params.k, "F": F}
                for bname in BASELINES:
                    row[f"F_{bname}"] = ref_F[bname]
                    row[f"ratio_{bname}"] = F / ref_F[bname] if ref_F[bname] else np.nan
                    for mname, mval in set_metrics(lab, ref_lab[bname], params.k).items():
                        row[f"{mname}_{bname}"] = mval
                row.update(release_metrics(res.explanations))
                row["mechanism_ms"] = res.timings["mechanism_ms"]
                row["selections"] = json.dumps(lab)
                rows.append(row)
    return rows


def run_accuracy(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False,
                 fixed_gamma: bool = False) -> dict:
    e = cfg[EXP]
    n_orders = 2 if quick else int(e["orders"])
    tpo = 1 if quick else int(e["trials_per_order"])
    name = "trials_fixed_gamma" if fixed_gamma else "trials"
    rows = []
    for pid in pairs or cfg["pairs"]:
        rows += accuracy_rows(pid, cfg, n_orders, tpo, fixed_gamma=fixed_gamma)
        print(f"  E7{'g' if fixed_gamma else 'a'} {pid}: done", flush=True)
        write_raw(pd.DataFrame(rows), EXP, name, base)
    write_csv(summarise(pd.DataFrame(rows)), out_dir(EXP, base) / f"accuracy_summary{'_fixed_gamma' if fixed_gamma else ''}.csv")
    write_json(run_metadata(cfg, experiment="e7g" if fixed_gamma else "e7a", orders=n_orders, trials_per_order=tpo),
               out_dir(EXP, base) / f"metadata_accuracy{'_fixed_gamma' if fixed_gamma else ''}.json")
    return {}


def run_accuracy_fixed_gamma(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    return run_accuracy(cfg, pairs, base, quick, fixed_gamma=True)


RUNTIME = SimpleNamespace(run=run_runtime, __doc__="E7t -- running time against the number of explanation attributes.")
ACCURACY = SimpleNamespace(run=run_accuracy, __doc__="E7a -- accuracy against the number of explanation attributes.")
ACCURACY_FIXED_GAMMA = SimpleNamespace(
    run=run_accuracy_fixed_gamma,
    __doc__="E7g -- accuracy against the number of explanation attributes, gamma fixed at its default.")
