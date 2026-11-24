import numpy as np
import pandas as pd
import pytest

from pqde.cqa import choose_cqa_selection, conflict_hypergraph, consistent_answer
from pqde.refinement import Constraint, refine


def test_fd_conflicts():
    df = pd.DataFrame({
        "name": ["h1", "h1", "h1", "h2", "h2", "h3"],
        "zip": ["1", "1", "9", "2", "2", "3"],
        "city": ["x", "x", "y", "z", "z", "w"],
        "type": ["A", "A", "B", "A", "B", "A"],
    })
    g = conflict_hypergraph(df, [("name", "zip"), ("zip", "city")])
    assert g.in_conflict.tolist() == [True, True, True, False, False, False]
    assert g.per_fd["name->zip"]["edges"] == 2
    q, qs = consistent_answer("type = 'A'", df, g)
    assert q.tolist() == [True, True, False, True, False, True]
    assert qs.tolist() == [False, False, False, True, False, True]


def test_cqa_selection_rule():
    df = pd.DataFrame({"k": list("aaaabbbbbb"), "fd_l": list("1122334455"), "fd_r": list("xyxxxxxyxx"),
                       "o": list("ppppqqqqqq")})
    g = conflict_hypergraph(df, [("fd_l", "fd_r")])
    sel = choose_cqa_selection(df, g, "k", ["o"], min_size=1)
    assert sel is not None and 0.1 <= sel["drop_fraction"] <= 0.9


def test_refinement_relaxes_threshold():
    rng = np.random.default_rng(0)
    n = 2000
    g = rng.choice(["F", "M"], size=n, p=[0.3, 0.7])
    h = np.where(g == "F", rng.integers(20, 45, n), rng.integers(30, 70, n))
    df = pd.DataFrame({"g": g, "h": h})
    c = Constraint("g", ("F",), min_share=0.25)
    res = refine("h >= 50", [c], df)
    assert res.refined is not None
    mask = res.refined.evaluate(df)
    assert c.share(df, mask) >= 0.25
    assert res.refined.to_sql().startswith("h >= ")
    assert float(res.refined.to_sql().split(">=")[1]) < 50


def test_where_constraint():
    df = pd.DataFrame({"r": [0, 0, 1, 2, 3], "s": [1, 1, 1, 1, 1]})
    c = Constraint.from_dict({"where": "r > 0", "min_share": 0.5})
    assert c.share(df, np.ones(5, bool)) == pytest.approx(0.6)
