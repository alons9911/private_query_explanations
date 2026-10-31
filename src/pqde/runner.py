"""End-to-end execution of the four compared methods.

Every method starts from the same input -- the database ``D`` and the pair of
outputs ``(Q1(D), Q2(D))`` -- and ends with its selected explanation set, so a
timing of :func:`run_method` is end to end: statistics on the server
(``build``) plus the method itself (``mech``; for the direct/lazy routes this
includes materialising the histograms of the views it scores).

=========  ==============================================================
PRIV_EXPL  Algorithm 1 (private view selection, Algorithm 2, noisy release)
B1         Algorithm 1 with every mechanism noiseless, tau and gamma kept
B2         exhaustive optimum over the candidates of the exact top-tau views
B3         exact top-tau views by Use, then greedy (Algorithm 2 without noise)
=========  ==============================================================
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .algorithm import Params, explain
from .baselines import b1, b2, b3
from .data.encode import EncodedDataset
from .stats import build_cache
from .views import View

METHODS = ("PRIV_EXPL", "B1", "B2", "B3")


@dataclass
class RunOutput:
    method: str
    selections: list | None  # [(view index, attr)], None when B2 was only estimated
    build_s: float
    mech_s: float
    total_s: float
    estimated: bool = False
    extra: dict = field(default_factory=dict)


def run_method(method: str, ds: EncodedDataset, q1: np.ndarray, q2: np.ndarray, params: Params, *,
               views: list[View] | None = None, rng=None, stats: dict | None = None, gamma_eval: float = 0.0,
               b2_max_subsets: int | None = None) -> RunOutput:
    stats = stats or {}
    t0 = time.perf_counter()
    cache = build_cache(ds, q1, q2, views, mode=stats.get("mode", "grouped"), rep=stats.get("rep", "general"),
                        hist=stats.get("hist", "eager"))
    t1 = time.perf_counter()
    extra: dict = {}
    estimated = False
    if method == "PRIV_EXPL":
        res = explain(cache, params, rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng))
        sel = res.selections
        extra = {"tau": res.tau, "gamma": res.gamma}
    elif method == "B1":
        res = b1(cache, params)
        sel = res.selections
        extra = {"tau": res.tau, "gamma": res.gamma}
    elif method == "B3":
        sel = b3(cache, params, gamma_eval)
    elif method == "B2":
        sel, info = b2(cache, params, gamma_eval, return_info=True, max_subsets=b2_max_subsets)
        estimated = bool(info.get("estimated"))
        extra = {"pool": info["pool_size"], "subsets": info["subsets"]}
        if estimated:
            extra["estimated_seconds"] = info["estimated_seconds"]
    else:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")
    t2 = time.perf_counter()
    mech = t2 - t1
    if estimated:
        mech = mech + extra["estimated_seconds"]
    return RunOutput(method, sel, t1 - t0, mech, (t1 - t0) + mech, estimated, extra)
