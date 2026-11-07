import math

import numpy as np
import pytest

from pqde.mechanisms import (exponential_mechanism, exponential_probabilities, laplace_mechanism,
                             one_shot_top_k)


def test_exponential_mechanism_distribution():
    rng = np.random.default_rng(0)
    u = np.array([1.0, 0.5, 0.0, np.nan, 0.8])
    p = exponential_probabilities(u, 0.5, 2.0)
    assert p[3] == 0
    draws = np.bincount([exponential_mechanism(u, 0.5, 2.0, rng) for _ in range(40000)], minlength=5) / 40000
    assert np.allclose(draws, p, atol=0.01)


def test_noiseless_limits():
    rng = np.random.default_rng(0)
    u = np.array([0.1, 0.7, 0.3, 0.9])
    assert exponential_mechanism(u, 1.0, math.inf, rng) == 3
    assert one_shot_top_k(u, 2, 1.0, math.inf, rng).tolist() == [3, 1]
    assert np.array_equal(laplace_mechanism(u, 1.0, math.inf, rng), u)


def test_one_shot_top1_equals_exponential_mechanism():
    """Top-1 with Gumbel(2 Delta / eps) is exactly the exponential mechanism (Theorem 2.17)."""
    rng = np.random.default_rng(1)
    u = np.array([1.0, 0.6, 0.2])
    p = exponential_probabilities(u, 1.0, 3.0)
    draws = np.bincount([one_shot_top_k(u, 1, 1.0, 3.0, rng)[0] for _ in range(40000)], minlength=3) / 40000
    assert np.allclose(draws, p, atol=0.01)


def test_one_shot_top_k_shape():
    rng = np.random.default_rng(2)
    u = rng.random(100)
    out = one_shot_top_k(u, 15, 0.01, 1.0, rng)
    assert len(out) == 15 and len(set(out.tolist())) == 15


def test_laplace_scale():
    rng = np.random.default_rng(3)
    x = laplace_mechanism(np.zeros(200000), 2.0, 0.5, rng)
    assert np.std(x) == pytest.approx(math.sqrt(2) * 4.0, rel=0.02)
