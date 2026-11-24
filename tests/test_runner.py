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
