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
    """Section 4 (running example): |Q| = 3,055, |Q'| = 2,453; view education='Masters' has coverage 0.068,
    Rep 0.80 at gamma_R = N/100 against the Eq. (5) ceiling 0.92, and Rep 0.53 at gamma_R = N."""
    from pqde.pairs import pair_cache, resolve_pair

    p = resolve_pair("A2")
    assert (int(p.q1.sum()), int(p.q2.sum())) == (3055, 2453)
    c = pair_cache("A2")
    i = next(i for i, v in enumerate(c.views) if c.view_label(i) == "education='Masters'")
    assert c.cov[i] == pytest.approx(0.068, abs=5e-4)
    assert c.rep[i] == pytest.approx(0.80, abs=5e-3)
    assert 1 - c.gamma_R / (2 * (c.m[i] + c.gamma_R)) == pytest.approx(0.92, abs=5e-3)
    from pqde.stats import build_cache
    cN = build_cache(p.dataset, p.q1, p.q2, gamma_R=float(p.dataset.N))
    assert cN.rep[i] == pytest.approx(0.53, abs=5e-3)


@pytest.mark.skipif(not (DEFAULT_RAW_DIR / "hospital" / "hospital_clean.csv").exists(), reason="hospital not downloaded")
def test_hospital_declared_domain():
    from pqde.data import load_dataset

    h = load_dataset("hospital")
    assert h.domains["EmergencyService"][:2] == ["no", "yes"]
    assert "yxs" not in h.domains["EmergencyService"]


@pytest.mark.skipif(not (DEFAULT_RAW_DIR / "ipums" / "cps_00005.csv.gz").exists(), reason="IPUMS not downloaded")
def test_ipums_as_dpxplain_and_contrast_exclusion():
    """DPXPlain's preparation gives 1,146,552 rows; contrast pairs drop the group attribute."""
    from pqde.pairs import resolve_pair
    from pqde.views import enumerate_views

    p = resolve_pair("I1")
    assert p.dataset.N == 1_146_552
    assert (int(p.q1.sum()), int(p.q2.sum())) == (556_230, 590_322)
    assert "SEX" not in p.dataset.explain_attrs and "SEX" not in p.dataset.view_attrs
    assert all("SEX" not in v.attrs for v in enumerate_views(p.dataset))
