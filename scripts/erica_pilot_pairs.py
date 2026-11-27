"""Pilot: query pairs from the stored results of the Erica experiments on Adult, COMPAS and Healthcare.

Reads the queries, constraints and minimal refinements that Erica's experiments stored
(github.com/alons9911/Query_refinement for Adult and COMPAS, github.com/JinyangLi01/query_refinement
for the Healthcare queries of the paper) -- no Erica code is run.  A refinement vector holds the
numeric thresholds in the order of the query's JSON, then one flag per categorical value of the
domain that the query does not select (relaxation) or does select (contraction), in the order of
the query's ``categorical_attributes`` list.  Each decoded refinement is validated on Erica's own
copy of the data: the original query must violate the constraints, the refinement satisfy them.
Erica returns every minimal refinement; the pilot keeps the one closest to the original query by
Erica's predicate distance.

Writes results/erica_pilot/pairs.csv and prints a YAML block for configs/pairs.yaml.

Usage: python scripts/erica_pilot_pairs.py
"""

from __future__ import annotations

import json
import re
from itertools import permutations
from pathlib import Path

import numpy as np
import pandas as pd

DEMO = Path("/home/user/ext/alons9911_Query_refinement")
if (DEMO / "alons9911_Query_refinement").exists():
    DEMO = DEMO / "alons9911_Query_refinement"
JL = Path("/home/user/jinyangli01/query_refinement")
OUT = Path("results/erica_pilot")
OUT.mkdir(parents=True, exist_ok=True)

ADULT_COLS = ("age,workclass,fnlwgt,education,education-num,marital-status,occupation,relationship,race,sex,"
              "capital-gain,capital-loss,hours-per-week,native-country,income").split(",")


def load(ds: str) -> pd.DataFrame:
    if ds == "adult_erica":
        df = pd.read_csv(DEMO / "InputData/Adult/adult.data", header=None, names=ADULT_COLS, skipinitialspace=True)
        for c in ("age", "education-num", "capital-gain", "capital-loss", "hours-per-week"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["age"])
    elif ds == "compas_erica":
        df = pd.read_csv(DEMO / "InputData/Compas/compas-scores.csv")
    else:
        df = pd.read_csv(JL / "InputData/Healthcare/incomeK/before_selection_incomeK.csv")
    return df.reset_index(drop=True)


def blocks(path: Path) -> dict[int, list[list[float]]]:
    """Blocks of the result file by POSITION (1-based): a block is headed by the value of the varied
    parameter (a query or constraint number, or a threshold), in the order of the query/constraint files."""
    out, cur = {}, None
    for line in path.read_text().splitlines():
        line = line.strip()
        if re.fullmatch(r"\d+", line):
            cur = len(out) + 1
            out[cur] = []
        elif line.startswith("[") and cur is not None:
            out[cur].append([float(x) for x in line.strip("[]").split(",")])
    return out


def mask(df, num: dict, cat: dict) -> np.ndarray:
    m = np.ones(len(df), dtype=bool)
    for a, (op, t) in num.items():
        x = pd.to_numeric(df[a], errors="coerce")
        m &= ((x >= t) if op == ">=" else (x <= t) if op == "<=" else (x > t) if op == ">" else (x < t)).to_numpy()
    for a, vals in cat.items():
        m &= df[a].astype(str).isin([str(v) for v in vals]).to_numpy()
    return m


def satisfies(df, m: np.ndarray, cj: dict) -> bool:
    for fc in cj["fairness_constraints"]:
        g = m.copy()
        for a, v in fc["sensitive_attributes"].items():
            g &= (df[a].astype(str) == str(v)).to_numpy()
        n = int(g.sum())
        if fc["symbol"] == ">=" and n < fc["number"] or fc["symbol"] == "<=" and n > fc["number"]:
            return False
    return True


def decode(df, qj: dict, cj: dict, vec: list[float], layout: str):
    num = {a: (v[0], v[1]) for a, v in qj["selection_numeric_attributes"].items()}
    sel = {a: [str(x) for x in v] for a, v in qj.get("selection_categorical_attributes", {}).items()}
    dom = {a: [str(x) for x in qj.get("categorical_attributes", {}).get(a, df[a].dropna().astype(str).unique())]
           for a in sel}
    thr, flags = vec[:len(num)], vec[len(num):]
    cat, pos = {}, 0
    for a, chosen in sel.items():
        cols = [x for x in dom[a] if x not in chosen] if layout == "relax" else chosen if layout == "contract" else dom[a]
        fl = flags[pos:pos + len(cols)]
        if len(fl) != len(cols):
            return None
        cat[a] = (chosen + [x for x, f in zip(cols, fl) if f == 1]) if layout == "relax" else \
            [x for x, f in zip(cols, fl) if f == 1]
        pos += len(cols)
    if pos != len(flags):
        return None
    nq = {a: (num[a][0], t) for a, t in zip(num, thr)}
    return nq, cat


def distance(df, num0, cat0, num1, cat1) -> float:
    d = 0.0
    for a, (_, t0) in num0.items():
        x = pd.to_numeric(df[a], errors="coerce")
        d += abs(num1[a][1] - t0) / ((x.max() - x.min()) or 1)
    for a, v0 in cat0.items():
        s0, s1 = set(v0), set(cat1[a])
        d += len(s0 ^ s1) / len(s0 | s1)
    return d


def sql(num: dict, cat: dict) -> str:
    parts = []
    for a, (op, t) in num.items():
        t = int(t) if float(t).is_integer() else t
        parts.append(f"{a.replace('-', '_')} {op} {t}")
    for a, vals in cat.items():
        q = ", ".join("'" + v + "'" for v in vals)
        parts.append(f"{a.replace('-', '_')} = '{vals[0]}'" if len(vals) == 1 else f"{a.replace('-', '_')} IN ({q})")
    return " AND ".join(parts)


def constraints_yaml(cj: dict) -> list[dict]:
    out = []
    for fc in cj["fairness_constraints"]:
        where = " AND ".join(f"{a.replace('-', '_')} = '{v}'" for a, v in fc["sensitive_attributes"].items())
        out.append({"where": where, ("min_count" if fc["symbol"] == ">=" else "max_count"): int(fc["number"])})
    return out


# (pilot id, dataset, folder, query file, constraint file, result file, block index)
COMBOS = [
    ("EA1", "adult_erica", DEMO / "Experiment/adult/query_change_2/Q1C1_1", "query1.json", "constraint1.json", "result_q1c1.txt", 1),
    ("EA2", "adult_erica", DEMO / "Experiment/adult/query_change_2/Q1C1_1", "query2.json", "constraint1.json", "result_q1c1.txt", 2),
    ("EA3", "adult_erica", DEMO / "Experiment/adult/query_change_2/Q2C1", "query1.json", "constraint1.json", "result_q2c1.txt", 1),
    ("EA4", "adult_erica", DEMO / "Experiment/adult/query_change_2/Q1C2_2", "query1.json", "constraint2.json", "result_q1c2.txt", 1),
    ("EC1", "compas_erica", DEMO / "Experiment/compas/query_change_2/Q1C1_1", "query1.json", "constraint1.json", "result_q1c1.txt", 1),
    ("EC2", "compas_erica", DEMO / "Experiment/compas/query_change_2/Q1C1_1", "query5.json", "constraint1.json", "result_q1c1.txt", 5),
    ("EC3", "compas_erica", DEMO / "Experiment/compas/constraint_change/Q2C1_1", "query2.json", "constraint11.json", "result_q2c1.txt", 1),
    ("EH1", "healthcare_erica", JL / "Experiment/healthcare/constraint_change2/Q1C1", "query1.json", None, "result_constraint_change_q1_1.txt", 1),
    ("EH2", "healthcare_erica", JL / "Experiment/healthcare/constraint_change2/Q2C1", None, None, None, 1),
    ("EH3", "healthcare_erica", JL / "Experiment/healthcare/constraint_change2/Q3C1", None, None, None, 1),
    ("EH4", "healthcare_erica", JL / "Experiment/healthcare/constraint_change2/Q4C1", None, None, None, 1),
    ("EH5", "healthcare_erica", JL / "Experiment/healthcare/constraint_change2/Q1C2", None, None, None, 1),
]

rows = []
data = {}
for pid, ds, folder, qf, cf, rf, idx in COMBOS:
    if not folder.exists():
        print(pid, "folder missing", folder)
        continue
    df = data.setdefault(ds, load(ds))
    qf = qf or sorted(p.name for p in folder.glob("query*.json"))[0]
    cfs = sorted(folder.glob("constraint*.json"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    cf_path = folder / cf if cf else cfs[idx - 1]
    rf_path = folder / rf if rf else sorted(folder.glob("result*.txt"))[0]
    qj, cj = json.loads((folder / qf).read_text()), json.loads(cf_path.read_text())
    vecs = blocks(rf_path).get(idx, [])
    num0 = {a: (v[0], v[1]) for a, v in qj["selection_numeric_attributes"].items()}
    cat0 = {a: [str(x) for x in v] for a, v in qj.get("selection_categorical_attributes", {}).items()}
    q1m = mask(df, num0, cat0)
    best = None
    for layout in ("relax", "contract", "mixed"):
        dec = [decode(df, qj, cj, v, layout) for v in vecs]
        ok = [d for d in dec if d is not None and satisfies(df, mask(df, *d), cj) and mask(df, *d).sum() > 0]
        if ok and (best is None or len(ok) > len(best[1])):
            best = (layout, ok)
    if best is None:
        print(f"{pid}: no refinement validates ({len(vecs)} vectors in block {idx} of {rf_path.name})")
        continue
    layout, ok = best
    num1, cat1 = min(ok, key=lambda d: distance(df, num0, cat0, *d))
    q2m = mask(df, num1, cat1)
    row = {"pair": pid, "dataset": ds, "source": f"{folder.relative_to(folder.parents[3])}/{qf} + {cf_path.name}",
           "q1": sql(num0, cat0), "q2": sql(num1, cat1), "constraints": json.dumps(constraints_yaml(cj)),
           "N": len(df), "n_q1": int(q1m.sum()), "n_q2": int(q2m.sum()), "q1_violates": not satisfies(df, q1m, cj),
           "layout": layout, "n_refinements": len(vecs), "n_valid": len(ok)}
    rows.append(row)
    print(f"{pid} {ds}: {row['q1']}  ->  {row['q2']}  |Q1|={row['n_q1']} |Q2|={row['n_q2']} "
          f"Q1 violates={row['q1_violates']} valid {len(ok)}/{len(vecs)} ({layout})")
pd.DataFrame(rows).to_csv(OUT / "pairs.csv", index=False)
