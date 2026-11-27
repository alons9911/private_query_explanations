"""Split the running-time rerun (E4, E5, E7t, E7t7; every method of pqde.runner) into cloud shards.

One job = one experiment on one pair (all methods of a pair in one process, on one machine).
Job lengths are estimated from the earlier runs per dataset (hours, with the B2 part counted twice
for EXH_ALL); jobs are assigned longest first to the shard whose simulated makespan (4 jobs at a
time, in file order) grows least.  Writes scripts/shards/rt-<n>.jobs.

Usage: python scripts/plan_runtime_shards.py [n_shards]
"""
import heapq
import sys

import yaml

N_SHARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
SLOTS = 4
EST = {  # e4, e5, e7t, e7t7 (hours)
    "adult": (12.3, 0.1, 0.2, 20.7), "acsincome": (28.2, 1.0, 3.7, 19.9), "tax": (11.2, 0.1, 0.4, 9.2),
    "compas": (11.2, 0.1, 0.1, 21.6), "law": (7.2, 0.1, 0.1, 1.7), "meps": (12.5, 0.1, 0.1, 24.8),
    "adult_erica": (12.3, 0.1, 0.2, 20.7), "compas_erica": (11.2, 0.1, 0.1, 21.6),
    "healthcare_erica": (8.0, 0.1, 0.1, 10.0),
}
ERICA = ["EA1", "EA2", "EA4", "EC1", "EC2", "EC3", "EH1", "EH2", "EH3", "EH5"]
pairs = list(yaml.safe_load(open("configs/experiments.yaml"))["pairs"]) + ERICA
spec = yaml.safe_load(open("configs/pairs.yaml"))
spec = spec.get("pairs", spec)
jobs = [(EST[spec[p]["dataset"]][i], e, p) for p in pairs for i, e in enumerate(("e4", "e5", "e7t", "e7t7"))]
jobs.sort(key=lambda j: -j[0])


def makespan(js):
    slots = [0.0] * SLOTS
    for h, _, _ in sorted(js, key=lambda j: -j[0]):
        t = heapq.heappop(slots) if len(slots) == SLOTS else 0.0
        heapq.heappush(slots, t + h)
    return max(slots)


shards = [[] for _ in range(N_SHARDS)]
for j in jobs:
    best = min(range(N_SHARDS), key=lambda s: (makespan(shards[s] + [j]), len(shards[s])))
    shards[best].append(j)
for n, js in enumerate(shards, 1):
    js.sort(key=lambda j: -j[0])
    with open(f"scripts/shards/rt-{n}.jobs", "w") as f:
        f.write("# Running-time rerun, every method (PEEQ, OptPEEQ, NonPrivate, Exhaustive, B3, OPT, SingleStage,\n"
                "# EXH_ALL, EXH_NAIVE), our 36 refinement pairs + Erica's 10 pairs; approved 2026-11-27.\n"
                f"# Estimated makespan {makespan(js):.0f} h (4 jobs at a time), longest job first.\n")
        for h, e, p in js:
            f.write(f"{e} {p}\n")
    print(f"rt-{n}: {len(js)} jobs, est. makespan {makespan(js):.1f} h, work {sum(h for h, _, _ in js):.0f} h")
print("total work", round(sum(j[0] for j in jobs)), "h; longest job", jobs[0])
