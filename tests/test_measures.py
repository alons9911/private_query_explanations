import numpy as np
import pytest

from pqde.measures import coverage, representativeness, set_objective, smoothed_hd
from pqde.stats import build_cache
from pqde.views import enumerate_views


def test_hd_gamma_zero_skips_empty_bins():
    n = np.array([10, 0, 5])
    h1 = np.array([5, 0, 5])
    h2 = np.array([0, 0, 1])
    assert smoothed_hd(n, h1, h2, 0.0) == pytest.approx(5 / 10 + 4 / 5)
    assert smoothed_hd(n, h1, h2, 2.0) == pytest.approx(5 / 12 + 4 / 7)


def test_hd_one_sided_view():
    # a refinement that removes the whole view: Q2(p(D)) is empty, HD_0 = number of non-empty bins of Q1
    n = np.array([4, 6, 0])
    assert smoothed_hd(n, n, np.zeros(3), 0.0) == pytest.approx(2.0)


def test_rep_collapses_at_gamma_R_equals_N(toy):
    """Eq. (10): at gamma_R = N every summand is non-negative and Rep_N = (2m+N) / (2(m+N))."""
    q = np.ones(toy.N, dtype=bool)
    c = build_cache(toy, q, q, gamma_R=float(toy.N))
    m, N = c.m, toy.N
    assert np.allclose(c.rep, (2 * m + N) / (2 * (m + N)))
    assert (c.rep <= 0.75 + 1e-12).all()


def test_rep_ceiling_eq_5(toy):
    """Eq. (5): Rep_{gamma_R} <= 1 - gamma_R / (2(m + gamma_R)) <= (2 + alpha) / (2(1 + alpha)) at gamma_R = alpha N."""
    q = np.ones(toy.N, dtype=bool)
    for alpha in (0.01, 0.1, 0.5):
        c = build_cache(toy, q, q, gamma_R=alpha * toy.N)
        g = c.gamma_R
        assert (c.rep <= 1 - g / (2 * (c.m + g)) + 1e-12).all()
        assert (c.rep <= (2 + alpha) / (2 * (1 + alpha)) + 1e-12).all()


def test_rep_formula_direct():
    c = np.array([50, 30, 20])
    d = np.array([[10, 0, 0]])
    r = representativeness(c, d, 100, np.array([10]), 0.0)
    assert r[0] == pytest.approx(1 - 0.5 * (abs(0.5 - 1) + 0.3 + 0.2))


def test_coverage_range():
    assert coverage(np.array([5]), np.array([5]), 5)[0] == 2.0
    assert coverage(np.array([0]), np.array([0]), 5)[0] == 0.0


def test_example_7_2_set_objective():
    """Example 7.2: lambda = 1/2, k = 3; scores 9, 4 on A and 7, 6, 2 on B; the optimum is 19."""
    from itertools import combinations

    items = [("A", 9), ("A", 4), ("B", 7), ("B", 6), ("B", 2)]
    best = max(set_objective(s, lam=0.5) for s in combinations(items, 3))
    assert best == pytest.approx(19)
    assert set_objective([("A", 9), ("A", 4), ("B", 7)], lam=0.5) == pytest.approx(18)


def test_set_objective_special_cases():
    items = [("A", 3.0), ("A", 2.0), ("B", 1.0)]
    assert set_objective(items, lam=1.0) == pytest.approx(6.0)  # modular sum
    assert set_objective(items, lam=0.0) == pytest.approx(4.0)  # group maxima
    assert set_objective(items, weights=[1.0, 0.25]) == pytest.approx(3.5 + 1.0)


def test_view_enumeration_is_public(toy):
    views = enumerate_views(toy, 2)
    sizes = {a: toy.domain_size(a) for a in toy.view_attrs}
    singles = sum(sizes.values())
    pairs = sizes["a"] * sizes["b"] + sizes["a"] * sizes["c"] + sizes["b"] * sizes["c"]
    assert len(views) == singles + pairs
