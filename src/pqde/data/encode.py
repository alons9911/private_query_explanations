"""Encoding of a relation into public histogram bins (Section 2.3).

Every attribute used by the framework is mapped to a *public* finite set of
bins ``Dom(D[A])``.  Categorical attributes keep their values; numerical
attributes are bucketed into ranges.  The paper buckets numerical attributes
into six quantile bins.  The paper requires the bins to come from the public
schema / domain metadata; in this reproduction the cut points are computed
once from the full benchmark file and are then treated as public metadata
(they are stored with the encoded dataset and never recomputed per query).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MISSING = "NA"
OTHER = "Other"


@dataclass
class EncodedDataset:
    """A relation together with its public bin encoding.

    Attributes
    ----------
    name:
        Dataset name.
    raw:
        The raw relation; queries ``Q1``/``Q2`` are evaluated on it.
    codes:
        ``attr -> int array`` with the bin index of every tuple.
    domains:
        ``attr -> list[str]``: the public labels of ``Dom(D[A])``.
    explain_attrs, ref_attrs, view_attrs:
        ``Attrs``, ``A_R`` and the attributes over which views are built.
    numeric_edges:
        The bin edges used for every bucketed numeric attribute.
    meta:
        Free-form provenance information (source file, synthetic flag, ...).
    """

    name: str
    raw: pd.DataFrame
    codes: dict[str, np.ndarray]
    domains: dict[str, list[str]]
    explain_attrs: list[str]
    ref_attrs: list[str]
    view_attrs: list[str]
    numeric_edges: dict[str, list[float]] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def N(self) -> int:
        return len(self.raw)

    def domain_size(self, attr: str) -> int:
        return len(self.domains[attr])

    def subsample(self, n: int, seed: int = 0, replace: bool = False) -> "EncodedDataset":
        """A uniformly sampled sub-relation with the *same* public bins."""
        rng = np.random.default_rng(seed)
        idx = rng.choice(self.N, size=n, replace=replace)
        idx = np.sort(idx)
        return EncodedDataset(
            name=f"{self.name}[n={n}]",
            raw=self.raw.iloc[idx].reset_index(drop=True),
            codes={a: c[idx] for a, c in self.codes.items()},
            domains=self.domains,
            explain_attrs=self.explain_attrs,
            ref_attrs=self.ref_attrs,
            view_attrs=self.view_attrs,
            numeric_edges=self.numeric_edges,
            meta={**self.meta, "subsample_of": self.name, "subsample_seed": seed},
        )


def _fmt_edge(x: float) -> str:
    if float(x).is_integer():
        return str(int(x))
    return f"{x:.4g}"


def quantile_edges(x: np.ndarray, n_bins: int) -> list[float]:
    """Quantile cut points; duplicate edges (heavy atoms) are merged as in ``pd.qcut``."""
    x = x[~np.isnan(x)]
    qs = np.quantile(x, np.linspace(0.0, 1.0, n_bins + 1))
    edges = [float(qs[0])]
    for q in qs[1:]:
        if q > edges[-1]:
            edges.append(float(q))
    if len(edges) == 1:  # constant column
        edges.append(edges[0])
    return edges


def bucketize(x: np.ndarray, edges: list[float]) -> tuple[np.ndarray, list[str]]:
    """Map values to right-closed bins ``(e_{i}, e_{i+1}]``; the first bin is closed.

    Missing values get their own trailing bin labelled ``NA`` (only if present).
    """
    x = np.asarray(x, dtype=float)
    inner = np.asarray(edges[1:-1], dtype=float)
    codes = np.searchsorted(inner, x, side="left")  # right-closed bins
    labels = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        labels.append(f"[{_fmt_edge(lo)}, {_fmt_edge(hi)}]" if i == 0 else f"({_fmt_edge(lo)}, {_fmt_edge(hi)}]")
    nan = np.isnan(x)
    if nan.any():
        codes = codes.copy()
        codes[nan] = len(labels)
        labels.append(MISSING)
    return codes.astype(np.int64), labels


def categorical_codes(col: pd.Series, order: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    """Codes for a categorical column; values sorted by decreasing frequency unless ``order`` given."""
    s = col.astype("string").fillna(MISSING)
    if order is None:
        vc = s.value_counts(sort=True)
        order = list(vc.index)
    else:
        seen = set(order)
        extra = [v for v in s.unique() if v not in seen]
        order = list(order) + sorted(extra, key=lambda v: (v == MISSING, str(v)))
    lookup = {v: i for i, v in enumerate(order)}
    codes = s.map(lookup).to_numpy(dtype=np.int64)
    return codes, [str(v) for v in order]


def encode(
    name: str,
    raw: pd.DataFrame,
    *,
    numeric: list[str],
    categorical: list[str],
    explain_attrs: list[str],
    ref_attrs: list[str],
    view_attrs: list[str],
    n_bins: int = 6,
    top_values: dict[str, int] | None = None,
    declared_domains: dict[str, list[str]] | None = None,
    value_labels: dict[str, dict] | None = None,
    meta: dict | None = None,
) -> EncodedDataset:
    """Build an :class:`EncodedDataset`.

    ``top_values`` optionally caps the domain of a categorical attribute to its
    most frequent values plus an ``Other`` bin (used for very wide attributes).
    ``declared_domains`` fixes the domain of a categorical attribute to the values
    declared by the schema; values outside it go to an ``Other`` bin.
    """
    top_values = top_values or {}
    declared_domains = declared_domains or {}
    codes, domains, edges = {}, {}, {}
    for a in numeric:
        x = pd.to_numeric(raw[a], errors="coerce").to_numpy(dtype=float)
        e = quantile_edges(x, n_bins)
        codes[a], domains[a] = bucketize(x, e)
        edges[a] = e
    for a in categorical:
        col = raw[a].astype("string")
        if a in declared_domains:
            dom = [str(v) for v in declared_domains[a]]
            col = col.where(col.isin(dom) | col.isna(), OTHER)
            codes[a], domains[a] = categorical_codes(col, order=dom)
            continue
        if a in top_values:
            keep = list(col.value_counts().index[: top_values[a]])
            col = col.where(col.isin(keep) | col.isna(), OTHER)
        codes[a], domains[a] = categorical_codes(col)
    for a, mapping in (value_labels or {}).items():  # display names only; data keep their codes
        if a in domains:
            m = {str(k): str(v) for k, v in mapping.items()}
            domains[a] = [m.get(lab, lab) for lab in domains[a]]
    used = set(explain_attrs) | set(ref_attrs) | set(view_attrs)
    missing = used - set(codes)
    if missing:
        raise ValueError(f"attributes {sorted(missing)} are used but neither numeric nor categorical")
    return EncodedDataset(
        name=name,
        raw=raw.reset_index(drop=True),
        codes=codes,
        domains=domains,
        explain_attrs=list(explain_attrs),
        ref_attrs=list(ref_attrs),
        view_attrs=list(view_attrs),
        numeric_edges=edges,
        meta=meta or {},
    )
