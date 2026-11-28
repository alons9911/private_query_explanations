"""Split the PREVIEW of the running-time rerun (configs/experiments_preview.yaml) into cloud shards pv-<n>.

Jobs: E4 one per (pair, sweep), E5, E7t and E7t7 one per pair; every method of a job runs in one
process on one machine.  Job lengths are estimated from the raw data of the earlier runs: 3 repeats
instead of 10 (3 attribute orders in E7), the exhaustive searches' timeouts stopped after their first
block, B2 counted twice (EXH_ALL), and half of PEEQ's time added for OPT, SingleStage and EXH_NAIVE.
Pairs without earlier data take the mean of their dataset.  Longest first, to the shard whose
simulated makespan (4 jobs at a time) grows least.

Usage: python scripts/plan_preview_shards.py [n_shards]
"""
import heapq
import io
import subprocess
import sys

import numpy as np
import pandas as pd
import yaml

N_SHARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
SLOTS = 4
cfg = yaml.safe_load(open("configs/experiments.yaml"))
ERICA = ["EA1", "EA2", "EA4", "EC1", "EC2", "EC3", "EH1", "EH2", "EH3", "EH5"]
PAIRS = list(cfg["pairs"]) + ERICA
SWEEPS = list(cfg["e4"]["sweeps"])
spec = yaml.safe_load(open("configs/pairs.yaml"))
spec = spec.get("pairs", spec)
LIKE = {"adult_erica": "adult", "compas_erica": "compas", "healthcare_erica": "law"}

frames = []
for f, e in [("results/e4/raw/runtime.csv", "e4"), ("results/e7/raw/runtime_k7.csv", "e7t7"),
             ("results/e7/raw/runtime.csv", "e7t"), ("results/e5/raw/default_point.csv", "e5")]:
    d = pd.read_csv(f)
    d["exp"] = e
    frames.append(d)
for n in range(1, 6):
    b = f"claude/git-repo-experiments-f0705v-new-{n}"
    subprocess.run(["git", "fetch", "-q", "origin", b])
    ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", "FETCH_HEAD", f"results_shards/new-{n}"],
                        capture_output=True, text=True).stdout.split()
    for f in ls:
        if f.endswith("raw/runtime.csv") or f.endswith("raw/runtime_k7.csv"):
            txt = subprocess.run(["git", "show", f"FETCH_HEAD:{f}"], capture_output=True, text=True).stdout
            d = pd.read_csv(io.StringIO(txt))
            d["exp"] = "e7t7" if "k7" in f else "e4"
            frames.append(d)
d = pd.concat(frames, ignore_index=True)
d = d[d.pair.isin(PAIRS)]
d["to"] = d.timeout.astype(str).str.lower().eq("true")
d["sweep"] = d.get("sweep").fillna("-") if "sweep" in d else "-"
d.loc[d.exp != "e4", "sweep"] = "-"
d["value"] = d["value"].fillna(0) if "value" in d else 0
g = d.groupby(["exp", "pair", "sweep", "value", "method"]).agg(
    n=("total_s", "size"), mean=("total_s", "mean"), to=("to", "max")).reset_index()
c = g["mean"] * np.minimum(g.n, 3)
c[g.to] = np.minimum(g.n[g.to], 3) * 60.0
g["c"] = c
job = g.groupby(["exp", "pair", "sweep"]).apply(
    lambda x: (x.c.sum() + x.c[x.method == "B2"].sum() + 0.5 * x.c[x.method == "PRIV_EXPL"].sum()) / 3600)
job = job.rename("h").reset_index()
job["ds"] = job.pair.map(lambda p: spec[p]["dataset"])
ds_mean = job.groupby(["ds", "exp", "sweep"]).h.mean()

jobs = []
for p in PAIRS:
    ds = spec[p]["dataset"]
    for exp in ("e4", "e5", "e7t", "e7t7"):
        for sw in (SWEEPS if exp == "e4" else ["-"]):
            hit = job[(job.pair == p) & (job.exp == exp) & (job.sweep == sw)]
            h = float(hit.h.iloc[0]) if len(hit) else float(ds_mean.get((LIKE.get(ds, ds), exp, sw), 0.5))
            jobs.append((max(h, 0.02), exp, p, sw))
jobs.sort(key=lambda j: -j[0])


def makespan(js):
    slots = [0.0] * SLOTS
    for h, *_ in sorted(js, key=lambda j: -j[0]):
        t = heapq.heappop(slots)
        heapq.heappush(slots, t + h)
    return max(slots)


shards = [[] for _ in range(N_SHARDS)]
for j in jobs:
    best = min(range(N_SHARDS), key=lambda s: (makespan(shards[s] + [j]), len(shards[s])))
    shards[best].append(j)
for n, js in enumerate(shards, 1):
    js.sort(key=lambda j: -j[0])
    with open(f"scripts/shards/pv-{n}.jobs", "w") as f:
        f.write("# PREVIEW of the running-time rerun (run with CONFIG=configs/experiments_preview.yaml): 3 repeats,\n"
                "# early stop of the exhaustive searches; every method; 36 refinement pairs + Erica's 10.\n"
                f"# Estimated makespan {makespan(js):.1f} h (4 jobs at a time), longest job first.\n")
        for h, e, p, sw in js:
            f.write(f"{e} {p}" + (f" {sw}" if sw != "-" else "") + "\n")
    print(f"pv-{n}: {len(js)} jobs, est. makespan {makespan(js):.1f} h, work {sum(j[0] for j in js):.1f} h")
print("total work", round(sum(j[0] for j in jobs)), "h; longest jobs", [(round(h, 1), e, p, s) for h, e, p, s in jobs[:4]])
