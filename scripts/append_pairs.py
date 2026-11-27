"""Append the raw rows of a separate run (e.g. new pairs run with --out results_new) to results/.

For every results_new/<exp>/raw/<name>.csv, the rows of its pairs replace any rows of the same
pairs in results/<exp>/raw/<name>.csv; the rows of all other pairs are kept.  Idempotent.
The columns must match the existing file.

Usage: python scripts/append_pairs.py results_new e2 e3 e6 e8 [e7]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src_base = ROOT / sys.argv[1]
for exp in sys.argv[2:]:
    for src in sorted((src_base / exp / "raw").glob("*.csv")):
        new = pd.read_csv(src)
        dst = ROOT / "results" / exp / "raw" / src.name
        if dst.exists():
            old = pd.read_csv(dst)
            if list(old.columns) != list(new.columns):
                raise SystemExit(f"{dst}: columns differ from {src}")
            kept = old[~old["pair"].isin(set(new["pair"]))]
            out = pd.concat([kept, new], ignore_index=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            kept, out = new.iloc[:0], new
        tmp = dst.with_suffix(".csv.tmp")
        out.to_csv(tmp, index=False)
        os.replace(tmp, dst)
        print(f"{dst.relative_to(ROOT)}: kept {len(kept)} rows, added {len(new)} ({new['pair'].nunique()} pairs)")
