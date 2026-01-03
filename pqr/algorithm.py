from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from .dp import add_laplace_noise_to_counts, exponential_mechanism, one_shot_top_tau
from .query import Condition, Op, Query, active_domain


def histogram(rows: Sequence[Mapping[str, Any]], attr: str, buckets: Sequence[Any]) -> dict[Any, float]:
    """
    Deterministic histogram over an explicit bucket set.
    """

    h = {b: 0.0 for b in buckets}
    for r in rows:
        v = r.get(attr)
        if v in h:
            h[v] += 1.0
    return h


def histogram_distance_hd(
    *,
    dataset: Sequence[Mapping[str, Any]],
    view: Query,
    attr: str,
    q1: Query,
    q2: Query,
) -> float:
    """
    Definition 4.1 (Histogram Distance, HD) from the PDF text extraction.

    HD = Σ_{V in buckets(D[A])} | H_{Q1(p(D)),A}(V) - H_{Q2(p(D)),A}(V) | / H_{p(D),A}(V)

    The PDF’s text extraction loses some formatting (notably absolute-value bars),
    so we implement the intended absolute difference. Division-by-zero buckets are
    skipped (equivalently contribute 0).
    """

    view_rows = view(dataset)
    buckets = active_domain(view_rows, attr)
    if not buckets:
        return 0.0

    h_view = histogram(view_rows, attr, buckets)
    h1 = histogram(q1(view_rows), attr, buckets)
    h2 = histogram(q2(view_rows), attr, buckets)

    total = 0.0
    for b in buckets:
        denom = h_view[b]
        if denom <= 0:
            continue
        total += abs(h1[b] - h2[b]) / denom
    return float(total)


def coverage_index(
    *,
    dataset: Sequence[Mapping[str, Any]],
    view: Query,
    q1: Query,
    q2: Query,
) -> float:
    """
    Definition 4.4’s coverage index (Equation (6) in the PDF text):

      Coverage(p, Q1, Q2, D) = ( |Q1(p(D))| + |Q2(p(D))| ) / |D|
    """

    n = len(dataset)
    if n == 0:
        return 0.0
    view_rows = view(dataset)
    return (len(q1(view_rows)) + len(q2(view_rows))) / float(n)


def diversity_score_unique_attribute(attr: str, chosen_attrs: set[str]) -> float:
    """
    Algorithm 2 multiplies HD by a diversity term.

    The draft text references more elaborate diversity/similarity penalties, but
    the fully specified formula is not present in the PDF. This default enforces
    attribute diversity (don’t pick the same attribute twice).
    """

    return 0.0 if attr in chosen_attrs else 1.0


@dataclass(frozen=True)
class Candidate:
    view: Query
    attribute: str
    # Deterministic histograms; noise is added only to the selected outputs.
    h_q1: dict[Any, float]
    h_q2: dict[Any, float]


def generate_simple_predicate_views(
    dataset: Sequence[Mapping[str, Any]],
    predicate_attrs: Sequence[str],
    *,
    max_values_per_attr: int | None = None,
) -> list[Query]:
    """
    “Views generation using predicates” (slides) / predicate views P (Algorithm 1).

    The paper draft does not fully specify the view-generation procedure, so this
    provides a simple, reasonable default: for each predicate attribute A and for
    each value v in its active domain, create a single-condition view A == v.
    """

    views: list[Query] = []
    for a in predicate_attrs:
        dom = active_domain(dataset, a)
        if max_values_per_attr is not None:
            dom = dom[: max_values_per_attr]
        for v in dom:
            views.append(Query((Condition(a, Op.EQ, v),)))
    return views


def find_top_k_explanations(
    *,
    dataset: Sequence[Mapping[str, Any]],
    q1: Query,
    q2: Query,
    candidates: Sequence[Candidate],
    k: int,
    epsilon: float,
    hd_sensitivity: float = 1.0,
    diversity: Callable[[str, set[str]], float] = diversity_score_unique_attribute,
    rng: random.Random,
) -> list[Candidate]:
    """
    Algorithm 2 Find-Top-k-Explanations (as in the PDF pseudocode).

    The pseudocode adds histogram noise after selecting each Hi. We follow that:
    this function returns the chosen (deterministic) candidates; the caller can
    noise the selected histograms using its per-step budget.
    """

    if k <= 0 or not candidates:
        return []
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")

    remaining = list(candidates)
    chosen: list[Candidate] = []
    chosen_attrs: set[str] = set()

    # Per the pseudocode, selection happens k times; we allocate epsilon equally.
    eps_per_pick = epsilon / float(k)

    for _ in range(min(k, len(remaining))):
        def util(c: Candidate) -> float:
            return histogram_distance_hd(dataset=dataset, view=c.view, attr=c.attribute, q1=q1, q2=q2) * diversity(
                c.attribute, chosen_attrs
            )

        em_res = exponential_mechanism(
            remaining,
            util,
            epsilon=eps_per_pick,
            sensitivity=hd_sensitivity,
            rng=rng,
        )
        picked = em_res.item  # type: ignore[assignment]
        assert isinstance(picked, Candidate)
        chosen.append(picked)
        chosen_attrs.add(picked.attribute)
        remaining = [c for c in remaining if c is not picked]

    return chosen


def private_queries_diff_topk_explanation(
    *,
    dataset: Sequence[Mapping[str, Any]],
    q1: Query,
    q2: Query,
    attributes: Sequence[str],
    predicate_views: Sequence[Query],
    tau: int,
    k: int,
    epsilon: float,
    rng: random.Random | None = None,
    view_score: Callable[[Query], float] | None = None,
) -> list[dict[str, Any]]:
    """
    Algorithm 1 Private-Queries-Diff-Top-K-Explanation (as in the PDF pseudocode).

    Returns a list of k explanation objects, each containing:
    - view predicate (as a list of conditions)
    - attribute explained
    - noisy histograms for Q1(view(D)) and Q2(view(D))

    Notes on draft gaps:
    - The paper references “One-Shot Top-τ” without specifying it; we implement
      it via noisy top-τ with Laplace noise on the view usefulness score.
    - The draft references another algorithm to “build noisy histograms”; here we
      add Laplace noise to histogram counts with the appropriate budget.
    """

    if rng is None:
        rng = random.Random()
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    if k <= 0:
        return []
    if tau <= 0:
        return []

    # Allocate budget as in the pseudocode: epsilon/2 for view selection, epsilon/2 for top-k selection+release.
    eps_views = epsilon / 2.0
    eps_expl = epsilon / 2.0

    if view_score is None:
        # Default view score uses the paper’s “coverage index” (Eq. (6)).
        view_score = lambda p: coverage_index(dataset=dataset, view=p, q1=q1, q2=q2)

    p_hat = one_shot_top_tau(
        list(predicate_views),
        view_score,
        tau=tau,
        epsilon=eps_views,
        sensitivity=1.0,
        rng=rng,
    )

    candidates: list[Candidate] = []
    for p in p_hat:
        view_rows = p(dataset)
        for a in attributes:
            buckets = active_domain(view_rows, a)
            h1 = histogram(q1(view_rows), a, buckets)
            h2 = histogram(q2(view_rows), a, buckets)
            candidates.append(Candidate(view=p, attribute=a, h_q1=h1, h_q2=h2))

    chosen = find_top_k_explanations(
        dataset=dataset,
        q1=q1,
        q2=q2,
        candidates=candidates,
        k=k,
        epsilon=eps_expl,
        rng=rng,
    )

    # Release noisy histograms. We use a simple sequential split: epsilon/k for each selected histogram pair.
    # Each histogram count has L1 sensitivity 1 under add/remove-one neighboring relation.
    eps_per_release = eps_expl / float(max(1, k))

    out: list[dict[str, Any]] = []
    for c in chosen:
        noisy_q1 = add_laplace_noise_to_counts(c.h_q1, epsilon=eps_per_release, sensitivity=1.0, rng=rng)
        noisy_q2 = add_laplace_noise_to_counts(c.h_q2, epsilon=eps_per_release, sensitivity=1.0, rng=rng)
        out.append(
            {
                "attribute": c.attribute,
                "view": [(cond.attr, cond.op.value, cond.value) for cond in c.view.conditions],
                "noisy_hist_q1": noisy_q1,
                "noisy_hist_q2": noisy_q2,
            }
        )
    return out

