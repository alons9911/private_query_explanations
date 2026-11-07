"""Predicate views (Definition 2.1).

The collection ``P`` consists of all conjunctions of at most ``l`` atomic
conditions ``A = b`` over the designated view attributes, where ``b`` ranges
over the public bins ``Dom(D[A])``.  ``P`` is built from the public schema
only, so ``|P|`` does not depend on the contents of ``D`` (empty views are
kept).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

import numpy as np

from .data.encode import EncodedDataset


@dataclass(frozen=True)
class View:
    """A conjunction ``A1 = b1 AND ... AND Al = bl`` of bin conditions."""

    attrs: tuple[str, ...]
    codes: tuple[int, ...]

    @property
    def attr_set(self) -> frozenset:
        return frozenset(self.attrs)

    def mask(self, ds: EncodedDataset) -> np.ndarray:
        out = np.ones(ds.N, dtype=bool)
        for a, c in zip(self.attrs, self.codes):
            out &= ds.codes[a] == c
        return out

    def label(self, ds: EncodedDataset) -> str:
        parts = []
        for a, c in zip(self.attrs, self.codes):
            v = ds.domains[a][c]
            parts.append(f"{a} IN {v}" if v.startswith(("(", "[")) else f"{a}='{v}'")
        return " AND ".join(parts)

    def __len__(self) -> int:
        return len(self.attrs)


def enumerate_views(ds: EncodedDataset, max_atoms: int | None = None, attrs: list[str] | None = None) -> list[View]:
    """All views with 1..``max_atoms`` atoms over ``attrs`` (default: the dataset's view attributes).

    Views are grouped by attribute set, and within a group ordered by the
    mixed-radix code of their bins; :class:`pqde.stats.StatsCache` relies on it.
    """
    attrs = list(attrs if attrs is not None else ds.view_attrs)
    max_atoms = max_atoms if max_atoms is not None else ds.meta.get("max_view_atoms", 2)
    views: list[View] = []
    for r in range(1, max_atoms + 1):
        for aset in combinations(attrs, r):
            for codes in product(*(range(ds.domain_size(a)) for a in aset)):
                views.append(View(tuple(aset), tuple(int(c) for c in codes)))
    return views
