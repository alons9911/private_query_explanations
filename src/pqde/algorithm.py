"""Algorithms 1 and 2 of the paper.

Algorithm 1  Private-Queries-Diff-Top-k-Explanation
    1  eps_P, eps_S, eps_H <- eps/3, eps/3, eps/3
    3  gamma_R <- alpha N (alpha = 1/100);  tau <- min(3k, |P|);  gamma <- 2 ln(tau |Attrs|) k / eps_S
    4  u_use(p) <- Use(p, Q1, Q2, D)
    5  P_hat <- OneShotTop-tau(P, u_use, eps_P, Delta = 4 / |D|)             (eps_P-DP)
    6  E_out <- Find-Top-k-Expl(D, Q1, Q2, P_hat, Attrs, k, gamma, lambda, eps_S, eps_H)

Algorithm 2  Find-Top-k-Explanations
    1  Counts <- 0; E_out <- {}; eps_i <- eps_S / k
    2  for i = 1..k:
    3      C_i <- {(p, A) in E : p in P_hat, (p, A) not in E_out}
    4      u_i(p, A) <- HD_gamma(D; p, A, Q1, Q2) * lambda^Counts[A]
    5      (p_i, A_i) <- ExpMech(C_i, u_i, eps_i, Delta = 1/(1+gamma))
    6      H^j_i <- H_{Q_j(p_i(D)), A_i}            j = 1, 2
    7      H^j_i <- H^j_i + Laplace(2k / eps_H)
    8      E_out <- E_out + {(p_i, A_i, H^1_i, H^2_i)};  Counts[A_i]++

The whole pipeline is (eps_P + eps_S + eps_H) = eps -DP (Proposition 4.2).
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field, replace

import numpy as np

from .mechanisms import exponential_mechanism, laplace_mechanism, one_shot_top_k
from .stats import GAMMA_R_ALPHA, StatsCache  # noqa: F401  (gamma_R = alpha N, Eq. (4))

USE_SENSITIVITY_CONST = 4.0  # Proposition 3.11: GS(Use) <= 4 / N at gamma_R = alpha N, alpha in [0, 1]


@dataclass
class Params:
    """Parameters of Algorithm 1 (defaults = Section 5.1)."""

    k: int = 5
    lam: float = 0.5
    epsilon: float = 1.0
    split: tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3)
    tau: int | None = None  # None -> min(tau_factor * k, |P|)  (Eq. (11))
    tau_factor: int = 3
    gamma: float | None = None  # None -> 2 ln(tau |Attrs|) k / eps_S  (Eq. (12))
    N_public: int | None = None  # public N~ <= |D| for the view-stage sensitivity (None -> |D|)
    release: str = "pair"  # "pair": noisy (H1, H2), Laplace(2k/eps_H); "diff": noisy H1-H2, Laplace(k/eps_H)
    noiseless: bool = False  # run every mechanism with eps = inf (baseline B1); constants still use eps

    def budgets(self) -> tuple[float, float, float]:
        s = float(sum(self.split))
        return tuple(self.epsilon * x / s for x in self.split)  # type: ignore[return-value]

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)


def choose_tau(k: int, n_views: int, factor: int = 3) -> int:
    """Eq. (11): tau = min(3k, |P|)."""
    return int(min(factor * k, n_views))


def choose_gamma(tau: int, n_attrs: int, k: int, eps_S: float) -> float:
    """Eq. (12): gamma = 2 ln(tau |Attrs|) k / eps_S."""
    return 2.0 * math.log(max(tau * n_attrs, 2)) * k / eps_S


@dataclass
class Explanation:
    """One released explanation (p, A, H^1, H^2) plus non-released diagnostics."""

    round: int
    view: int
    view_label: str
    attr: str
    bins: list[str]
    noisy_h1: np.ndarray
    noisy_h2: np.ndarray
    # ---- diagnostics below are exact (NOT differentially private, never released)
    exact_n: np.ndarray
    exact_h1: np.ndarray
    exact_h2: np.ndarray
    hd_gamma: float
    utility: float
    n_candidates: int

    def to_dict(self, include_exact: bool = True) -> dict:
        d = {
            "round": self.round,
            "view": self.view_label,
            "attr": self.attr,
            "bins": list(self.bins),
            "noisy_h1": np.round(self.noisy_h1, 3).tolist(),
            "noisy_h2": np.round(self.noisy_h2, 3).tolist(),
        }
        if include_exact:
            d.update({
                "exact_n": self.exact_n.astype(int).tolist(),
                "exact_h1": self.exact_h1.astype(int).tolist(),
                "exact_h2": self.exact_h2.astype(int).tolist(),
                "hd_gamma": float(self.hd_gamma),
                "utility": float(self.utility),
                "n_candidates": self.n_candidates,
            })
        return d


@dataclass
class Result:
    explanations: list[Explanation]
    retained: np.ndarray  # view indices of P_hat (in noisy-rank order)
    tau: int
    gamma: float
    gamma_R: float
    eps_P: float
    eps_S: float
    eps_H: float
    use_sensitivity: float
    timings: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)

    @property
    def selections(self) -> list[tuple[int, str]]:
        return [(e.view, e.attr) for e in self.explanations]


def select_views(cache: StatsCache, tau: int, eps_P: float, rng: np.random.Generator,
                 N_public: int | None = None) -> tuple[np.ndarray, float]:
    """Line 5 of Algorithm 1: one-shot top-tau over ``Use`` with Delta = 4 / N~ (Proposition 3.11)."""
    n_pub = cache.N if N_public is None else int(N_public)
    if n_pub > cache.N:
        raise ValueError("N_public must not exceed |D| (the bound needs N~ <= |D|)")
    delta = USE_SENSITIVITY_CONST / n_pub
    return one_shot_top_k(cache.use, tau, delta, eps_P, rng), delta


def find_top_k_explanations(cache: StatsCache, retained: np.ndarray, *, k: int, lam: float, gamma: float,
                            eps_S: float, eps_H: float, rng: np.random.Generator, release: str = "pair",
                            noiseless: bool = False) -> list[Explanation]:
    """Algorithm 2."""
    retained = np.asarray(retained, dtype=int)
    attrs = cache.explain_attrs
    hd = cache.hd_matrix(gamma, retained)  # tau x |Attrs|; NaN = A in attr(p)
    taken = np.zeros_like(hd, dtype=bool)
    counts = np.zeros(len(attrs), dtype=int)
    eps_i = eps_S / k
    eps_round_H = eps_H / k
    em_delta = 1.0 / (1.0 + gamma)
    out: list[Explanation] = []
    for i in range(k):
        util = hd * np.power(lam, counts)[None, :]
        util = np.where(taken | np.isnan(hd), np.nan, util)
        n_cand = int(np.sum(~np.isnan(util)))
        if n_cand == 0:
            break
        flat = exponential_mechanism(util.ravel(), em_delta, math.inf if noiseless else eps_i, rng)
        r, a = divmod(flat, len(attrs))
        view, attr = int(retained[r]), attrs[a]
        n, h1, h2 = cache.histograms(view, attr)
        eps_rel = math.inf if noiseless else eps_round_H
        if release == "pair":
            nh1 = laplace_mechanism(h1, 2.0, eps_rel, rng)
            nh2 = laplace_mechanism(h2, 2.0, eps_rel, rng)
        elif release == "diff":
            d = laplace_mechanism(h1 - h2, 1.0, eps_rel, rng)
            nh1, nh2 = d, np.zeros_like(d)
        else:
            raise ValueError(f"unknown release mode {release!r}")
        out.append(Explanation(
            round=i + 1, view=view, view_label=cache.view_label(view), attr=attr,
            bins=list(cache.ds.domains[attr]), noisy_h1=nh1, noisy_h2=nh2,
            exact_n=n.copy(), exact_h1=h1.copy(), exact_h2=h2.copy(),
            hd_gamma=float(hd[r, a]), utility=float(util[r, a]), n_candidates=n_cand,
        ))
        taken[r, a] = True
        counts[a] += 1
    return out


def explain(cache: StatsCache, params: Params | None = None, rng: np.random.Generator | int | None = None) -> Result:
    """Algorithm 1 (Private-Queries-Diff-Top-k-Explanation) on a prebuilt statistics cache."""
    params = params or Params()
    rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
    eps_P, eps_S, eps_H = params.budgets()
    tau = params.tau if params.tau is not None else choose_tau(params.k, cache.n_views, params.tau_factor)
    tau = int(min(tau, cache.n_views))
    gamma = params.gamma if params.gamma is not None else choose_gamma(tau, len(cache.explain_attrs), params.k, eps_S)
    t0 = time.perf_counter()
    retained, delta = select_views(cache, tau, math.inf if params.noiseless else eps_P, rng, params.N_public)
    t1 = time.perf_counter()
    expl = find_top_k_explanations(cache, retained, k=params.k, lam=params.lam, gamma=gamma, eps_S=eps_S,
                                   eps_H=eps_H, rng=rng, release=params.release, noiseless=params.noiseless)
    t2 = time.perf_counter()
    return Result(
        explanations=expl, retained=retained, tau=tau, gamma=gamma, gamma_R=cache.gamma_R,
        eps_P=eps_P, eps_S=eps_S, eps_H=eps_H, use_sensitivity=delta,
        timings={"view_stage_ms": 1e3 * (t1 - t0), "explanation_stage_ms": 1e3 * (t2 - t1),
                 "mechanism_ms": 1e3 * (t2 - t0), "cache_build_s": cache.build_seconds},
        params=asdict(params),
    )
