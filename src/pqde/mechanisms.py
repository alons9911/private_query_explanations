"""Differentially private primitives (Section 2.5).

* :func:`laplace_mechanism`    -- Definition 2.14
* :func:`exponential_mechanism` -- Definition 2.15, sampled with the Gumbel-max trick
* :func:`one_shot_top_k`        -- Definition 2.16 (Durfee & Rogers), Theorem 2.17

``epsilon = math.inf`` turns every mechanism into its noiseless counterpart
(argmax / exact top-k / exact values); this is how baseline B1 is obtained.
"""

from __future__ import annotations

import math

import numpy as np


def _check(epsilon: float, sensitivity: float) -> None:
    if not (epsilon > 0):
        raise ValueError(f"epsilon must be > 0, got {epsilon}")
    if not (sensitivity > 0):
        raise ValueError(f"sensitivity must be > 0, got {sensitivity}")


def laplace_mechanism(values: np.ndarray, sensitivity: float, epsilon: float, rng: np.random.Generator) -> np.ndarray:
    """``f(D) + Laplace(sensitivity / epsilon)`` per coordinate."""
    _check(epsilon, sensitivity)
    values = np.asarray(values, dtype=float)
    if math.isinf(epsilon):
        return values.copy()
    return values + rng.laplace(0.0, sensitivity / epsilon, size=values.shape)


def laplace_scale(sensitivity: float, epsilon: float) -> float:
    return 0.0 if math.isinf(epsilon) else sensitivity / epsilon


def exponential_mechanism(utilities: np.ndarray, sensitivity: float, epsilon: float,
                          rng: np.random.Generator) -> int:
    """Index sampled with probability proportional to ``exp(eps * u / (2 * Delta))``.

    Uses the Gumbel-max trick: ``argmax(eps*u/(2 Delta) + Gumbel(0, 1))`` has
    exactly that distribution.  NaN utilities are never selected.
    """
    _check(epsilon, sensitivity)
    u = np.asarray(utilities, dtype=float)
    ok = ~np.isnan(u)
    if not ok.any():
        raise ValueError("no candidate with a defined utility")
    if math.isinf(epsilon):
        return int(np.nanargmax(np.where(ok, u, -np.inf)))
    logits = np.where(ok, epsilon * u / (2.0 * sensitivity), -np.inf)
    return int(np.argmax(logits + rng.gumbel(size=u.shape)))


def exponential_probabilities(utilities: np.ndarray, sensitivity: float, epsilon: float) -> np.ndarray:
    """Selection probabilities of the exponential mechanism (for analysis / tests)."""
    u = np.asarray(utilities, dtype=float)
    logits = np.where(np.isnan(u), -np.inf, epsilon * u / (2.0 * sensitivity))
    logits = logits - np.max(logits)
    p = np.exp(logits)
    return p / p.sum()


def one_shot_top_k(utilities: np.ndarray, k: int, sensitivity: float, epsilon: float,
                   rng: np.random.Generator) -> np.ndarray:
    """One-shot top-k: perturb every score once with ``Gumbel(2 k Delta / eps)`` and keep the k largest.

    Returns the indices of the ``k`` winners in decreasing order of noisy score.
    ``epsilon``-DP by Theorem 2.17.
    """
    _check(epsilon, sensitivity)
    u = np.asarray(utilities, dtype=float)
    k = int(min(k, np.sum(~np.isnan(u))))
    base = np.where(np.isnan(u), -np.inf, u)
    if math.isinf(epsilon):
        noisy = base
    else:
        noisy = base + rng.gumbel(0.0, 2.0 * k * sensitivity / epsilon, size=u.shape)
    if k <= 0:
        return np.zeros(0, dtype=int)
    part = np.argpartition(-noisy, k - 1)[:k]
    return part[np.argsort(-noisy[part], kind="stable")]
