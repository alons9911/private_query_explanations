"""Exact statistics on the trusted server (the "cache build" of Section 5.3.2).

For a dataset ``D``, a pair of outputs ``Q1(D), Q2(D)`` (boolean masks) and the
public view collection ``P`` the cache holds, for every view ``p``:

* ``m[p] = |p(D)|``, ``s1[p] = |Q1(p(D))|``, ``s2[p] = |Q2(p(D))|``
* ``rep[p] = Rep_{gamma_R}(p, D)`` (Eq. (3)), ``cov[p]`` (Eq. (5)), ``use[p]`` (Eq. (8))

and, for every explanation attribute ``A`` not constrained by ``p``, the three
histograms ``H_{p(D),A}``, ``H_{Q1(p(D)),A}``, ``H_{Q2(p(D)),A}`` from which
``HD_gamma(p, A)`` is computed for any gamma.

Nothing here is private: it is the server's working state, and only the
mechanisms of :mod:`pqde.algorithm` release anything.  Two computation routes
are available; both produce identical numbers, so the released distribution
is the same whichever is used.

``mode="direct"``   (the route described in Section 4.2)
    One pass over ``D`` per view for ``m, s1, s2`` and the reference histograms
    of ``Rep`` (cost ``O(|P| r N)``); the explanation histograms of a view are
    materialised lazily, only for the views the algorithm actually scores
    (``O(tau a N)``).

``mode="grouped"``  (optimisation O1)
    Views that constrain the same attribute set are computed together: one
    ``bincount`` per (attribute set, attribute, population) yields the counts of
    *every* view of the set at once (cost ``O(G (r + a) N)`` for ``G`` attribute
    sets, e.g. ``G = 21`` against ``|P| = 1,048`` on Adult).

``hist="lazy"``  (with ``mode="grouped"``)
    The explanation histograms are not computed in the grouped pass but
    materialised per view on demand, as in the direct route (``O(tau a N)``).
    ``hist="eager"`` computes them for every view inside the grouped pass.

``rep="closed_form"``  (optimisation O2, only valid at gamma_R = N)
    At ``gamma_R = N`` every summand of Eq. (2) is non-negative, so
    ``Rep_N(p, D) = (2m + N) / (2(m + N))`` (Eq. (10)) for every view: the
    reference-attribute histograms are not needed for the view stage at all.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .data.encode import EncodedDataset
from .measures import coverage, representativeness, smoothed_hd, usefulness
from .views import View, enumerate_views

STATS_MODES = ("grouped", "direct")
REP_MODES = ("general", "closed_form")
HIST_MODES = ("eager", "lazy")


@dataclass
class StatsCache:
    ds: EncodedDataset
    q1: np.ndarray
    q2: np.ndarray
    views: list[View]
    explain_attrs: list[str]
    ref_attrs: list[str]
    gamma_R: float
    m: np.ndarray
    s1: np.ndarray
    s2: np.ndarray
    rep: np.ndarray
    hist: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]
    valid: dict[str, np.ndarray]
    have_hist: np.ndarray  # per view: explanation histograms materialised
    mode: str = "grouped"
    rep_mode: str = "general"
    build_seconds: float = 0.0
    lazy_seconds: float = 0.0  # time spent materialising histograms after the build (direct mode)
    info: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ derived
    @property
    def N(self) -> int:
        return self.ds.N

    @property
    def n_views(self) -> int:
        return len(self.views)

    @property
    def cov(self) -> np.ndarray:
        return coverage(self.s1, self.s2, self.N)

    @property
    def use(self) -> np.ndarray:
        return usefulness(self.rep, self.cov)

    def view_label(self, i: int) -> str:
        return self.views[i].label(self.ds)

    # ------------------------------------------------------------- histograms
    def ensure_histograms(self, rows) -> None:
        """Materialise the explanation histograms of ``rows`` (no-op when present)."""
        rows = np.atleast_1d(np.asarray(rows, dtype=int))
        missing = rows[~self.have_hist[rows]]
        if len(missing) == 0:
            return
        t0 = time.perf_counter()
        ds = self.ds
        pop = self.q1.astype(np.int64) + 2 * self.q2.astype(np.int64)  # 0 none, 1 Q1 only, 2 Q2 only, 3 both
        for r in np.unique(missing):
            v = self.views[r]
            idx = np.flatnonzero(v.mask(ds))
            pv = pop[idx]
            for a in self.explain_attrs:
                if a in v.attrs:
                    continue
                K = ds.domain_size(a)
                b = np.bincount(ds.codes[a][idx] * 4 + pv, minlength=4 * K).reshape(K, 4)
                n_, h1_, h2_ = self.hist[a]
                n_[r] = b.sum(axis=1)
                h1_[r] = b[:, 1] + b[:, 3]
                h2_[r] = b[:, 2] + b[:, 3]
            self.have_hist[r] = True
        self.lazy_seconds += time.perf_counter() - t0

    def hd(self, attr: str, gamma: float, rows: np.ndarray | None = None) -> np.ndarray:
        """HD_gamma(p, attr) for the given view rows (NaN where attr in attr(p))."""
        if rows is None:
            rows = np.arange(self.n_views)
        rows = np.asarray(rows, dtype=int)
        self.ensure_histograms(rows)
        n, h1, h2 = self.hist[attr]
        out = smoothed_hd(n[rows], h1[rows], h2[rows], gamma)
        return np.where(self.valid[attr][rows], out, np.nan)

    def hd_matrix(self, gamma: float, rows: np.ndarray | None = None) -> np.ndarray:
        """``(len(rows), |Attrs|)`` matrix of HD_gamma; NaN marks non-candidates."""
        return np.stack([self.hd(a, gamma, rows) for a in self.explain_attrs], axis=1)

    def histograms(self, view: int, attr: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self.ensure_histograms([view])
        n, h1, h2 = self.hist[attr]
        return n[view], h1[view], h2[view]

    def candidate_count(self) -> int:
        return int(sum(v.sum() for v in self.valid.values()))


def _closed_form_rep(m: np.ndarray, N: int) -> np.ndarray:
    return (2.0 * m + N) / (2.0 * (m + N))


def build_cache(
    ds: EncodedDataset,
    q1: np.ndarray,
    q2: np.ndarray,
    views: list[View] | None = None,
    *,
    gamma_R: float | None = None,
    explain_attrs: list[str] | None = None,
    ref_attrs: list[str] | None = None,
    max_atoms: int | None = None,
    mode: str = "grouped",
    rep: str = "general",
    hist: str = "eager",
) -> StatsCache:
    """Build the statistics cache (exact, non-private) for the pair ``(Q1(D), Q2(D))``.

    ``gamma_R`` defaults to ``N`` as fixed by Algorithm 1 (line 3).  ``mode`` and
    ``rep`` select the computation route (module docstring); every route returns
    the same statistics.
    """
    if mode not in STATS_MODES:
        raise ValueError(f"mode must be one of {STATS_MODES}")
    if rep not in REP_MODES:
        raise ValueError(f"rep must be one of {REP_MODES}")
    if hist not in HIST_MODES:
        raise ValueError(f"hist must be one of {HIST_MODES}")
    if mode == "direct":
        hist = "lazy"
    t0 = time.perf_counter()
    q1 = np.asarray(q1, dtype=bool)
    q2 = np.asarray(q2, dtype=bool)
    if views is None:
        views = enumerate_views(ds, max_atoms)
    explain_attrs = list(explain_attrs or ds.explain_attrs)
    ref_attrs = list(ref_attrs or ds.ref_attrs)
    N = ds.N
    gR = float(N if gamma_R is None else gamma_R)
    if rep == "closed_form" and gR != N:
        raise ValueError("the closed form of Rep (Eq. (10)) holds only at gamma_R = N")
    P = len(views)
    m = np.zeros(P)
    s1 = np.zeros(P)
    s2 = np.zeros(P)
    rep_arr = np.zeros(P)
    hist_mode = hist
    hist = {a: tuple(np.zeros((P, ds.domain_size(a))) for _ in range(3)) for a in explain_attrs}
    valid = {a: np.array([a not in v.attrs for v in views], dtype=bool) for a in explain_attrs}
    have_hist = np.zeros(P, dtype=bool)
    global_counts = {a: np.bincount(ds.codes[a], minlength=ds.domain_size(a)).astype(float) for a in ref_attrs}

    if mode == "direct":
        for i, v in enumerate(views):
            pm = v.mask(ds)
            m[i] = pm.sum()
            s1[i] = (pm & q1).sum()
            s2[i] = (pm & q2).sum()
            if rep == "general":
                terms = []
                for a in ref_attrs:
                    if a in v.attrs:
                        continue
                    d = np.bincount(ds.codes[a][pm], minlength=ds.domain_size(a)).astype(float)
                    terms.append(representativeness(global_counts[a], d[None, :], N, np.array([m[i]]), gR)[0])
                if not terms:
                    raise ValueError(f"A_R(p) is empty for {v}; need |A_R| > l")
                rep_arr[i] = float(np.mean(terms))
        if rep == "closed_form":
            rep_arr = _closed_form_rep(m, N)
        groups_n = len({v.attrs for v in views})
    else:
        groups: dict[tuple[str, ...], list[int]] = {}
        for i, v in enumerate(views):
            groups.setdefault(v.attrs, []).append(i)
        stat_attrs = list(dict.fromkeys((explain_attrs if hist_mode == "eager" else [])
                                        + (ref_attrs if rep == "general" else [])))
        codes_q1 = {a: ds.codes[a][q1] for a in stat_attrs}
        codes_q2 = {a: ds.codes[a][q2] for a in stat_attrs}
        for attrs, rows in groups.items():
            rows = np.asarray(rows)
            sizes = [ds.domain_size(a) for a in attrs]
            G = int(np.prod(sizes))
            g = np.zeros(N, dtype=np.int64)
            for a, s in zip(attrs, sizes):
                g = g * s + ds.codes[a]
            g1, g2 = g[q1], g[q2]
            cells = np.zeros(len(rows), dtype=np.int64)
            for j, (a, s) in enumerate(zip(attrs, sizes)):
                cells = cells * s + np.array([views[r].codes[j] for r in rows])
            m_g = np.bincount(g, minlength=G).astype(float)
            m[rows] = m_g[cells]
            s1[rows] = np.bincount(g1, minlength=G)[cells]
            s2[rows] = np.bincount(g2, minlength=G)[cells]
            rep_terms = []
            for a in stat_attrs:
                if a in attrs:
                    continue
                K = ds.domain_size(a)
                d = np.bincount(g * K + ds.codes[a], minlength=G * K).reshape(G, K).astype(float)
                if rep == "general" and a in global_counts:
                    rep_terms.append(representativeness(global_counts[a], d[cells], N, m_g[cells], gR))
                if hist_mode == "eager" and a in hist:
                    n_, h1_, h2_ = hist[a]
                    n_[rows] = d[cells]
                    h1_[rows] = np.bincount(g1 * K + codes_q1[a], minlength=G * K).reshape(G, K)[cells]
                    h2_[rows] = np.bincount(g2 * K + codes_q2[a], minlength=G * K).reshape(G, K)[cells]
            if rep == "general":
                if not rep_terms:
                    raise ValueError(f"A_R(p) is empty for views over {attrs}; need |A_R| > l")
                rep_arr[rows] = np.mean(rep_terms, axis=0)
        if rep == "closed_form":
            rep_arr = _closed_form_rep(m, N)
        have_hist[:] = hist_mode == "eager"
        groups_n = len(groups)

    cache = StatsCache(
        ds=ds, q1=q1, q2=q2, views=views, explain_attrs=explain_attrs, ref_attrs=ref_attrs, gamma_R=gR,
        m=m, s1=s1, s2=s2, rep=rep_arr, hist=hist, valid=valid, have_hist=have_hist, mode=mode, rep_mode=rep,
    )
    cache.build_seconds = time.perf_counter() - t0
    cache.info = {"N": N, "|P|": P, "|Q1|": int(q1.sum()), "|Q2|": int(q2.sum()), "groups": groups_n,
                  "mode": mode, "rep": rep, "hist": hist_mode}
    return cache
