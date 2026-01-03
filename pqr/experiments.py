from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .algorithm import (
    Candidate,
    histogram,
    histogram_distance_hd,
)
from .query import Condition, Op, Query, active_domain


def _coerce_scalar(x: str) -> object:
    s = x.strip()
    if s == "":
        return ""
    # ints first
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass
    # floats
    try:
        # avoid treating codes like "0012" as float; keep them as string
        if any(ch in s for ch in (".", "e", "E")):
            return float(s)
    except Exception:
        pass
    return s


def load_csv(path: Path, *, infer_types: bool = True) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows: list[dict[str, object]] = []
        for r in csv.DictReader(f):
            if not infer_types:
                rows.append(dict(r))
                continue
            rows.append({k: _coerce_scalar(v) for k, v in dict(r).items()})
        return rows


def downsample(rows: Sequence[Mapping[str, Any]], n: int, *, rng: random.Random) -> list[Mapping[str, Any]]:
    if n >= len(rows):
        return list(rows)
    idxs = list(range(len(rows)))
    rng.shuffle(idxs)
    return [rows[i] for i in idxs[:n]]


def generate_pairwise_predicate_views(
    dataset: Sequence[Mapping[str, Any]],
    predicate_attrs: Sequence[str],
    *,
    max_values_per_attr: int | None = None,
) -> list[Query]:
    """
    View generation per the slide pseudocode (“All combinations of A1=v1 and A2=v2”):

      for each (Ai, Aj) in Attributes × Attributes:
        for each (vi, vj) in Dom(Ai) × Dom(Aj):
          p(t) := (t[Ai] == vi) AND (t[Aj] == vj)

    Notes:
    - We only generate unordered pairs Ai != Aj to avoid duplicates and to keep runtime bounded.
    - `max_values_per_attr` bounds the per-attribute domain used in view generation.
    """

    attrs = list(dict.fromkeys(predicate_attrs))
    doms: dict[str, list[Any]] = {}
    for a in attrs:
        dom = active_domain(dataset, a)
        if max_values_per_attr is not None:
            dom = dom[: max_values_per_attr]
        doms[a] = dom

    views: list[Query] = []
    for i, ai in enumerate(attrs):
        for aj in attrs[i + 1 :]:
            for vi in doms.get(ai, []):
                for vj in doms.get(aj, []):
                    views.append(Query((Condition(ai, Op.EQ, vi), Condition(aj, Op.EQ, vj))))
    return views


def brute_force_topk_proxy(
    *,
    dataset: Sequence[Mapping[str, Any]],
    q1: Query,
    q2: Query,
    attributes: Sequence[str],
    predicate_views: Sequence[Query],
    tau: int,
    k: int,
) -> list[Candidate]:
    """
    Baseline: brute-force with the paper’s proxy utility (HD) and deterministic selection.

    Steps:
    - Choose top-τ views by coverage (deterministic, non-private).
    - Build candidates for all (view, attribute).
    - Select top-k by HD (with a simple attribute-uniqueness diversity penalty).
    """

    if tau <= 0 or k <= 0:
        return []

    def coverage(p: Query) -> float:
        view_rows = p(dataset)
        n = len(dataset) or 1
        return (len(q1(view_rows)) + len(q2(view_rows))) / float(n)

    p_sorted = sorted(predicate_views, key=coverage, reverse=True)[: min(tau, len(predicate_views))]

    candidates: list[Candidate] = []
    for p in p_sorted:
        view_rows = p(dataset)
        for a in attributes:
            buckets = active_domain(view_rows, a)
            h1 = histogram(q1(view_rows), a, buckets)
            h2 = histogram(q2(view_rows), a, buckets)
            candidates.append(Candidate(view=p, attribute=a, h_q1=h1, h_q2=h2))

    chosen: list[Candidate] = []
    chosen_attrs: set[str] = set()
    remaining = list(candidates)
    for _ in range(min(k, len(remaining))):
        def score(c: Candidate) -> float:
            if c.attribute in chosen_attrs:
                return float("-inf")
            return histogram_distance_hd(dataset=dataset, view=c.view, attr=c.attribute, q1=q1, q2=q2)

        best = max(remaining, key=score)
        chosen.append(best)
        chosen_attrs.add(best.attribute)
        remaining = [c for c in remaining if c is not best]
    return chosen


def non_proxy_distribution_distance(
    *,
    dataset: Sequence[Mapping[str, Any]],
    view: Query,
    attr: str,
    q1: Query,
    q2: Query,
) -> float:
    """
    “Non-proxy utility” (draft): L1 distance between conditional distributions of A
    in Q1(view(D)) vs Q2(view(D)).

    The paper text (around Definition 3.6) describes an “interestingness score”
    as absolute differences of conditional probabilities; we implement that.
    """

    view_rows = view(dataset)
    r1 = q1(view_rows)
    r2 = q2(view_rows)
    b = sorted(set(active_domain(r1, attr)) | set(active_domain(r2, attr)))
    if not b:
        return 0.0
    h1 = histogram(r1, attr, b)
    h2 = histogram(r2, attr, b)
    n1 = sum(h1.values())
    n2 = sum(h2.values())
    if n1 <= 0 or n2 <= 0:
        return 0.0
    return sum(abs((h1[x] / n1) - (h2[x] / n2)) for x in b)


def brute_force_topk_non_proxy(
    *,
    dataset: Sequence[Mapping[str, Any]],
    q1: Query,
    q2: Query,
    attributes: Sequence[str],
    predicate_views: Sequence[Query],
    tau: int,
    k: int,
) -> list[Candidate]:
    """
    Baseline: brute-force using the “non-proxy” conditional-distribution distance.
    """

    if tau <= 0 or k <= 0:
        return []

    # Still use coverage for view truncation to keep runtime reasonable.
    def coverage(p: Query) -> float:
        view_rows = p(dataset)
        n = len(dataset) or 1
        return (len(q1(view_rows)) + len(q2(view_rows))) / float(n)

    p_sorted = sorted(predicate_views, key=coverage, reverse=True)[: min(tau, len(predicate_views))]

    candidates: list[Candidate] = []
    for p in p_sorted:
        view_rows = p(dataset)
        for a in attributes:
            buckets = active_domain(view_rows, a)
            h1 = histogram(q1(view_rows), a, buckets)
            h2 = histogram(q2(view_rows), a, buckets)
            candidates.append(Candidate(view=p, attribute=a, h_q1=h1, h_q2=h2))

    chosen: list[Candidate] = []
    chosen_attrs: set[str] = set()
    remaining = list(candidates)
    for _ in range(min(k, len(remaining))):
        def score(c: Candidate) -> float:
            if c.attribute in chosen_attrs:
                return float("-inf")
            return non_proxy_distribution_distance(dataset=dataset, view=c.view, attr=c.attribute, q1=q1, q2=q2)

        best = max(remaining, key=score)
        chosen.append(best)
        chosen_attrs.add(best.attribute)
        remaining = [c for c in remaining if c is not best]
    return chosen


def private_explanations_topk(
    *,
    dataset: Sequence[Mapping[str, Any]],
    q1: Query,
    q2: Query,
    attributes: Sequence[str],
    predicate_views: Sequence[Query],
    tau: int,
    k: int,
    epsilon: float,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    A minimal private implementation aligned with Algorithm 1/2:
    - DP one-shot top-τ view selection (report noisy top-τ with Laplace)
    - DP top-k selection using Exponential Mechanism (via pqr.algorithm)
    - Laplace noise to released histograms
    """

    # Import locally to avoid circular imports.
    from .algorithm import private_queries_diff_topk_explanation

    return private_queries_diff_topk_explanation(
        dataset=dataset,
        q1=q1,
        q2=q2,
        attributes=attributes,
        predicate_views=predicate_views,
        tau=tau,
        k=k,
        epsilon=epsilon,
        rng=rng,
    )


class AlgorithmName(str):
    PRIVATE = "private-explanations"
    BRUTE_PROXY = "brute-force"
    BRUTE_NON_PROXY = "brute-force-non-proxy-utilities"


@dataclass(frozen=True)
class RunSpec:
    """
    A single experiment run (one point in a sweep).
    """

    dataset_csv: str
    q1: dict[str, Any]
    q2: dict[str, Any]
    attributes: list[str]
    predicate_attrs: list[str]
    max_values_per_predicate_attr: int | None
    algorithm: str
    k: int
    tau: int
    epsilon: float
    predicate_view_mode: str = "pairwise"  # "pairwise" (slides) or "single"
    n_tuples: int | None = None
    seed: int = 7
    repeats: int = 1
    label: str | None = None
    dataset_name: str | None = None


@dataclass(frozen=True)
class RunResult:
    """
    Captures runtime and a few quality-ish measures to support slide 43 “heatmaps”.
    """

    spec: RunSpec
    trial: int
    runtime_s: float
    avg_selected_hd: float
    avg_noisy_hist_mae: float | None


def _query_from_dict(d: Mapping[str, Any]) -> Query:
    # Format: {"conditions": [{"attr": "...", "op": "==", "value": ...}, ...]}
    conds = []
    for c in d.get("conditions", []):
        conds.append(Condition(c["attr"], Op(c["op"]), c["value"]))
    return Query(tuple(conds))


def _compute_selected_hd(
    *,
    dataset: Sequence[Mapping[str, Any]],
    q1: Query,
    q2: Query,
    selected: Iterable[tuple[Query, str]],
) -> float:
    vals = []
    for view, attr in selected:
        vals.append(histogram_distance_hd(dataset=dataset, view=view, attr=attr, q1=q1, q2=q2))
    return sum(vals) / float(len(vals) or 1)


def _hist_mae(true_h: Mapping[Any, float], noisy_h: Mapping[Any, float]) -> float:
    keys = set(true_h) | set(noisy_h)
    return sum(abs(float(true_h.get(k, 0.0)) - float(noisy_h.get(k, 0.0))) for k in keys) / float(len(keys) or 1)


def run_once(spec: RunSpec) -> RunResult:
    # Kept for backward compatibility; run_once represents a single trial.
    return _run_trial(spec, trial=0)


def _run_trial(spec: RunSpec, *, trial: int) -> RunResult:
    rng = random.Random(spec.seed + trial)
    dataset_full = load_csv(Path(spec.dataset_csv), infer_types=True)
    dataset: Sequence[Mapping[str, Any]]
    if spec.n_tuples is not None:
        dataset = downsample(dataset_full, spec.n_tuples, rng=rng)
    else:
        dataset = dataset_full

    q1 = _query_from_dict(spec.q1)
    q2 = _query_from_dict(spec.q2)

    if spec.predicate_view_mode == "pairwise":
        predicate_views = generate_pairwise_predicate_views(
            dataset,
            predicate_attrs=spec.predicate_attrs,
            max_values_per_attr=spec.max_values_per_predicate_attr,
        )
    elif spec.predicate_view_mode == "single":
        # Fall back to the simpler generator from algorithm.py
        from .algorithm import generate_simple_predicate_views

        predicate_views = generate_simple_predicate_views(
            dataset,
            predicate_attrs=spec.predicate_attrs,
            max_values_per_attr=spec.max_values_per_predicate_attr,
        )
    else:
        raise ValueError(f"Unknown predicate_view_mode: {spec.predicate_view_mode}")

    t0 = time.perf_counter()
    avg_noisy_mae: float | None = None

    if spec.algorithm == AlgorithmName.PRIVATE:
        out = private_explanations_topk(
            dataset=dataset,
            q1=q1,
            q2=q2,
            attributes=spec.attributes,
            predicate_views=predicate_views,
            tau=spec.tau,
            k=spec.k,
            epsilon=spec.epsilon,
            rng=rng,
        )
        runtime = time.perf_counter() - t0

        # Reconstruct selected views to compute HD and noise error.
        selected: list[tuple[Query, str]] = []
        maes: list[float] = []
        for e in out:
            attr = e["attribute"]
            view_conds = e["view"]
            view = Query(tuple(Condition(a, Op(op), v) for a, op, v in view_conds))
            selected.append((view, attr))

            # Compare noisy histogram against the true histogram for that same selection.
            view_rows = view(dataset)
            buckets = active_domain(view_rows, attr)
            true_h1 = histogram(q1(view_rows), attr, buckets)
            true_h2 = histogram(q2(view_rows), attr, buckets)
            maes.append(_hist_mae(true_h1, e["noisy_hist_q1"]))
            maes.append(_hist_mae(true_h2, e["noisy_hist_q2"]))
        avg_hd = _compute_selected_hd(dataset=dataset, q1=q1, q2=q2, selected=selected)
        avg_noisy_mae = sum(maes) / float(len(maes) or 1)
        return RunResult(
            spec=spec, trial=trial, runtime_s=runtime, avg_selected_hd=avg_hd, avg_noisy_hist_mae=avg_noisy_mae
        )

    if spec.algorithm == AlgorithmName.BRUTE_PROXY:
        chosen = brute_force_topk_proxy(
            dataset=dataset,
            q1=q1,
            q2=q2,
            attributes=spec.attributes,
            predicate_views=predicate_views,
            tau=spec.tau,
            k=spec.k,
        )
        runtime = time.perf_counter() - t0
        selected = [(c.view, c.attribute) for c in chosen]
        avg_hd = _compute_selected_hd(dataset=dataset, q1=q1, q2=q2, selected=selected)
        return RunResult(spec=spec, trial=trial, runtime_s=runtime, avg_selected_hd=avg_hd, avg_noisy_hist_mae=None)

    if spec.algorithm == AlgorithmName.BRUTE_NON_PROXY:
        chosen = brute_force_topk_non_proxy(
            dataset=dataset,
            q1=q1,
            q2=q2,
            attributes=spec.attributes,
            predicate_views=predicate_views,
            tau=spec.tau,
            k=spec.k,
        )
        runtime = time.perf_counter() - t0
        selected = [(c.view, c.attribute) for c in chosen]
        avg_hd = _compute_selected_hd(dataset=dataset, q1=q1, q2=q2, selected=selected)
        return RunResult(spec=spec, trial=trial, runtime_s=runtime, avg_selected_hd=avg_hd, avg_noisy_hist_mae=None)

    raise ValueError(f"Unknown algorithm: {spec.algorithm}")


def run_repeated(spec: RunSpec) -> list[RunResult]:
    """
    Run the same spec multiple times (different RNG seeds) to match the slide's “# of trials”.
    """

    reps = max(1, int(spec.repeats))
    return [_run_trial(spec, trial=i) for i in range(reps)]


def run_planned_experiments(
    *,
    out_dir: Path,
    base_spec: RunSpec,
) -> list[RunResult]:
    """
    Implements the “planned experiments” from slides 41–43:

    Slide 42 (Scalability):
    - Runtime = f(#tuples) (by down sampling)
    - Runtime = f(Algorithm)
    - Runtime = f(k)
    - Runtime = f(#Predicates)
    - Runtime = f(epsilon)
    - Runtime = f(tau)

    Slide 43 (Quality measures):
    - For each dataset, generate a heatmap by varying:
      initial predicates, tau, algorithm, epsilon

    Output:
    - Writes CSV files into out_dir suitable for plotting.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[RunResult] = []

    def emit(name: str, rows: list[RunResult]) -> None:
        p = out_dir / f"{name}.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                d = asdict(r)
                f.write(json.dumps(d) + "\n")

    # --- Runtime f(#tuples) ---
    sizes = []
    full_n = len(load_csv(Path(base_spec.dataset_csv)))
    for frac in (0.25, 0.5, 0.75, 1.0):
        sizes.append(max(2, int(full_n * frac)))
    sizes = sorted(set(sizes))
    for n in sizes:
        s = RunSpec(**{**asdict(base_spec), "n_tuples": n})
        results.extend(run_repeated(s))
    emit("runtime_vs_tuples", results[-len(sizes) * max(1, base_spec.repeats) :])

    # --- Runtime f(Algorithm) ---
    algs = [AlgorithmName.PRIVATE, AlgorithmName.BRUTE_PROXY, AlgorithmName.BRUTE_NON_PROXY]
    rows = []
    for a in algs:
        s = RunSpec(**{**asdict(base_spec), "algorithm": a})
        rows.extend(run_repeated(s))
    results.extend(rows)
    emit("runtime_vs_algorithm", rows)

    # --- Runtime f(k) ---
    ks = sorted(set([1, max(1, base_spec.k), base_spec.k + 1, base_spec.k + 2]))
    rows = []
    for k in ks:
        s = RunSpec(**{**asdict(base_spec), "k": k})
        rows.extend(run_repeated(s))
    results.extend(rows)
    emit("runtime_vs_k", rows)

    # --- Runtime f(#Predicates) ---
    # We approximate “#Predicates” by limiting values per predicate attribute.
    limits = [1, 2, 3, base_spec.max_values_per_predicate_attr or 3]
    limits = sorted({x for x in limits if x is not None and x > 0})
    rows = []
    for lim in limits:
        s = RunSpec(**{**asdict(base_spec), "max_values_per_predicate_attr": lim})
        rows.extend(run_repeated(s))
    results.extend(rows)
    emit("runtime_vs_num_predicates", rows)

    # --- Runtime f(epsilon) ---
    epsilons = [0.1, 0.5, base_spec.epsilon, 2.0]
    epsilons = sorted(set(float(e) for e in epsilons if e > 0))
    rows = []
    for e in epsilons:
        s = RunSpec(**{**asdict(base_spec), "epsilon": e})
        rows.extend(run_repeated(s))
    results.extend(rows)
    emit("runtime_vs_epsilon", rows)

    # --- Runtime f(tau) ---
    taus = sorted(set([1, 2, base_spec.tau, base_spec.tau + 2]))
    rows = []
    for t in taus:
        s = RunSpec(**{**asdict(base_spec), "tau": t})
        rows.extend(run_repeated(s))
    results.extend(rows)
    emit("runtime_vs_tau", rows)

    # --- Quality “heatmap” grid (slide 43) ---
    # Vary: initial predicates (approximated by predicate limit), tau, algorithm, epsilon.
    grid_rows: list[RunResult] = []
    for lim in limits:
        for t in taus:
            for a in algs:
                for e in epsilons:
                    s = RunSpec(
                        **{
                            **asdict(base_spec),
                            "max_values_per_predicate_attr": lim,
                            "tau": t,
                            "algorithm": a,
                            "epsilon": e,
                        }
                    )
                    grid_rows.extend(run_repeated(s))
    results.extend(grid_rows)
    emit("quality_heatmap_grid", grid_rows)

    return results


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run planned experiments (slides 41–43).")
    p.add_argument("--suite", default=None, help="Named suite (e.g., 'slide41').")
    p.add_argument("--dataset", default=str(Path(__file__).with_name("toy.csv")), help="CSV dataset path")
    p.add_argument("--dataset-ipums", default=None, help="IPUMS-CPS CSV path (for slide41 suite)")
    p.add_argument("--dataset-stackoverflow", default=None, help="StackOverflow survey CSV path (for slide41 suite)")
    p.add_argument("--out", default="results", help="Output directory")
    p.add_argument("--algorithm", default=AlgorithmName.PRIVATE, help="Algorithm name")
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--tau", type=int, default=3)
    p.add_argument("--epsilon", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--repeats", type=int, default=1, help="Number of trials to repeat each point")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)

    out_dir = Path(args.out)

    if args.suite == "slide41":
        from .slide_specs import slide41_suite

        suite = slide41_suite(ipums_csv=args.dataset_ipums, stackoverflow_csv=args.dataset_stackoverflow)
        for s in suite:
            s = RunSpec(**{**asdict(s), "seed": args.seed, "repeats": args.repeats})
            ds_name = s.dataset_name or Path(s.dataset_csv).stem
            label = s.label or "run"
            run_planned_experiments(out_dir=out_dir / ds_name / label, base_spec=s)
        print(f"Wrote slide41 experiment outputs to: {out_dir.resolve()}")
        return

    # Default query pair matches the demo: sales vs engineering.
    base = RunSpec(
        dataset_csv=args.dataset,
        q1={"conditions": [{"attr": "department", "op": "==", "value": "sales"}]},
        q2={"conditions": [{"attr": "department", "op": "==", "value": "engineering"}]},
        attributes=["gender", "seniority"],
        predicate_attrs=["country"],
        max_values_per_predicate_attr=3,
        algorithm=args.algorithm,
        k=args.k,
        tau=args.tau,
        epsilon=args.epsilon,
        seed=args.seed,
        repeats=args.repeats,
    )

    run_planned_experiments(out_dir=out_dir, base_spec=base)
    print(f"Wrote experiment outputs to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

