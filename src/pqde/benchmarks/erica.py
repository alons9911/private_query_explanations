"""Erica's ACSIncome benchmark (Li et al., PVLDB 17(2), 2023) as query pairs.

The queries, constraints and the minimal refinements returned by Erica are read
from ``configs/benchmarks/erica_acsincome`` (copied from the authors'
repository).  The refinement vectors are decoded here -- Erica's code is not
executed -- following the layout of its PVL tables
(``Algorithm/ProvenanceSearchValues_8_20230119.py``):

* relaxation constraints: [numeric thresholds..., one flag per categorical value
  *not* selected by the query, in order of first appearance in the data];
  flag 1 = the value is added;
* contraction constraints: [numeric thresholds..., one flag per selected value,
  in the query's order]; flag 1 = the value is kept;
* mixed constraints: [numeric thresholds..., one flag per categorical value in
  order of first appearance]; flag 1 = the value is selected.

Every decoded refinement is validated on the data: it must satisfy all of its
constraints, and the original query must violate them.  Combinations whose
vectors do not validate under this layout (Q1C3 and Q4C9, whose flag order is
ambiguous) are reported and left out.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..data import CONFIG_DIR

BENCH_DIR = CONFIG_DIR / "benchmarks" / "erica_acsincome"
# Erica's notation: the constraint sets C1..C9 of its Figure 3
COMBOS = {(1, "relax1"): "C1", (1, "contract1"): "C2", (1, "refine1"): "C3",
          (2, "relax1"): "C1", (2, "contract1"): "C2", (2, "refine1"): "C3",
          (3, "relax1"): "C4", (3, "contract1"): "C5", (3, "refine1"): "C6",
          (4, "relax1"): "C7", (4, "contract1"): "C8", (4, "refine1"): "C9"}


def _q(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def query_sql(numeric: dict, categorical: dict) -> str:
    parts = [f"{a} {op} {int(t) if float(t).is_integer() else t}" for a, (op, t) in numeric.items()]
    for a, vals in categorical.items():
        vals = list(vals)
        parts.append(f"{a} = {_q(vals[0])}" if len(vals) == 1 else f"{a} IN ({', '.join(_q(v) for v in vals)})")
    return " AND ".join(parts)


def constraint_dicts(cj: dict) -> list[dict]:
    out = []
    for fc in cj["fairness_constraints"]:
        where = " AND ".join(f"{a} = {_q(v) if isinstance(v, str) else v}" for a, v in fc["sensitive_attributes"].items())
        key = "min_count" if fc["symbol"] == ">=" else "max_count"
        out.append({"where": where, key: int(fc["number"])})
    return out


def _vectors(q: int, c: str) -> list[list[float]]:
    txt = (BENCH_DIR / "results" / f"result_q{q}{c}.csv").read_text()
    block = txt.split("provenance search")[1].split("baseline")[0]
    return [[float(x) for x in m.split(",")] for m in re.findall(r"\[([^\]]+)\]", block)]


def _group_count(df: pd.DataFrame, mask: np.ndarray, sens: dict) -> int:
    m = mask.copy()
    for a, v in sens.items():
        m &= (df[a].astype(str) == str(v)).to_numpy()
    return int(m.sum())


def _satisfies(df: pd.DataFrame, mask: np.ndarray, cj: dict) -> bool:
    for fc in cj["fairness_constraints"]:
        n = _group_count(df, mask, fc["sensitive_attributes"])
        if (fc["symbol"] == ">=" and n < fc["number"]) or (fc["symbol"] == "<=" and n > fc["number"]):
            return False
    return True


def _mask(df: pd.DataFrame, numeric: dict, categorical: dict) -> np.ndarray:
    m = np.ones(len(df), dtype=bool)
    for a, (op, t) in numeric.items():
        m &= (df[a] >= t).to_numpy() if op == ">=" else (df[a] <= t).to_numpy()
    for a, vals in categorical.items():
        m &= df[a].astype(str).isin([str(v) for v in vals]).to_numpy()
    return m


def decode_combo(df: pd.DataFrame, q: int, c: str) -> dict:
    qj = json.loads((BENCH_DIR / f"q{q}" / f"q{q}.json").read_text())
    cj = json.loads((BENCH_DIR / f"q{q}" / f"constraint_{c}.json").read_text())
    num = {a: (v[0], v[1]) for a, v in qj["selection_numeric_attributes"].items()}
    sel = {a: [str(x) for x in v] for a, v in qj.get("selection_categorical_attributes", {}).items()}
    order = {a: [str(v) for v in df[a].dropna().astype(str).unique().tolist()] for a in sel}
    refinements = []
    for vec in _vectors(q, c):
        thr, flags = vec[:len(num)], vec[len(num):]
        cat, pos = {}, 0
        for a, chosen in sel.items():
            if c.startswith("relax"):
                cols = [x for x in order[a] if x not in chosen]
                fl = flags[pos:pos + len(cols)]
                cat[a] = chosen + [x for x, f in zip(cols, fl) if f == 1]
            elif c.startswith("contract"):
                cols = chosen
                fl = flags[pos:pos + len(cols)]
                cat[a] = [x for x, f in zip(cols, fl) if f == 1]
            else:
                cols = order[a]
                fl = flags[pos:pos + len(cols)]
                cat[a] = [x for x, f in zip(cols, fl) if f == 1]
            pos += len(cols)
        nq = {a: (num[a][0], t) for a, t in zip(num, thr)}
        refinements.append({"vector": vec, "sql": query_sql(nq, cat),
                            "valid": bool(cat and all(cat.values()) or not sel) and _satisfies(df, _mask(df, nq, cat), cj)})
    return {"id": f"Q{q}{COMBOS[(q, c)]}", "query": q, "constraint_file": c, "constraint_set": COMBOS[(q, c)],
            "q1_sql": query_sql(num, sel), "constraints": constraint_dicts(cj),
            "original_violates": not _satisfies(df, _mask(df, num, sel), cj), "refinements": refinements,
            "all_valid": all(r["valid"] for r in refinements)}


def decode_all(df: pd.DataFrame) -> list[dict]:
    return [decode_combo(df, q, c) for (q, c) in COMBOS]
