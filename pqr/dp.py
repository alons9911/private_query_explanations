from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")


def laplace(scale: float, rng: random.Random) -> float:
    """
    Draw Laplace(0, scale) noise using inverse CDF.

    scale must be > 0.
    """

    if scale <= 0:
        raise ValueError("scale must be > 0")
    # U ~ Uniform(-0.5, 0.5)
    u = rng.random() - 0.5
    return -scale * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u))


def add_laplace_noise_to_counts(
    counts: dict[T, float], *, epsilon: float, sensitivity: float = 1.0, rng: random.Random
) -> dict[T, float]:
    """
    Laplace mechanism for histogram counts.
    """

    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    if sensitivity <= 0:
        raise ValueError("sensitivity must be > 0")
    scale = sensitivity / epsilon
    return {k: float(v) + laplace(scale, rng) for k, v in counts.items()}


@dataclass(frozen=True)
class ExponentialMechanismResult:
    item: object
    utility: float


def exponential_mechanism(
    candidates: Sequence[T],
    utility: Callable[[T], float],
    *,
    epsilon: float,
    sensitivity: float = 1.0,
    rng: random.Random,
) -> ExponentialMechanismResult:
    """
    Exponential mechanism:
      P(select y) ∝ exp( epsilon * u(y) / (2 * sensitivity) )

    Returns the selected item and its (non-noisy) utility value.
    """

    if not candidates:
        raise ValueError("candidates must be non-empty")
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    if sensitivity <= 0:
        raise ValueError("sensitivity must be > 0")

    us = [float(utility(c)) for c in candidates]
    # Stabilize exponentiation.
    m = max(us)
    denom = 2.0 * sensitivity
    weights = [math.exp((epsilon / denom) * (u - m)) for u in us]
    total = sum(weights)
    if not math.isfinite(total) or total <= 0:
        # Fallback: choose argmax deterministically if numerics went sideways.
        idx = max(range(len(candidates)), key=lambda i: us[i])
        return ExponentialMechanismResult(item=candidates[idx], utility=us[idx])

    r = rng.random() * total
    acc = 0.0
    for c, w, u in zip(candidates, weights, us):
        acc += w
        if acc >= r:
            return ExponentialMechanismResult(item=c, utility=u)
    return ExponentialMechanismResult(item=candidates[-1], utility=us[-1])


def one_shot_top_tau(
    items: Sequence[T],
    score: Callable[[T], float],
    *,
    tau: int,
    epsilon: float,
    sensitivity: float = 1.0,
    rng: random.Random,
) -> list[T]:
    """
    A practical “one-shot top-τ” DP primitive used by Algorithm 1.

    This is a standard approach: add Laplace noise to each score and take the
    top-τ by noisy score (a.k.a. “report noisy top-k”).

    The paper draft references a One-Shot Top-τ subroutine but does not specify
    it. This implementation is a common instantiation.
    """

    if tau <= 0:
        return []
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    if sensitivity <= 0:
        raise ValueError("sensitivity must be > 0")

    scale = sensitivity / epsilon
    scored = []
    for it in items:
        s = float(score(it))
        noisy = s + laplace(scale, rng)
        scored.append((noisy, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[: min(tau, len(scored))]]

