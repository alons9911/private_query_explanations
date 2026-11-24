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
=============  =============================================================

PRIV_EXPL, B1, B2 and B3 use the original (direct) route; only OPT_PRIV_EXPL
uses the optimised one.

Timing (:func:`time_methods`).  The four methods on the original route do the
same statistics build, so it is timed once per repeat; each method then runs
on a fresh copy of the cache (lazily materialised histograms discarded) and
pays for its own work, histograms included.  A method's end-to-end time is
``build + own work``.  OPT_PRIV_EXPL is timed separately with its own build.
Every timed run is subject to a cooperative time limit; a run that hits it is
recorded as ``timeout`` with ``total_s`` = the limit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from . import timeouts
from .algorithm import Params, explain
from .baselines import b1, b2, b3
from .data.encode import EncodedDataset
from .stats import StatsCache, build_cache
from .views import View

METHODS = ("PRIV_EXPL", "OPT_PRIV_EXPL", "B1", "B2", "B3")
ORIGINAL_ROUTE = {"mode": "direct", "rep": "general", "hist": "lazy"}
OPT_ROUTE = {"mode": "grouped", "rep": "general", "hist": "lazy"}


@dataclass
class RunOutput:
    method: str
    selections: list | None  # [(view index, attr)]; None on timeout
    build_s: float
    mech_s: float
    total_s: float
    timeout: bool = False
    extra: dict = field(default_factory=dict)


def _run_on_cache(method: str, cache: StatsCache, params: Params, rng, gamma_eval: float) -> tuple[list, dict]:
    if method in ("PRIV_EXPL", "OPT_PRIV_EXPL"):
        res = explain(cache, params, rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng))
        return res.selections, {"result": res}
    if method == "B1":
        return b1(cache, params).selections, {}
    if method == "B3":
        return b3(cache, params, gamma_eval), {}
    if method == "B2":
        sel, info = b2(cache, params, gamma_eval, return_info=True)
        return sel, {"pool": info["pool_size"], "subsets": info["subsets"]}
    raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")


def run_method(method: str, ds: EncodedDataset, q1: np.ndarray, q2: np.ndarray, params: Params, *,
               views: list[View] | None = None, rng=None, route: dict | None = None, gamma_eval: float = 0.0,
               timeout_s: float | None = None) -> RunOutput:
    """One method end to end (its own build)."""
    route = route or (OPT_ROUTE if method == "OPT_PRIV_EXPL" else ORIGINAL_ROUTE)
    t0 = time.perf_counter()
    try:
        with timeouts.deadline(timeout_s):
            cache = build_cache(ds, q1, q2, views, **route)
            t1 = time.perf_counter()
            sel, extra = _run_on_cache(method, cache, params, rng, gamma_eval)
    except timeouts.RunTimeout as exc:
        return RunOutput(method, None, float("nan"), float("nan"), float(timeout_s), True, dict(exc.info))
    t2 = time.perf_counter()
    return RunOutput(method, sel, t1 - t0, t2 - t1, t2 - t0, False, extra)


def time_methods(ds: EncodedDataset, q1: np.ndarray, q2: np.ndarray, params: Params, *, methods=METHODS,
                 views: list[View] | None = None, seed: int = 0, repeat: int = 0, gamma_eval: float = 0.0,
                 timeout_s: float | None = None, skip: set | None = None) -> list[RunOutput]:
    """Time ``methods`` end to end for one repeat (see the module docstring).

    ``skip`` lists methods known to time out at this point (recorded as timeouts
    without running).
    """
    skip = skip or set()
    out: list[RunOutput] = []
    shared = [m for m in methods if m != "OPT_PRIV_EXPL"]
    if shared:
        t0 = time.perf_counter()
        try:
            with timeouts.deadline(timeout_s):
                base = build_cache(ds, q1, q2, views, **ORIGINAL_ROUTE)
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
                    sel, extra = _run_on_cache(m, cache, params, np.random.default_rng([seed, repeat]), gamma_eval)
                own = time.perf_counter() - t1
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
