import numpy as np
import pandas as pd
import pytest

from pqde.refinement import Constraint, refine
from pqde.search import conjunctions, hidden_attributes, pinned_attributes, score_refinement, tvd_masks


def test_pinned_and_hidden(toy):
    assert pinned_attributes("a = 'a0' AND x >= 3") == {"a"}
    assert pinned_attributes("b IN ('b1') AND a IN ('a0', 'a1')") == {"b"}
    c = Constraint("c", ("yes",), min_share=0.5)
    hid = hidden_attributes(toy, ["a = 'a0'", "a IN ('a0', 'a1')"], c, proxies={"a": ["b"]})
    assert hid == ["x"]


def test_conjunctions_skip_same_attribute():
    qs = conjunctions(["a = 1", "a = 2", "b = 3"], 2)
    assert "a = 1 AND a = 2" not in qs and "a = 1 AND b = 3" in qs and len(qs) == 5


def test_tvd_masks(toy):
    m = np.ones(toy.N, dtype=bool)
    assert tvd_masks(toy, "a", m, m) == pytest.approx(0.0)
    a0 = toy.raw.a.eq("a0").to_numpy()
    assert tvd_masks(toy, "a", a0, ~a0) == pytest.approx(1.0)


def test_unexplained_aggregate_is_zero_for_pure_reweighting():
    # y depends on the group only, so any change of the aggregate is explained by the new share
    rng = np.random.default_rng(0)
    n = 4000
    g = rng.random(n) < 0.3
    df = pd.DataFrame({"g": np.where(g, "F", "M"), "h": rng.integers(20, 70, n), "y": g.astype(float)})
    from pqde.data.encode import encode

    ds = encode("t", df, numeric=["h", "y"], categorical=["g"], explain_attrs=["g", "h", "y"], ref_attrs=["g", "h", "y"],
                view_attrs=["g"])
    r = score_refinement(ds, "h >= 50", "h >= 30", Constraint("g", ("F",), min_share=0.2), "y")
    assert r["agg_unexplained"] == pytest.approx(0.0, abs=1e-9)


def test_refine_without_replacement():
    df = pd.DataFrame({"k": list("aaabbbcccc"), "g": list("MMMFFFFFFM")})
    c = Constraint("g", ("F",), min_share=0.9)   # only the swap k = 'b' reaches 90%
    swap = refine("k = 'a'", [c], df, allow_drop=False)
    keep = refine("k = 'a'", [c], df, allow_drop=False, allow_replace=False)
    assert swap.refined.to_sql() == "k = 'b'"
    assert keep.refined is None                  # a relaxation of {'a'} cannot reach 90%
    assert keep.n_evaluated < swap.n_evaluated
