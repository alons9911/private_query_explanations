import numpy as np
import pytest

from pqde.measures import representativeness, smoothed_hd
from pqde.query import parse
from pqde.stats import build_cache


def test_cache_matches_direct_computation(toy):
    q1 = parse("x >= 25").evaluate(toy.raw)
    q2 = parse("a = 'a1' OR c = 'yes'").evaluate(toy.raw)
    c = build_cache(toy, q1, q2, gamma_R=37.0)
    rng = np.random.default_rng(0)
    for i in rng.choice(c.n_views, size=25, replace=False):
        v = c.views[i]
        pm = v.mask(toy)
        assert c.m[i] == pm.sum()
        assert c.s1[i] == (pm & q1).sum() and c.s2[i] == (pm & q2).sum()
        reps = []
        for a in toy.ref_attrs:
            if a in v.attrs:
                continue
            K = toy.domain_size(a)
            cnt = np.bincount(toy.codes[a], minlength=K)
            d = np.bincount(toy.codes[a][pm], minlength=K)
            reps.append(representativeness(cnt, d[None, :], toy.N, np.array([pm.sum()]), 37.0)[0])
        assert c.rep[i] == pytest.approx(np.mean(reps))
        for a in toy.explain_attrs:
            assert c.valid[a][i] == (a not in v.attrs)
            if a in v.attrs:
                continue
            K = toy.domain_size(a)
            n = np.bincount(toy.codes[a][pm], minlength=K)
            h1 = np.bincount(toy.codes[a][pm & q1], minlength=K)
            h2 = np.bincount(toy.codes[a][pm & q2], minlength=K)
            got = c.histograms(i, a)
            assert np.array_equal(got[0], n) and np.array_equal(got[1], h1) and np.array_equal(got[2], h2)
            assert c.hd(a, 5.0, np.array([i]))[0] == pytest.approx(smoothed_hd(n, h1, h2, 5.0))


def test_view_restriction_containment(toy):
    """Proposition 2.2: Q(p(D)) subset of p(D) and of Q(D)."""
    q1 = parse("x >= 25").evaluate(toy.raw)
    c = build_cache(toy, q1, q1)
    assert (c.s1 <= c.m).all() and (c.s1 <= q1.sum()).all()
