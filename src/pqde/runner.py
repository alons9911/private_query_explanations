"""End-to-end execution and timing of the compared methods.

Every method starts from the same input -- the database ``D`` and the pair of
outputs ``(Q1(D), Q2(D))`` -- and ends with its selected explanation set.

=============  =============================================================
PRIV_EXPL      Algorithm 1, statistics by the direct route of Section 4.2
OPT_PRIV_EXPL  the same algorithm with optimisations O1 (grouped pass) and O3
               (lazy histograms, one combined pass); identical output
B1             Algorithm 1 with every mechanism noiseless, tau and gamma kept
B2             exhaustive optimum over the candidates of the exact top-tau views
B3             exact top-tau views by Use, then greedy (Algorithm 2 without noise)
OPT            greedy over the candidates of every view (exact optimum, no view stage)
SINGLE_STAGE   one private selection over the candidates of every view (no view stage)
EXH_ALL        exhaustive optimum over the candidates of every view, top-k-per-attribute pruning
EXH_NAIVE      exhaustive optimum over the candidates of every view, no pruning
=============  =============================================================

PRIV_EXPL, B1, B2 and B3 use the original (direct) route; only OPT_PRIV_EXPL
uses the optimised one.  The four methods without a view stage use the direct
route without view statistics (``rep="none"``): they do not compute Use, and
materialise the explanation histograms of every view themselves.

Timing (:func:`time_methods`).  The four methods on the original route do the
same statistics build, so it is timed once per repeat; each method then runs
on a fresh copy of the cache (lazily materialised histograms discarded) and
pays for its own work, histograms included.  A method's end-to-end time is
``build + own work``.  The methods without a view stage share their own build
in the same way.  OPT_PRIV_EXPL is timed separately with its own build.
EXH_NAIVE runs its enumeration only when the rate of its first block says it
fits in the remaining time; otherwise it is recorded as a timeout whose time is
extrapolated (``extra["estimated"]``, ``extra["estimated_seconds"]``).  With
``early_stop = f`` (preview runs only; off by default) B2 and EXH_ALL do the same
when their first block says the enumeration would take more than f times the
remaining time; between 1x and fx they run until the limit as usual.
Every timed run is subject to a cooperative time limit; a run that hits it is
recorded as ``timeout`` with ``total_s`` = the limit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from . import timeouts
from .algorithm import Params, explain
from .baselines import b1, b2, b3, exhaustive_naive, opt_all, single_stage
from .data.encode import EncodedDataset
from .stats import StatsCache, build_cache
from .views import View

METHODS = ("PRIV_EXPL", "OPT_PRIV_EXPL", "B1", "B2", "B3", "OPT", "SINGLE_STAGE", "EXH_ALL", "EXH_NAIVE")
NO_VIEW_STAGE = ("OPT", "SINGLE_STAGE", "EXH_ALL", "EXH_NAIVE")
ORIGINAL_ROUTE = {"mode": "direct", "rep": "general", "hist": "lazy"}
OPT_ROUTE = {"mode": "grouped", "rep": "general", "hist": "lazy"}
NO_VIEW_ROUTE = {"mode": "direct", "rep": "none", "hist": "lazy"}


def runtime_methods(naive: bool) -> tuple[str, ...]:
    """The methods of a running-time point; EXH_NAIVE only where ``naive`` (the k sweep, the default point)."""
    return tuple(m for m in METHODS if naive or m != "EXH_NAIVE")


@dataclass
class RunOutput:
    method: str
    selections: list | None  # [(view index, attr)]; None on timeout
    build_s: float
    mech_s: float
    total_s: float
    timeout: bool = False
    extra: dict = field(default_factory=dict)


def _run_on_cache(method: str, cache: StatsCache, params: Params, rng, gamma_eval: float,
                  time_budget: float | None = None, early_stop: float | None = None) -> tuple[list, dict]:
    stop = None if early_stop is None or time_budget is None else float(early_stop) * time_budget
    if method == "OPT":
        return opt_all(cache, params, gamma_eval), {}
    if method == "SINGLE_STAGE":
        rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        return [(x.view, x.attr) for x in single_stage(cache, params, rng)], {}
    if method == "EXH_ALL":
        sel, info = b2(cache, params, gamma_eval, pool="all", return_info=True, time_budget=stop)
        return sel, {"pool": info["pool_size"], "subsets": info["subsets"], "estimated": info["estimated"],
                     "estimated_seconds": info.get("estimated_seconds")}
    if method == "EXH_NAIVE":
        sel, info = exhaustive_naive(cache, params, gamma_eval, time_budget)
        return sel, {"pool": info["pool_size"], "subsets": info["subsets"], "estimated": info["estimated"],
                     "estimated_seconds": info.get("estimated_seconds")}
    if method in ("PRIV_EXPL", "OPT_PRIV_EXPL"):
        res = explain(cache, params, rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng))
        return res.selections, {"result": res}
    if method == "B1":
        return b1(cache, params).selections, {}
    if method == "B3":
        return b3(cache, params, gamma_eval), {}
    if method == "B2":
        sel, info = b2(cache, params, gamma_eval, return_info=True, time_budget=stop)
        return sel, {"pool": info["pool_size"], "subsets": info["subsets"], "estimated": info["estimated"],
                     "estimated_seconds": info.get("estimated_seconds")}
    raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")


def run_method(method: str, ds: EncodedDataset, q1: np.ndarray, q2: np.ndarray, params: Params, *,
               views: list[View] | None = None, rng=None, route: dict | None = None, gamma_eval: float = 0.0,
               timeout_s: float | None = None, early_stop: float | None = None) -> RunOutput:
    """One method end to end (its own build)."""
    route = route or (OPT_ROUTE if method == "OPT_PRIV_EXPL" else NO_VIEW_ROUTE if method in NO_VIEW_STAGE
                      else ORIGINAL_ROUTE)
    t0 = time.perf_counter()
    try:
        with timeouts.deadline(timeout_s):
            cache = build_cache(ds, q1, q2, views, **route)
            t1 = time.perf_counter()
            budget = None if timeout_s is None else max(timeout_s - (t1 - t0), 0.0)
            sel, extra = _run_on_cache(method, cache, params, rng, gamma_eval, budget, early_stop)
    except timeouts.RunTimeout as exc:
        return RunOutput(method, None, float("nan"), float("nan"), float(timeout_s), True, dict(exc.info))
    t2 = time.perf_counter()
    if extra.get("estimated"):
        return RunOutput(method, None, t1 - t0, t2 - t1, float(timeout_s), True, extra)
    return RunOutput(method, sel, t1 - t0, t2 - t1, t2 - t0, False, extra)


def time_methods(ds: EncodedDataset, q1: np.ndarray, q2: np.ndarray, params: Params, *, methods=METHODS,
                 views: list[View] | None = None, seed: int = 0, repeat: int = 0, gamma_eval: float = 0.0,
                 timeout_s: float | None = None, skip: set | None = None,
                 early_stop: float | None = None) -> list[RunOutput]:
    """Time ``methods`` end to end for one repeat (see the module docstring).

    ``skip`` lists methods known to time out at this point (recorded as timeouts
    without running).
    """
    skip = skip or set()
    out: list[RunOutput] = []
    groups = ((ORIGINAL_ROUTE, [m for m in methods if m not in NO_VIEW_STAGE and m != "OPT_PRIV_EXPL"]),
              (NO_VIEW_ROUTE, [m for m in methods if m in NO_VIEW_STAGE]))
    for route, shared in groups:
        if not shared:
            continue
        t0 = time.perf_counter()
        try:
            with timeouts.deadline(timeout_s):
                base = build_cache(ds, q1, q2, views, **route)
            build = time.perf_counter() - t0
        except timeouts.RunTimeout:
            base, build = None, None
        for m in shared:
            if base is None or m in skip:
                out.append(RunOutput(m, None, build if build is not None else float("nan"), float("nan"),
                                     float(timeout_s), True, {"skipped": m in skip}))
                continue
            cache = base.fresh_copy()
            remaining = None if timeout_s is None else max(timeout_s - build, 0.0)
            t1 = time.perf_counter()
            try:
                with timeouts.deadline(remaining):
                    sel, extra = _run_on_cache(m, cache, params, np.random.default_rng([seed, repeat]), gamma_eval,
                                               remaining, early_stop)
                own = time.perf_counter() - t1
                if extra.get("estimated"):  # would not fit in the time limit (extrapolated, not run)
                    out.append(RunOutput(m, None, build, own, float(timeout_s), True, extra))
                else:
                    out.append(RunOutput(m, sel, build, own, build + own, False, extra))
            except timeouts.RunTimeout as exc:
                out.append(RunOutput(m, None, build, float("nan"), float(timeout_s), True, dict(exc.info)))
    if "OPT_PRIV_EXPL" in methods:
        if "OPT_PRIV_EXPL" in skip:
            out.append(RunOutput("OPT_PRIV_EXPL", None, float("nan"), float("nan"), float(timeout_s), True,
                                 {"skipped": True}))
        else:
            out.append(run_method("OPT_PRIV_EXPL", ds, q1, q2, params, views=views,
                                  rng=np.random.default_rng([seed, repeat]), gamma_eval=gamma_eval,
                                  timeout_s=timeout_s))
    return out
