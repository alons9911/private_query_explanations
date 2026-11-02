"""Assemble results/ from the shard outputs in results_shards/ (see scripts/run_shard.sh).

* Experiments run as one job (E1, E2, E3, E6, cases): their output directory is copied.
* Experiments run as one job per pair (E4, E5): the raw CSVs of all jobs are concatenated
  into results/<exp>/raw/, the metadata of the first job is kept, and the figures and
  summaries are rebuilt from the merged raw data (``pqde plot``).

Usage: python scripts/merge_shards.py [experiment ...]   (default: every experiment found)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "results_shards"
RESULTS = ROOT / "results"
WHOLE = {"e1": "e1", "e2": "e2", "e3": "e3", "e6": "e6", "cases": "case_studies"}
PER_PAIR = ("e4", "e5")


def job_dirs(exp: str) -> list[Path]:
    return sorted(p for p in SHARDS.glob(f"*/{exp}-*") if p.is_dir())


def merge_whole(exp: str) -> None:
    sub = WHOLE[exp]
    srcs = [d / sub for d in job_dirs(exp) if (d / sub).is_dir()]
    if not srcs:
        return
    if len(srcs) > 1:
        raise SystemExit(f"{exp}: more than one job output ({srcs}); expected one")
    dst = RESULTS / sub
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(srcs[0], dst)
    print(f"{exp}: copied {srcs[0].relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


def merge_per_pair(exp: str) -> None:
    dirs = [d / exp for d in job_dirs(exp) if (d / exp / "raw").is_dir()]
    if not dirs:
        return
    names = sorted({f.name for d in dirs for f in (d / "raw").glob("*.csv")})
    dst = RESULTS / exp
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "raw").mkdir(parents=True)
    for name in names:
        parts = [pd.read_csv(d / "raw" / name) for d in dirs if (d / "raw" / name).exists()]
        df = pd.concat(parts, ignore_index=True)
        df.to_csv(dst / "raw" / name, index=False)
        print(f"{exp}: {name}: {len(parts)} jobs, {len(df)} rows")
    meta = next((d / "metadata.json" for d in dirs if (d / "metadata.json").exists()), None)
    if meta:
        m = json.loads(meta.read_text())
        m["merged_from"] = [str(d.parent.relative_to(ROOT)) for d in dirs]
        (dst / "metadata.json").write_text(json.dumps(m, indent=2))


def main(argv: list[str]) -> None:
    exps = argv or list(WHOLE) + list(PER_PAIR)
    for exp in exps:
        (merge_per_pair if exp in PER_PAIR else merge_whole)(exp)
    plot = [e for e in exps if e in PER_PAIR and (RESULTS / e / "raw").is_dir()]
    if plot:
        from pqde.cli import main as cli

        cli(["plot", *plot])


if __name__ == "__main__":
    main(sys.argv[1:])
