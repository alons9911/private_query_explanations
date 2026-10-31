"""Checks against numbers printed in the paper (need the downloaded data)."""

import numpy as np
import pytest

from pqde.data.sources import DEFAULT_RAW_DIR

pytestmark = pytest.mark.skipif(not (DEFAULT_RAW_DIR / "adult" / "adult-all.csv").exists(),
                                reason="Adult not downloaded (run `pqde data`)")


def test_adult_size():
    from pqde.data import load_dataset

    assert load_dataset("adult").N == 48_842


@pytest.mark.parametrize("pid,s1,s2", [("A1", 0.047, 0.269), ("A2", 0.195, 0.306)])
def test_constraint_shares_table2(pid, s1, s2):
    from pqde.pairs import resolve_pair

    p = resolve_pair(pid)
    c = p.constraints[0]
    assert c.share(p.dataset.raw, p.q1) == pytest.approx(s1, abs=5e-4)
    assert c.share(p.dataset.raw, p.q2) == pytest.approx(s2, abs=5e-4)


def test_a2_running_example_view():
    """Section 5.2.1: |Q| = 3,055, |Q'| = 2,453; view education='Masters' has coverage 0.068 and Rep 0.53."""
    from pqde.pairs import pair_cache, resolve_pair

    p = resolve_pair("A2")
    assert (int(p.q1.sum()), int(p.q2.sum())) == (3055, 2453)
    c = pair_cache("A2")
    i = next(i for i, v in enumerate(c.views) if c.view_label(i) == "education='Masters'")
    assert c.cov[i] == pytest.approx(0.068, abs=5e-4)
    assert c.rep[i] == pytest.approx(0.53, abs=5e-3)


@pytest.mark.skipif(not (DEFAULT_RAW_DIR / "hospital" / "hospital_clean.csv").exists(), reason="hospital not downloaded")
def test_hospital_declared_domain():
    from pqde.data import load_dataset

    h = load_dataset("hospital")
    assert h.domains["EmergencyService"][:2] == ["no", "yes"]
    assert "yxs" not in h.domains["EmergencyService"]
