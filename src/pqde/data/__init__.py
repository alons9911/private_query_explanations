"""Datasets: acquisition (``sources``), public bin encoding (``encode``) and the config-driven loader."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .encode import EncodedDataset, encode
from .sources import DEFAULT_RAW_DIR, LOADERS, REPO_ROOT, fetch

CONFIG_DIR = REPO_ROOT / "configs"

__all__ = ["EncodedDataset", "encode", "fetch", "load_dataset", "dataset_config", "CONFIG_DIR", "REPO_ROOT"]


def dataset_config(name: str, path: Path | None = None) -> dict:
    path = Path(path or CONFIG_DIR / "datasets.yaml")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if name not in cfg:
        raise KeyError(f"dataset {name!r} not in {path}; known: {sorted(cfg)}")
    return cfg[name]


@lru_cache(maxsize=8)
def _load_cached(name: str, raw_dir: str | None, config_path: str | None) -> EncodedDataset:
    cfg = dataset_config(name, Path(config_path) if config_path else None)
    loader = LOADERS[cfg.get("loader", name)]
    kwargs = {}
    if cfg.get("loader", name) == "tax":
        kwargs = {"target_rows": cfg.get("target_rows"), "seed": cfg.get("resample_seed", 0)}
    if cfg.get("loader", name) == "stackoverflow":
        kwargs = {"allow_synthetic": cfg.get("allow_synthetic", True)}
    raw, meta = loader(Path(raw_dir) if raw_dir else None, **kwargs)
    return encode(
        name,
        raw,
        numeric=cfg.get("numeric", []),
        categorical=cfg.get("categorical", []),
        explain_attrs=cfg["explain_attrs"],
        ref_attrs=cfg.get("ref_attrs", cfg["explain_attrs"]),
        view_attrs=cfg["view_attrs"],
        n_bins=cfg.get("n_bins", 6),
        top_values=cfg.get("top_values"),
        value_labels=cfg.get("value_labels"),
        declared_domains=meta.pop("declared_domains", None) if cfg.get("declared_domains", True) else None,
        meta={**meta, "max_view_atoms": cfg.get("max_view_atoms", 2), "fds": cfg.get("fds", [])},
    )


def load_dataset(name: str, raw_dir: Path | str | None = None, config_path: Path | str | None = None) -> EncodedDataset:
    """Load and encode a dataset according to ``configs/datasets.yaml`` (memoised)."""
    return _load_cached(name, str(raw_dir) if raw_dir else None, str(config_path) if config_path else None)
