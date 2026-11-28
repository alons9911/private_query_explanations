"""OPT and SingleStage with the shared pass of OptPEEQ (one pass per attribute set), at the defaults.

Reviewer question: OptPEEQ computes the statistics of all views on the same attributes in one pass; the
same grouping could speed up OPT and SingleStage, which build the histograms of every view.  Per pair and
repeat, on one machine, one after the other: PEEQ, OptPEEQ, OPT and SingleStage as in E5, then OPT and
SingleStage on the grouped route.  Also checks that the grouped route selects what the direct one selects.

Usage: python scripts/time_grouped_baselines.py OUT.csv [PAIR ...]   (default: the 40 pairs of the paper)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pqde.experiments.common import machine, make_params  # noqa: E402
from pqde.pairs import resolve_pair  # noqa: E402
from pqde.runner import run_method, time_methods  # noqa: E402
from pqde.views import enumerate_views  # noqa: E402

GROUPED_NONE = {"mode": "grouped", "rep": "none", "hist": "eager"}
cfg = yaml.safe_load(open("configs/experiments.yaml"))
d = cfg["defaults"]
REPEATS = int(__import__('os').environ.get('REPEATS', 10))


def main() -> None:
    out = Path(sys.argv[1])
    pairs = sys.argv[2:] or list(cfg["pairs"]) + ["EH1", "EH2", "EH3", "EH5"]
    new = not out.exists()
    f = open(out, "a", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["dataset", "pair", "repeat", "method", "route", "build_s", "mech_s", "total_s", "same_selection",
                    *__import__("pqde.experiments.common", fromlist=["machine"]).machine().keys()])
    for pid in pairs:
        pair = resolve_pair(pid)
        ds, q1, q2 = pair.dataset, pair.q1, pair.q2
        params = make_params(d, len(enumerate_views(ds)), len(ds.explain_attrs))
        for r in range(REPEATS):
            ref = {}
            for o in time_methods(ds, q1, q2, params, methods=("PRIV_EXPL", "OPT_PRIV_EXPL", "OPT", "SINGLE_STAGE"),
                                  seed=int(d["seed"]), repeat=r, gamma_eval=float(d["gamma_eval"]),
                                  timeout_s=float(d["timeout_s"])):
                ref[o.method] = o.selections
                w.writerow([ds.name, pid, r, o.method, "usual", o.build_s, o.mech_s, o.total_s, "", *machine().values()])
            for m in ("OPT", "SINGLE_STAGE"):
                o = run_method(m, ds, q1, q2, params, rng=np.random.default_rng([int(d["seed"]), r]),
                               gamma_eval=float(d["gamma_eval"]), timeout_s=float(d["timeout_s"]), route=GROUPED_NONE)
                same = _key(o.selections) == _key(ref.get(m))
                w.writerow([ds.name, pid, r, m, "grouped", o.build_s, o.mech_s, o.total_s, same, *machine().values()])
            f.flush()
        print(pid, flush=True)
    f.close()


def _key(sel):
    return None if sel is None else sorted((int(v), str(a)) for v, a in sel)


if __name__ == "__main__":
    main()
