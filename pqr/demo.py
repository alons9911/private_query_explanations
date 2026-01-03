from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from .algorithm import generate_simple_predicate_views, private_queries_diff_topk_explanation
from .query import Condition, Op, Query


def load_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, object]] = []
        for r in reader:
            # Keep everything as string for a simple demo.
            rows.append(dict(r))
        return rows


def main() -> None:
    """
    Minimal runnable demo:
    - compares Q1 vs Q2 on a dataset
    - generates simple predicate views
    - outputs k noisy histogram explanations
    """

    data_path = Path(__file__).with_name("toy.csv")
    dataset = load_csv(data_path)

    # Example “queries” (selection predicates only).
    # Q1: department == 'sales'
    # Q2: department == 'engineering'
    q1 = Query((Condition("department", Op.EQ, "sales"),))
    q2 = Query((Condition("department", Op.EQ, "engineering"),))

    # Explain differences using histograms over these attributes.
    attrs = ["gender", "seniority"]

    # Generate simple predicate views from a chosen predicate space.
    predicate_views = generate_simple_predicate_views(dataset, predicate_attrs=["country"])

    rng = random.Random(7)
    explanations = private_queries_diff_topk_explanation(
        dataset=dataset,
        q1=q1,
        q2=q2,
        attributes=attrs,
        predicate_views=predicate_views,
        tau=3,
        k=2,
        epsilon=1.0,
        rng=rng,
    )

    print(json.dumps(explanations, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

