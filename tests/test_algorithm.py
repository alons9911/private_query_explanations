from itertools import combinations

import numpy as np
import pytest

from pqde.algorithm import Params, choose_gamma, choose_tau, explain
from pqde.baselines import b1, b2, b3, exhaustive_best, greedy, objective
from pqde.measures import set_objective
from pqde.query import parse
from pqde.stats import build_cache


@pytest.fixture
def cache(toy):
    q1 = parse("x >= 25 AND a = 'a0'").evaluate(toy.raw)
    q2 = parse("x >= 15").evaluate(toy.raw)
    return build_cache(toy, q1, q2)


def test_constants_eq_11_12():
    assert choose_tau(5, 1052) == 15 and choose_tau(5, 7) == 7
    # Section 5.1: tau = 15, |Attrs| = 10, k = 5, eps_S = 1/3 gives gamma ~ 150
    assert choose_gamma(15, 10, 5, 1 / 3) == pytest.approx(150.3, abs=0.1)


def test_explain_invariants(cache):
    p = Params(k=4, epsilon=2.0)
    res = explain(cache, p, rng=0)
    assert len(res.explanations) == 4
    assert res.eps_P + res.eps_S + res.eps_H == pytest.approx(2.0)
    sel = res.selections
    assert len(set(sel)) == len(sel)
    for e in res.explanations:
        assert e.view in set(res.retained.tolist())
        assert e.attr not in cache.views[e.view].attrs  # Definition 3.1
        assert len(e.noisy_h1) == len(cache.ds.domains[e.attr])
    assert len(res.retained) == res.tau


def test_noiseless_run_is_greedy_on_smoothed_hd(cache):
    p = Params(k=5, epsilon=1.0)
    r = b1(cache, p)
    rows = r.retained
    assert r.selections == greedy(cache, rows, p.k, p.lam, r.gamma)
    for e in r.explanations:  # nothing perturbed
        assert np.array_equal(e.noisy_h1, e.exact_h1)


@pytest.mark.parametrize("lam", [0.0, 0.3, 0.5, 1.0])
def test_greedy_is_exact_prop_7_1(cache, lam):
    """Greedy on F_w returns the exact maximiser (Proposition 7.1) -- compare with brute force."""
    p = Params(k=3, lam=lam)
    rows = np.argsort(-cache.use)[:6]
    hd = cache.hd_matrix(0.0, rows)
    cands = [(int(rows[r]), cache.explain_attrs[a]) for r in range(len(rows)) for a in range(hd.shape[1])
             if not np.isnan(hd[r, a])]
    brute = max(objective(cache, list(s), lam) for s in combinations(cands, 3))
    assert objective(cache, greedy(cache, rows, 3, lam, 0.0), lam) == pytest.approx(brute)


def test_b2_equals_b3(cache):
    p = Params(k=4)
    assert objective(cache, b2(cache, p), p.lam) == pytest.approx(objective(cache, b3(cache, p), p.lam))


def test_exhaustive_best_matches_set_objective():
    rng = np.random.default_rng(0)
    aidx = np.repeat(np.arange(4), 4)
    scores = np.concatenate([np.sort(rng.random(4))[::-1] for _ in range(4)])
    best, best_set, total, _ = exhaustive_best(scores, aidx, 3, 0.5)
    assert total == 560
    assert best == pytest.approx(set_objective([(aidx[i], scores[i]) for i in best_set], lam=0.5))


def test_release_noise_scale(cache):
    """Pair release: Laplace(2k / eps_H) per bin (Algorithm 2, line 7)."""
    p = Params(k=2, epsilon=3.0)
    diffs = []
    for s in range(300):
        r = explain(cache, p, rng=s)
        for e in r.explanations:
            diffs.extend((e.noisy_h1 - e.exact_h1).tolist())
    b = 2 * p.k / (p.epsilon / 3)
    assert np.std(diffs) == pytest.approx(np.sqrt(2) * b, rel=0.1)


def test_diff_release(cache):
    r = explain(cache, Params(k=2, release="diff"), rng=0)
    assert all(np.all(e.noisy_h2 == 0) for e in r.explanations)
