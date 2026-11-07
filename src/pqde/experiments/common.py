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
    """Params from the defaults with ``overrides``; tau/gamma follow their rules unless given.

    ``gamma_mult`` != 1 cannot be resolved here (it needs |P| and |Attrs|); use
    :func:`make_params` for that.
    """
    d = {**defaults, **overrides}
    return Params(
        k=int(d["k"]), lam=float(d["lam"]), epsilon=float(d["epsilon"]), split=tuple(d["split"]),
        tau_factor=int(d.get("tau_factor", 3)), release=d.get("release", "pair"),
        tau=d.get("tau"), gamma=d.get("gamma"),
    )


def make_params(defaults: dict, n_views: int, n_attrs: int, **overrides) -> Params:
    """Params with every derived constant resolved for a dataset with ``n_views`` views and ``n_attrs`` attributes.

    tau = min(tau_factor * k, |P|) unless ``tau`` is given; gamma = gamma_mult * Eq. (12)
    (computed with that tau) unless ``gamma`` is given.
    """
    from ..algorithm import choose_gamma, choose_tau

    d = {**defaults, **overrides}
    p = params_from(d)
    tau = int(min(d["tau"], n_views)) if d.get("tau") is not None else choose_tau(p.k, n_views, p.tau_factor)
    if d.get("gamma") is not None:
        gamma = float(d["gamma"])
    else:
        gamma = float(d.get("gamma_mult", 1.0)) * choose_gamma(tau, n_attrs, p.k, p.budgets()[1])
    return p.with_(tau=tau, gamma=gamma)


def stats_route(defaults: dict) -> dict:
    s = defaults.get("stats") or {}
    return {"mode": s.get("mode", "grouped"), "rep": s.get("rep", "general"), "hist": s.get("hist", "eager")}


def default_cache(pair_id: str, defaults: dict):
    """The memoised statistics cache of a pair under the configured route."""
    from ..pairs import pair_cache

    return pair_cache(pair_id, **stats_route(defaults))


def pairs_by_dataset(pair_ids: list[str], datasets: list[str] | None = None) -> dict[str, list[str]]:
    from ..pairs import pairs_config

    spec = pairs_config()
    out: dict[str, list[str]] = {d: [] for d in (datasets or [])}
    for pid in pair_ids:
        out.setdefault(spec[pid]["dataset"], []).append(pid)
    return {d: v for d, v in out.items() if v}


def write_raw(df: pd.DataFrame, exp: str, name: str, base: Path | None = None) -> Path:
    """Raw per-run data of an experiment: ``results/<exp>/raw/<name>.csv`` (figures are rebuilt from these)."""
    p = out_dir(f"{exp}/raw", base) / f"{name}.csv"
    df.to_csv(p, index=False)
    return p


def read_raw(exp: str, name: str, base: Path | None = None) -> pd.DataFrame:
    return pd.read_csv(Path(base or RESULTS_DIR) / exp / "raw" / f"{name}.csv")


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
