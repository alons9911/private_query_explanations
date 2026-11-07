"""Measures of explanation quality (Section 3.2) and the set objective (Definition 3.6).

All functions are vectorised over rows: a "row" is one view (or one candidate)
and the last axis indexes the public bins of an attribute.

* ``smoothed_hd``           -- HD_gamma, Eq. (1)
* ``representativeness``    -- Rep^A_{gamma_R}, Eq. (2) (average -> Eq. (3))
* ``coverage``              -- Cov, Eq. (5)
* ``usefulness``            -- Use = Rep * Cov, Eq. (8)
* ``diversity``             -- Div = lambda^count, Eq. (6)
* ``set_objective``         -- F_w, Eq. (7) with w_j = lambda^(j-1)

The unsmoothed forms used in prior work (Proposition 3.9) are included for the
sensitivity experiments: ``tvd``, ``interestingness_tvd``, ``rep_unsmoothed``,
``coverage_product``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Hashable, Iterable, Sequence

import numpy as np


def tvd(p1: np.ndarray, p2: np.ndarray, axis: int = -1) -> np.ndarray:
    """Total variation distance (Definition 2.10)."""
    return 0.5 * np.abs(np.asarray(p1, float) - np.asarray(p2, float)).sum(axis=axis)


def smoothed_hd(n: np.ndarray, h1: np.ndarray, h2: np.ndarray, gamma: float) -> np.ndarray:
    """Smoothed Histogram Distance HD_gamma (Definition 3.4, Eq. (1)).

    ``n`` is the histogram of the view ``H_{p(D),A}``; ``h1``/``h2`` the
    histograms of the two outputs inside the view.  For ``gamma = 0`` the sum is
    restricted to bins with ``n > 0``.
    """
    n = np.asarray(n, dtype=float)
    diff = np.abs(np.asarray(h1, float) - np.asarray(h2, float))
    if gamma > 0:
        return (diff / (n + gamma)).sum(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(n > 0, diff / np.where(n > 0, n, 1.0), 0.0)
    return terms.sum(axis=-1)


def representativeness(c: np.ndarray, d: np.ndarray, N: int, m: np.ndarray, gamma_R: float) -> np.ndarray:
    """Rep^A_{gamma_R}(p, D) = 1 - 1/2 sum_v | c_v/N - d_v/(m + gamma_R) |  (Definition 3.5, Eq. (2)).

    ``c``: counts of A over D (shape ``(b,)``); ``d``: counts inside each view
    (shape ``(rows, b)``); ``m``: view sizes (shape ``(rows,)``).
    """
    m = np.asarray(m, dtype=float)
    denom = m + gamma_R
    with np.errstate(divide="ignore", invalid="ignore"):
        view_dist = np.where(denom[:, None] > 0, np.asarray(d, float) / np.where(denom > 0, denom, 1.0)[:, None], 0.0)
    return 1.0 - 0.5 * np.abs(np.asarray(c, float)[None, :] / N - view_dist).sum(axis=-1)


def coverage(s1: np.ndarray, s2: np.ndarray, N: int) -> np.ndarray:
    """Cov(p, Q1, Q2, D) = (|Q1(p(D))| + |Q2(p(D))|) / |D|  (Eq. (5)), range [0, 2]."""
    return (np.asarray(s1, float) + np.asarray(s2, float)) / N


def usefulness(rep: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Use = Rep_{gamma_R} * Cov  (Eq. (8))."""
    return np.asarray(rep) * np.asarray(cov)


def diversity(lam: float, count: int | np.ndarray) -> np.ndarray:
    """Div(A, S) = lambda^count(A, S)  (Eq. (6)), with 0^0 = 1."""
    return np.power(float(lam), np.asarray(count, dtype=float))


def set_objective(items: Iterable[tuple[Hashable, float]], lam: float | None = None,
                  weights: Sequence[float] | None = None) -> float:
    """F_w(E) = sum_A sum_j w_j h^A_(j)  (Definition 3.6, Eq. (7)).

    ``items`` are ``(attribute, score)`` pairs of the selected candidates.  Use
    ``lam`` for the geometric weights ``w_j = lambda^(j-1)`` or pass explicit
    non-increasing ``weights`` with ``w_1 = 1``.
    """
    groups: dict[Hashable, list[float]] = defaultdict(list)
    for a, h in items:
        groups[a].append(float(h))
    total = 0.0
    for scores in groups.values():
        scores.sort(reverse=True)
        for j, h in enumerate(scores):
            if weights is not None:
                w = weights[j] if j < len(weights) else 0.0
            else:
                w = float(lam) ** j if not (lam == 0 and j == 0) else 1.0
            total += w * h
    return total


# ----------------------------------------------------------- forms used in prior work (Prop. 3.9)


def interestingness_tvd(h1: np.ndarray, h2: np.ndarray) -> float:
    """Distributional interestingness: 2 * TVD between the conditional distributions (undefined on empty)."""
    s1, s2 = np.sum(h1), np.sum(h2)
    if s1 == 0 or s2 == 0:
        return float("nan")
    return float(2 * tvd(np.asarray(h1) / s1, np.asarray(h2) / s2))


def rep_unsmoothed(c: np.ndarray, d: np.ndarray, N: int) -> float:
    """1 - TVD(view distribution, global distribution) (undefined on an empty view)."""
    m = np.sum(d)
    if m == 0:
        return float("nan")
    return float(1 - tvd(np.asarray(d) / m, np.asarray(c) / N))


def coverage_product(s1: int, s2: int) -> float:
    """Two-sided support |Q1(p(D))| * |Q2(p(D))|."""
    return float(s1) * float(s2)
