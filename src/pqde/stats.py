"""One-off statistics cache for a query pair (the "cache build" of Section 5.3.2).

For a dataset ``D``, a pair of outputs ``Q1(D), Q2(D)`` (boolean masks) and the
public view collection ``P`` the cache holds, for every view ``p``:

* ``m[p]  = |p(D)|``, ``s1[p] = |Q1(p(D))|``, ``s2[p] = |Q2(p(D))|``
* ``rep[p] = Rep_{gamma_R}(p, D)`` (Eq. (3)), ``cov[p]`` (Eq. (5)), ``use[p]`` (Eq. (8))

and, for every explanation attribute ``A`` not constrained by ``p``, the three
histograms ``H_{p(D),A}``, ``H_{Q1(p(D)),A}``, ``H_{Q2(p(D)),A}``.  From these
``HD_gamma(p, A)`` is computable for *any* gamma without revisiting the data.

Views sharing an attribute set are processed together with one ``bincount``
per (attribute set, attribute, population), which is the "two passes over D"
of the complexity paragraph of Section 4.2.  This cache is *not* private: it
is the trusted server's working state.  Only the mechanisms in
:mod:`pqde.algorithm` read it and release DP outputs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .data.encode import EncodedDataset
from .measures import coverage, representativeness, smoothed_hd, usefulness
from .views import View, enumerate_views


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
    build_seconds: float = 0.0
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

    def hd(self, attr: str, gamma: float, rows: np.ndarray | None = None) -> np.ndarray:
        """HD_gamma(p, attr) for the given view rows (NaN where attr in attr(p))."""
        n, h1, h2 = self.hist[attr]
        if rows is not None:
            n, h1, h2 = n[rows], h1[rows], h2[rows]
            ok = self.valid[attr][rows]
        else:
            ok = self.valid[attr]
        out = smoothed_hd(n, h1, h2, gamma)
        return np.where(ok, out, np.nan)

    def hd_matrix(self, gamma: float, rows: np.ndarray | None = None) -> np.ndarray:
        """``(len(rows), |Attrs|)`` matrix of HD_gamma; NaN marks non-candidates."""
        return np.stack([self.hd(a, gamma, rows) for a in self.explain_attrs], axis=1)

    def histograms(self, view: int, attr: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n, h1, h2 = self.hist[attr]
        return n[view], h1[view], h2[view]

    def candidate_count(self) -> int:
        return int(sum(v.sum() for v in self.valid.values()))


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
) -> StatsCache:
    """Build the statistics cache (exact, non-private) for the pair ``(Q1(D), Q2(D))``.

    ``gamma_R`` defaults to ``N`` as fixed by Algorithm 1 (line 3).
    """
    t0 = time.perf_counter()
    q1 = np.asarray(q1, dtype=bool)
    q2 = np.asarray(q2, dtype=bool)
    if views is None:
        views = enumerate_views(ds, max_atoms)
    explain_attrs = list(explain_attrs or ds.explain_attrs)
    ref_attrs = list(ref_attrs or ds.ref_attrs)
    N = ds.N
    gR = float(N if gamma_R is None else gamma_R)
    P = len(views)

    # group views by attribute tuple
    groups: dict[tuple[str, ...], list[int]] = {}
    for i, v in enumerate(views):
        groups.setdefault(v.attrs, []).append(i)

    m = np.zeros(P)
    s1 = np.zeros(P)
    s2 = np.zeros(P)
    rep = np.zeros(P)
    stat_attrs = list(dict.fromkeys(explain_attrs + ref_attrs))
    hist = {a: tuple(np.zeros((P, ds.domain_size(a))) for _ in range(3)) for a in explain_attrs}
    valid = {a: np.zeros(P, dtype=bool) for a in explain_attrs}
    global_counts = {a: np.bincount(ds.codes[a], minlength=ds.domain_size(a)).astype(float) for a in ref_attrs}
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
            if a in global_counts:
                rep_terms.append(representativeness(global_counts[a], d[cells], N, m_g[cells], gR))
            if a in hist:
                n_, h1_, h2_ = hist[a]
                n_[rows] = d[cells]
                h1_[rows] = np.bincount(g1 * K + codes_q1[a], minlength=G * K).reshape(G, K)[cells]
                h2_[rows] = np.bincount(g2 * K + codes_q2[a], minlength=G * K).reshape(G, K)[cells]
                valid[a][rows] = True
        if not rep_terms:
            raise ValueError(f"A_R(p) is empty for views over {attrs}; need |A_R| > l")
        rep[rows] = np.mean(rep_terms, axis=0)

    cache = StatsCache(
        ds=ds, q1=q1, q2=q2, views=views, explain_attrs=explain_attrs, ref_attrs=ref_attrs, gamma_R=gR,
        m=m, s1=s1, s2=s2, rep=rep, hist=hist, valid=valid,
    )
    cache.build_seconds = time.perf_counter() - t0
    cache.info = {"N": N, "|P|": P, "|Q1|": int(q1.sum()), "|Q2|": int(q2.sum()), "groups": len(groups)}
    return cache
