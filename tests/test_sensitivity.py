"""Empirical checks of the sensitivity bounds of Section 3.3 and Proposition 4.1.

Neighbouring databases follow Definition 2.11 (add or remove one tuple); the
public domains and the public view collection are fixed across the pair.  The
two queries are arbitrary selections, so each tuple's membership in Q1 / Q2 is
drawn at random (every such assignment is realised by a selection on a key).
"""

import numpy as np
import pandas as pd
import pytest

from pqde.data.encode import EncodedDataset
from pqde.measures import coverage_product, interestingness_tvd, rep_unsmoothed
from pqde.stats import build_cache
from pqde.views import enumerate_views

ATTRS = {"a": 3, "b": 2, "c": 3}


def make_ds(codes: dict, ref=("a", "b", "c")) -> EncodedDataset:
    n = len(next(iter(codes.values())))
    return EncodedDataset(
        name="rand", raw=pd.DataFrame({k: v for k, v in codes.items()}),
        codes={k: np.asarray(v, dtype=np.int64) for k, v in codes.items()},
        domains={k: [f"{k}{i}" for i in range(s)] for k, s in ATTRS.items()},
        explain_attrs=list(ATTRS), ref_attrs=list(ref), view_attrs=list(ATTRS), meta={"max_view_atoms": 2},
    )


def random_instance(rng, n):
    codes = {k: rng.integers(0, s, size=n) for k, s in ATTRS.items()}
    # skew some attributes so that views have very different sizes
    if rng.random() < 0.5:
        codes["a"] = np.where(rng.random(n) < 0.8, 0, codes["a"])
    q1 = rng.random(n) < rng.uniform(0.1, 0.9)
    q2 = rng.random(n) < rng.uniform(0.1, 0.9)
    return codes, q1, q2


def neighbour(rng, codes, q1, q2):
    n = len(q1)
    if rng.random() < 0.5 and n > 2:  # remove a tuple
        keep = np.ones(n, dtype=bool)
        keep[rng.integers(n)] = False
        return {k: v[keep] for k, v in codes.items()}, q1[keep], q2[keep]
    t = {k: rng.integers(0, s) for k, s in ATTRS.items()}
    return ({k: np.append(v, t[k]) for k, v in codes.items()}, np.append(q1, rng.random() < 0.5),
            np.append(q2, rng.random() < 0.5))


@pytest.mark.parametrize("seed", range(6))
def test_use_sensitivity_prop_3_10(seed):
    """GS_N(Use) <= 7 / (4N) with gamma_R = N on both sides (Proposition 3.10)."""
    rng = np.random.default_rng(seed)
    worst = 0.0
    for _ in range(150):
        n = int(rng.integers(3, 40))
        codes, q1, q2 = random_instance(rng, n)
        ds = make_ds(codes)
        views = enumerate_views(ds, 2)
        c = build_cache(ds, q1, q2, views)
        codes2, q1b, q2b = neighbour(rng, codes, q1, q2)
        c2 = build_cache(make_ds(codes2), q1b, q2b, views)
        ratio = np.max(np.abs(c2.use - c.use)) * n
        worst = max(worst, ratio)
        assert ratio <= 7 / 4 + 1e-12
    assert worst > 0.5  # the check is not vacuous


@pytest.mark.parametrize("gamma", [0.0, 0.5, 3.0, 20.0])
def test_hd_sensitivity_prop_3_8(gamma):
    """GS(HD_gamma) = 1 / (1 + gamma) (Proposition 3.8), over every view and attribute."""
    rng = np.random.default_rng(int(gamma * 10) + 1)
    worst = 0.0
    for _ in range(150):
        n = int(rng.integers(2, 30))
        codes, q1, q2 = random_instance(rng, n)
        ds = make_ds(codes)
        views = enumerate_views(ds, 2)
        c = build_cache(ds, q1, q2, views)
        codes2, q1b, q2b = neighbour(rng, codes, q1, q2)
        c2 = build_cache(make_ds(codes2), q1b, q2b, views)
        for a in ATTRS:
            d = np.abs(np.nan_to_num(c2.hd(a, gamma)) - np.nan_to_num(c.hd(a, gamma)))
            worst = max(worst, float(d.max()))
    assert worst <= 1 / (1 + gamma) + 1e-12
    assert worst >= 0.5 / (1 + gamma)  # bound is nearly attained


def test_released_histogram_sensitivity_prop_4_1():
    rng = np.random.default_rng(3)
    for _ in range(200):
        n = int(rng.integers(2, 30))
        codes, q1, q2 = random_instance(rng, n)
        views = enumerate_views(make_ds(codes), 2)
        c = build_cache(make_ds(codes), q1, q2, views)
        codes2, q1b, q2b = neighbour(rng, codes, q1, q2)
        c2 = build_cache(make_ds(codes2), q1b, q2b, views)
        for a in ATTRS:
            _, h1, h2 = c.hist[a]
            _, g1, g2 = c2.hist[a]
            pair_l1 = np.abs(g1 - h1).sum(axis=1) + np.abs(g2 - h2).sum(axis=1)
            diff_l1 = np.abs((g1 - g2) - (h1 - h2)).sum(axis=1)
            assert pair_l1.max() <= 2 and diff_l1.max() <= 1


def test_prior_forms_do_not_decay_prop_3_9():
    # (i) distributional interestingness: one tuple moves it by 1 (half its range)
    assert interestingness_tvd([1, 0], [0, 5]) == pytest.approx(2.0)
    assert interestingness_tvd([1, 1], [0, 5]) == pytest.approx(1.0)
    # (ii) unsmoothed representativeness: change > 1/2 - 1/N at any N
    for N in (10, 100, 1000):
        c = np.array([1, N - 1])  # the view's single tuple carries v1, the rest of D carries v2
        before = rep_unsmoothed(c, np.array([1, 0]), N)
        after = rep_unsmoothed(np.array([1, N]), np.array([1, 1]), N + 1)
        assert after - before >= 0.5 - 1 / N
    # (iii) two-sided support: change 2N + 1 when the view is the whole database
    N = 50
    assert coverage_product(N + 1, N + 1) - coverage_product(N, N) == 2 * N + 1
