"""Every statistics route (direct / grouped, eager / lazy histograms, general / closed-form Rep)
must give the same numbers, and therefore the same released output for the same randomness."""

import itertools

import numpy as np
import pytest

from pqde.algorithm import Params, explain
from pqde.query import parse
from pqde.stats import build_cache

ROUTES = [("direct", "general", "lazy"), ("direct", "closed_form", "lazy"), ("grouped", "general", "eager"),
          ("grouped", "general", "lazy"), ("grouped", "closed_form", "eager"), ("grouped", "closed_form", "lazy")]


@pytest.fixture
def masks(toy):
    return parse("x >= 25").evaluate(toy.raw), parse("a = 'a1' OR c = 'yes'").evaluate(toy.raw)


def _gR(toy, r, gamma_R):
    # the closed form of Rep exists only at gamma_R = N
    return float(toy.N) if r == "closed_form" else gamma_R


@pytest.mark.parametrize("gamma_R", [None, "N"])
def test_routes_agree(toy, masks, gamma_R):
    gR = float(toy.N) if gamma_R == "N" else None
    routes = ROUTES if gamma_R == "N" else [x for x in ROUTES if x[1] == "general"]
    caches = [build_cache(toy, *masks, mode=m, rep=r, hist=h, gamma_R=gR) for m, r, h in routes]
    ref = caches[0]
    for c in caches[1:]:
        assert np.array_equal(c.m, ref.m) and np.array_equal(c.s1, ref.s1) and np.array_equal(c.s2, ref.s2)
        assert np.allclose(c.rep, ref.rep, rtol=0, atol=1e-12)
        for g in (0.0, 3.0, 150.0):
            assert np.allclose(c.hd_matrix(g), ref.hd_matrix(g), equal_nan=True)


def test_closed_form_requires_gamma_R_N(toy, masks):
    with pytest.raises(ValueError):
        build_cache(toy, *masks, rep="closed_form", gamma_R=10.0)


@pytest.mark.parametrize("seed", range(5))
def test_same_release_for_same_randomness(toy, masks, seed):
    outs = []
    for m, r, h in ROUTES:
        c = build_cache(toy, *masks, mode=m, rep=r, hist=h, gamma_R=float(toy.N))
        res = explain(c, Params(k=4, epsilon=2.0), rng=seed)
        outs.append((res.retained.tolist(), res.selections,
                     [np.round(e.noisy_h1, 9).tolist() for e in res.explanations]))
    assert all(o == outs[0] for o in outs[1:])


def test_lazy_materialises_only_scored_views(toy, masks):
    c = build_cache(toy, *masks, mode="grouped", rep="general", hist="lazy")
    res = explain(c, Params(k=3), rng=0)
    assert set(np.flatnonzero(c.have_hist)) == set(res.retained.tolist())


@pytest.mark.parametrize("seed", range(3))
def test_same_release_at_default_gamma_R(toy, masks, seed):
    """At gamma_R = N / 100 (Eq. (4)) the general routes still release the same output."""
    outs = []
    for m, r, h in [x for x in ROUTES if x[1] == "general"]:
        c = build_cache(toy, *masks, mode=m, rep=r, hist=h)
        assert c.gamma_R == pytest.approx(0.01 * toy.N)
        res = explain(c, Params(k=4, epsilon=2.0), rng=seed)
        outs.append((res.retained.tolist(), res.selections,
                     [np.round(e.noisy_h1, 9).tolist() for e in res.explanations]))
    assert all(o == outs[0] for o in outs[1:])
