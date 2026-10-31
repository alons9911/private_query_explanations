"""Shared helpers for the experiment drivers."""

from __future__ import annotations

import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..algorithm import Params
from ..data import CONFIG_DIR, REPO_ROOT

RESULTS_DIR = REPO_ROOT / "results"


def experiments_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "experiments.yaml") as f:
        return yaml.safe_load(f)


def params_from(defaults: dict, **overrides) -> Params:
    d = {**defaults, **overrides}
    return Params(
        k=int(d["k"]), lam=float(d["lam"]), epsilon=float(d["epsilon"]), split=tuple(d["split"]),
        tau_factor=int(d.get("tau_factor", 3)), release=d.get("release", "pair"),
        tau=d.get("tau"), gamma=d.get("gamma"),
    )


def out_dir(name: str, base: Path | None = None) -> Path:
    p = Path(base or RESULTS_DIR) / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        f = float(o)
        return None if math.isnan(f) else f
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=_default)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.6g")


def run_metadata(cfg: dict, **extra) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "machine": platform.machine(),
        "config": cfg,
        **extra,
    }


def spawn_rngs(seed: int, n: int, *keys: int) -> list[np.random.Generator]:
    ss = np.random.SeedSequence([int(seed), *[int(k) for k in keys]])
    return [np.random.default_rng(s) for s in ss.spawn(n)]


def stable_key(s: str) -> int:
    """A deterministic integer key for a string (Python's hash() is salted)."""
    return int.from_bytes(s.encode()[:8].ljust(8, b"\0"), "little") % (2**31)


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t0
        self.ms = 1e3 * self.seconds


def to_markdown(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    """A GitHub-flavoured markdown table (no extra dependency)."""
    def fmt(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else floatfmt.format(v)
        return str(v)

    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(fmt(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"
