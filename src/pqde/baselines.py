"""Baselines B1-B3 and the evaluation metric of Section 5.1.

All baselines are scored with the set objective ``F_lambda`` of Definition 3.6
using the *unsmoothed* histogram distance (``gamma_eval = 0``).  ApproxRatio is
``F(released set) / F(baseline set)``.

B1  (eps -> inf)        The same algorithm with every mechanism noiseless while
                        tau and gamma keep the values derived from the nominal
                        eps.  The ratio to B1 is the cost of noise alone.
B2  (exhaustive)        Every size-k subset of the candidates built from the exact
                        top-tau views by Use, scored with F_lambda; enumeration is
                        restricted (losslessly) to the top-k candidates of every
                        attribute.
B3  (non-private greedy) Exact top-tau views by Use, then k greedy rounds on
                        HD_{gamma_eval} * lambda^Counts[A] (Algorithm 2 without noise).
"""

from __future__ import annotations

import math
import time
from itertools import combinations, islice

import numpy as np

from .algorithm import Params, Result, choose_tau, explain
from .measures import set_objective, smoothed_hd
from .stats import StatsCache


def objective(cache: StatsCache, selections: list[tuple[int, str]], lam: float, gamma_eval: float = 0.0) -> float:
    """F_lambda of a set of (view, attr) selections, with HD_{gamma_eval}."""
    items = []
    for view, attr in selections:
        n, h1, h2 = cache.histograms(view, attr)
        items.append((attr, float(smoothed_hd(n, h1, h2, gamma_eval))))
    return set_objective(items, lam=lam)


def approx_ratio(cache: StatsCache, released: list[tuple[int, str]], baseline: list[tuple[int, str]], lam: float,
                 gamma_eval: float = 0.0) -> float:
    den = objective(cache, baseline, lam, gamma_eval)
    num = objective(cache, released, lam, gamma_eval)
    return float("nan") if den == 0 else num / den


def exact_top_views(cache: StatsCache, tau: int) -> np.ndarray:
    """The exact (non-private) top-tau views by Use, in decreasing order."""
    use = cache.use
    tau = int(min(tau, len(use)))
    part = np.argpartition(-use, tau - 1)[:tau]
    return part[np.argsort(-use[part], kind="stable")]


def greedy(cache: StatsCache, rows: np.ndarray, k: int, lam: float, gamma: float) -> list[tuple[int, str]]:
    """k rounds of argmax of HD_gamma * lambda^Counts[A] (exact greedy on F_lambda, Prop. 7.1)."""
    rows = np.asarray(rows, dtype=int)
    hd = cache.hd_matrix(gamma, rows)
    taken = np.zeros_like(hd, dtype=bool)
    counts = np.zeros(hd.shape[1], dtype=int)
    out = []
    for _ in range(k):
        u = np.where(taken | np.isnan(hd), -np.inf, hd * np.power(lam, counts)[None, :])
        if not np.isfinite(u).any():
            break
        r, a = np.unravel_index(int(np.argmax(u)), u.shape)
        out.append((int(rows[r]), cache.explain_attrs[a]))
        taken[r, a] = True
        counts[a] += 1
    return out


def b1(cache: StatsCache, params: Params) -> Result:
    """B1: the private algorithm with the noise made negligible (constants from the nominal eps)."""
    return explain(cache, params.with_(noiseless=True), rng=0)


def b3(cache: StatsCache, params: Params, gamma_eval: float = 0.0, tau: int | None = None) -> list[tuple[int, str]]:
    tau = tau if tau is not None else (params.tau or choose_tau(params.k, cache.n_views, params.tau_factor))
    return greedy(cache, exact_top_views(cache, tau), params.k, params.lam, gamma_eval)


def b2_candidates(cache: StatsCache, params: Params, gamma_eval: float = 0.0, tau: int | None = None,
                  pool: str = "top-tau") -> tuple[list[tuple[int, str]], np.ndarray, np.ndarray]:
    """Candidate pool of B2, pruned to the top-k candidates of every attribute.

    Returns ``(candidates, scores, attr_index)`` sorted by (attribute, score desc).
    The pruning is lossless: a set that used a candidate outside the top-k of its
    attribute could swap it for an unused better one of the same attribute.
    """
    if pool == "top-tau":
        tau = tau if tau is not None else (params.tau or choose_tau(params.k, cache.n_views, params.tau_factor))
        rows = exact_top_views(cache, tau)
    elif pool == "all":
        rows = np.arange(cache.n_views)
    else:
        raise ValueError(pool)
    hd = cache.hd_matrix(gamma_eval, rows)
    cands, scores, aidx = [], [], []
    for a, attr in enumerate(cache.explain_attrs):
        col = hd[:, a]
        ok = np.flatnonzero(~np.isnan(col))
        top = ok[np.argsort(-col[ok], kind="stable")[: params.k]]
        for r in top:
            cands.append((int(rows[r]), attr))
            scores.append(float(col[r]))
            aidx.append(a)
    return cands, np.asarray(scores), np.asarray(aidx)


def exhaustive_best(scores: np.ndarray, aidx: np.ndarray, k: int, lam: float, chunk: int = 400_000
                    ) -> tuple[float, tuple[int, ...], int]:
    """Enumerate every size-k subset; candidates must be sorted by (attribute, score desc).

    Inside a subset (indices ascending) members of one attribute appear in
    decreasing score order, so the rank of a member in its group is the number
    of earlier members with the same attribute.  Returns (best F, best subset, #subsets).
    """
    n = len(scores)
    k = min(k, n)
    best, best_set, total = -math.inf, (), 0
    it = combinations(range(n), k)
    while True:
        block = list(islice(it, chunk))
        if not block:
            break
        idx = np.asarray(block, dtype=np.int32)
        total += len(idx)
        a = aidx[idx]
        rank = np.zeros_like(idx)
        for j in range(1, k):
            rank[:, j] = (a[:, :j] == a[:, j:j + 1]).sum(axis=1)
        f = (scores[idx] * np.power(lam, rank)).sum(axis=1)
        b = int(np.argmax(f))
        if f[b] > best:
            best, best_set = float(f[b]), tuple(int(x) for x in idx[b])
    return best, best_set, total


def b2(cache: StatsCache, params: Params, gamma_eval: float = 0.0, tau: int | None = None, pool: str = "top-tau",
       return_info: bool = False):
    t0 = time.perf_counter()
    cands, scores, aidx = b2_candidates(cache, params, gamma_eval, tau, pool)
    best, best_set, total = exhaustive_best(scores, aidx, params.k, params.lam)
    sel = [cands[i] for i in best_set]
    if return_info:
        return sel, {"pool_size": len(cands), "subsets": total, "F": best, "seconds": time.perf_counter() - t0}
    return sel
