"""Search for query pairs that make good case studies (Section 5.1, "Query pairs").

A good case-study pair is one where the two queries, the constraint and the
aggregate *do not* tell the analyst what changed, but the change is large
enough to survive the noise of an eps = 1 release.  The search scores every
candidate pair with:

``hidden_drift``
    max over the *hidden* attributes (explanation attributes that neither query
    predicate nor the constraint mentions, nor a proxy of the constraint
    attribute) of TVD(P_{Q1(D),A}, P_{Q2(D),A}): how much the population changed
    where nobody asked it to.
``group_drift``  (refinement only)
    the same TVD computed *inside* the constrained group G (e.g. women in Q vs
    women in Q'): high when the refinement did not bring in "more of the same"
    members of G but different ones -- the A2 story of the paper.
``agg_unexplained``  (refinement only)
    AVG_{Q'}(y) - [s' AVG_{Q and G}(y) + (1 - s') AVG_{Q and not G}(y)], where s'
    is the share of G in Q': the part of the change of the aggregate that the
    change in representation alone does not account for.
``agg_shift``  (CQA)
    AVG_{Q_Sigma}(y) - AVG_Q(y): the bias the repair semantics introduces.
``drop`` / ``unevenness``  (CQA, the rule of Section 5.1)
    share of Q(D) that the consistent answer removes, and the largest TVD between
    the removed tuples and Q(D) over the hidden attributes.

:func:`dp_check` then runs the private algorithm a few times on a candidate
and reports the ApproxRatio against B2 and how often the released explanations
land on a hidden attribute with at least one bin clearing twice the noise s.d.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from .algorithm import Params, explain
from .baselines import b2, objective
from .cqa import ConflictHypergraph
from .data.encode import EncodedDataset
from .query import parse
from .refinement import Constraint, refine
from .stats import build_cache


def _dist(ds: EncodedDataset, attr: str, mask: np.ndarray) -> np.ndarray:
    h = np.bincount(ds.codes[attr][mask], minlength=ds.domain_size(attr)).astype(float)
    s = h.sum()
    return h / s if s else h


def tvd_masks(ds: EncodedDataset, attr: str, m1: np.ndarray, m2: np.ndarray) -> float:
    if not m1.any() or not m2.any():
        return float("nan")
    return float(0.5 * np.abs(_dist(ds, attr, m1) - _dist(ds, attr, m2)).sum())


def max_tvd(ds: EncodedDataset, attrs: list[str], m1: np.ndarray, m2: np.ndarray) -> tuple[float, str | None]:
    best, where = 0.0, None
    for a in attrs:
        t = tvd_masks(ds, a, m1, m2)
        if t == t and t > best:
            best, where = t, a
    return best, where


def hidden_attributes(ds: EncodedDataset, sqls: list[str], constraint: Constraint | None = None,
                      proxies: dict | None = None) -> list[str]:
    """Explanation attributes the analyst cannot read off the queries or the constraint.

    Excludes every attribute a predicate or the constraint mentions, and their
    proxies (e.g. ``relationship`` for ``gender`` / ``maritalStatus`` on Adult).
    """
    used: set[str] = set()
    for s in sqls:
        if s and not s.startswith("Q_Sigma("):
            used |= parse(s).attributes()
    if constraint is not None:
        used |= {constraint.attr} if constraint.attr else parse(constraint.where).attributes()
    for a in list(used):
        used |= set((proxies or {}).get(a, []))
    return [a for a in ds.explain_attrs if a not in used]


def pinned_attributes(sql: str) -> set[str]:
    """Attributes a conjunctive predicate fixes to a single value (``A = v`` or ``A IN (v)``)."""
    from .query import Atom, conjuncts

    out = set()
    for a in conjuncts(parse(sql)):
        if isinstance(a, Atom) and (a.op == "=" or (a.op == "IN" and len(a.values) == 1)):
            out.add(a.attr)
    return out


def conjunctions(atoms: list[str], max_atoms: int = 2) -> list[str]:
    out = []
    for r in range(1, max_atoms + 1):
        for combo in combinations(atoms, r):
            attrs = [parse(a).attributes() for a in combo]
            if len(set().union(*attrs)) < sum(len(x) for x in attrs):
                continue  # two conditions on the same attribute
            out.append(" AND ".join(combo))
    return out


# --------------------------------------------------------------------------- refinement


def score_refinement(ds: EncodedDataset, q1_sql: str, q2_sql: str, constraint: Constraint, agg: str | None,
                     proxies: dict | None = None) -> dict:
    df = ds.raw
    q1 = parse(q1_sql).evaluate(df)
    q2 = parse(q2_sql).evaluate(df)
    g = constraint.group_mask(df)
    hidden = hidden_attributes(ds, [q1_sql, q2_sql], constraint, proxies)
    drift, drift_attr = max_tvd(ds, hidden, q1, q2)
    gdrift, gdrift_attr = max_tvd(ds, hidden, q1 & g, q2 & g)
    ngdrift, ngdrift_attr = max_tvd(ds, hidden, q1 & ~g, q2 & ~g)
    row = {
        "Q1": q1_sql, "Q2": q2_sql, "constraint": constraint.describe(), "|Q1|": int(q1.sum()), "|Q2|": int(q2.sum()),
        "share_Q1": constraint.share(df, q1), "share_Q2": constraint.share(df, q2),
        "output_jaccard": 1 - (q1 & q2).sum() / max(1, (q1 | q2).sum()),
        "hidden_drift": drift, "hidden_drift_attr": drift_attr,
        "group_drift": gdrift, "group_drift_attr": gdrift_attr,
        "nongroup_drift": ngdrift, "nongroup_drift_attr": ngdrift_attr,
        "hidden_attrs": ",".join(hidden),
    }
    if agg is not None and agg in hidden:
        y = pd.to_numeric(df[agg], errors="coerce").to_numpy(dtype=float)
        a1, a2 = np.nanmean(y[q1]), np.nanmean(y[q2])
        s2 = row["share_Q2"]
        if (q1 & g).any() and (q1 & ~g).any():
            cf = s2 * np.nanmean(y[q1 & g]) + (1 - s2) * np.nanmean(y[q1 & ~g])
        else:
            cf = float("nan")
        row.update({"agg": agg, "agg_Q1": a1, "agg_Q2": a2, "agg_counterfactual": cf,
                    "agg_change": a2 - a1, "agg_unexplained": a2 - cf})
    return row


def refinement_candidates(ds: EncodedDataset, atoms: list[str], constraints: list[dict], *, min_size: int = 1500,
                          max_size: int = 20000, agg: str | None = None, proxies: dict | None = None,
                          max_atoms: int = 2, refine_options: dict | None = None, log_every: int = 50) -> pd.DataFrame:
    df = ds.raw
    rows = []
    qs = conjunctions(atoms, max_atoms)
    masks = {q: parse(q).evaluate(df) for q in qs}
    todo = []
    for cdict in constraints:
        c = Constraint.from_dict(cdict)
        for q in qs:
            n = int(masks[q].sum())
            if not (min_size <= n <= max_size):
                continue
            sh = c.share(df, masks[q])
            ok = c.satisfied_counts(np.array([sh * n]), np.array([n]))[0]
            if ok:
                continue  # Q already satisfies the constraint: nothing to refine
            todo.append((q, c))
    for i, (q, c) in enumerate(todo):
        opts = {"allow_replace": False, **(refine_options or {})}
        res = refine(q, [c], df, min_size=min_size // 2, **opts)
        if res.refined is None:
            continue
        q2 = res.refined.to_sql()
        row = score_refinement(ds, q, q2, c, agg, proxies)
        row["predicate_distance"] = res.distance
        rows.append(row)
        if log_every and (i + 1) % log_every == 0:
            print(f"    refinement search {i + 1}/{len(todo)}")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- CQA


def cqa_candidates(ds: EncodedDataset, graph: ConflictHypergraph, atoms: list[str], *, min_size: int = 200,
                   min_drop: float = 0.10, max_drop: float = 0.90, agg: str | None = None,
                   max_atoms: int = 2) -> pd.DataFrame:
    df = ds.raw
    rows = []
    y = pd.to_numeric(df[agg], errors="coerce").to_numpy(dtype=float) if agg else None
    for q in conjunctions(atoms, max_atoms):
        m = parse(q).evaluate(df)
        n = int(m.sum())
        if n < min_size:
            continue
        qs = m & ~graph.in_conflict
        dropped = m & graph.in_conflict
        drop = dropped.sum() / n
        if not (min_drop <= drop <= max_drop):
            continue
        # both outputs carry the same predicate, so only attributes it pins to one value are visible
        pinned = pinned_attributes(q)
        hidden = [a for a in ds.explain_attrs if a not in pinned]
        unev, unev_attr = max_tvd(ds, hidden, dropped, m)
        drift, drift_attr = max_tvd(ds, hidden, m, qs)
        row = {"Q1": q, "Q2": f"Q_Sigma({q})", "|Q1|": n, "|Q2|": int(qs.sum()), "drop": float(drop),
               "unevenness": unev, "unevenness_attr": unev_attr, "hidden_drift": drift, "hidden_drift_attr": drift_attr,
               "hidden_attrs": ",".join(hidden)}
        if y is not None:
            a1, a2 = np.nanmean(y[m]), np.nanmean(y[qs])
            row.update({"agg": agg, "agg_Q1": a1, "agg_Q2": a2, "agg_shift": a2 - a1,
                        "agg_shift_rel": (a2 - a1) / a1 if a1 else np.nan})
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- DP visibility


def dp_check(ds: EncodedDataset, q1: np.ndarray, q2: np.ndarray, hidden: list[str], *, trials: int = 8,
             params: Params | None = None, seed: int = 0) -> dict:
    """ApproxRatio vs B2 and how often eps-DP explanations reveal a hidden attribute."""
    params = params or Params()
    cache = build_cache(ds, q1, q2)
    F2 = objective(cache, b2(cache, params), params.lam)
    ratios, hidden_hits, clear_hits, attrs_seen = [], [], [], {}
    for t in range(trials):
        res = explain(cache, params, np.random.default_rng([seed, t]))
        ratios.append(objective(cache, res.selections, params.lam) / F2 if F2 else np.nan)
        sd = 2 * (2 * params.k / res.eps_H)  # s.d. of the released per-bin difference
        for e in res.explanations:
            diff = np.abs(e.noisy_h1 - e.noisy_h2)
            clears = bool((diff >= 2 * sd).any())
            hidden_hits.append(e.attr in hidden and clears)
            clear_hits.append(clears)
            attrs_seen[e.attr] = attrs_seen.get(e.attr, 0) + 1
    return {"dp_ratio_B2": float(np.nanmean(ratios)), "dp_hidden_rate": float(np.mean(hidden_hits)),
            "dp_clear_rate": float(np.mean(clear_hits)),
            "dp_attrs": ",".join(f"{a}:{c}" for a, c in sorted(attrs_seen.items(), key=lambda x: -x[1]))}
