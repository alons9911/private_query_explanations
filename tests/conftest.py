import numpy as np
import pandas as pd
import pytest

from pqde.data.encode import encode


def make_toy(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    a = rng.choice(["a0", "a1", "a2"], size=n, p=[0.5, 0.3, 0.2])
    b = rng.choice(["b0", "b1", "b2", "b3"], size=n)
    c = np.where(rng.random(n) < 0.3 + 0.4 * (a == "a1"), "yes", "no")
    x = np.round(rng.gamma(3.0, 10.0, size=n))
    return pd.DataFrame({"a": a, "b": b, "c": c, "x": x})


def encode_toy(df: pd.DataFrame):
    return encode("toy", df, numeric=["x"], categorical=["a", "b", "c"], explain_attrs=["a", "b", "c", "x"],
                  ref_attrs=["a", "b", "c", "x"], view_attrs=["a", "b", "c"], n_bins=4,
                  meta={"max_view_atoms": 2})


@pytest.fixture
def toy():
    return encode_toy(make_toy())
