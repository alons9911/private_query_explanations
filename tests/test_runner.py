import numpy as np

from pqde import timeouts
from pqde.algorithm import Params
from pqde.query import parse
from pqde.runner import METHODS, run_method, time_methods


def _masks(toy):
    return parse("x >= 25").evaluate(toy.raw), parse("a = 'a1' OR c = 'yes'").evaluate(toy.raw)


def test_time_methods_all_methods_and_opt_matches_priv(toy):
    q1, q2 = _masks(toy)
    outs = {o.method: o for o in time_methods(toy, q1, q2, Params(k=3), seed=1, repeat=0)}
    assert set(outs) == set(METHODS)
    assert outs["PRIV_EXPL"].selections == outs["OPT_PRIV_EXPL"].selections
    for o in outs.values():
        assert not o.timeout and o.total_s >= o.build_s >= 0


def test_timeouts_are_recorded(toy):
    q1, q2 = _masks(toy)
    outs = time_methods(toy, q1, q2, Params(k=3), timeout_s=0.0)
    assert all(o.timeout and o.total_s == 0.0 for o in outs)
    out = run_method("B2", toy, q1, q2, Params(k=3), timeout_s=0.0)
    assert out.timeout and out.selections is None


def test_deadline_is_noop_outside_and_restored():
    timeouts.check()
    with timeouts.deadline(1000):
        timeouts.check()
    timeouts.check()


def test_methods_without_view_stage_reach_the_optimum(toy):
    """OPT (greedy over every candidate), EXH_ALL (pruned) and EXH_NAIVE (unpruned) find sets of equal F."""
    from pqde.baselines import objective
    from pqde.runner import NO_VIEW_ROUTE
    from pqde.stats import build_cache

    q1, q2 = _masks(toy)
    for k in (1, 2):
        outs = {o.method: o for o in time_methods(toy, q1, q2, Params(k=k), seed=1, repeat=0)}
        cache = build_cache(toy, q1, q2, **NO_VIEW_ROUTE)
        f = {m: objective(cache, outs[m].selections, 0.5) for m in ("OPT", "EXH_ALL", "EXH_NAIVE")}
        assert f["OPT"] > 0 and abs(f["OPT"] - f["EXH_ALL"]) < 1e-9 and abs(f["OPT"] - f["EXH_NAIVE"]) < 1e-9
        assert len(outs["SINGLE_STAGE"].selections) == k


def test_naive_exhaustive_is_extrapolated_when_it_cannot_fit(toy):
    q1, q2 = _masks(toy)
    out = run_method("EXH_NAIVE", toy, q1, q2, Params(k=6), timeout_s=5.0)
    assert out.timeout and out.selections is None and out.extra["estimated"]
    assert out.extra["estimated_seconds"] > 5.0
