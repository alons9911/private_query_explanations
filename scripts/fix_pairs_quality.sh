#!/bin/sh
# Quality suite for the pairs replaced on 2026-11-27 (exact minimal refinements), then merge into results/.
set -e
P="A1 T1 R5 L3 L5 M2 M5"
mkdir -p results_fix
python -m pqde run e2 e3 e6 e8 --pairs $P --out results_fix > results_fix/q1.log 2>&1 &
python -m pqde run e7a e7g --pairs $P --out results_fix > results_fix/q2.log 2>&1 &
wait
python scripts/append_pairs.py results_fix e2 e3 e6 e8 e7
python scripts/rescore_bruteforce.py $P > results_fix/rescore.log 2>&1
python - <<'PY'
import pandas as pd
P = {"A1", "T1", "R5", "L3", "L5", "M2", "M5"}
for f in ("results/rescored/review_numbers.csv", "results/rescored/coverage_tau.csv"):
    d = pd.read_csv(f); d[~d.pair.isin(P)].to_csv(f, index=False)
PY
python scripts/review_numbers.py > results_fix/review.log 2>&1
date > results_fix/DONE
