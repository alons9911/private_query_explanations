"""Numbers for the running-time paragraph, from the raw CSVs of one results directory.

Prints, for our refinement pairs (configs/experiments.yaml) and for Erica's pairs separately:
* E5, the defaults: per dataset the mean over pairs of each method's median end-to-end time; the
  speedup of OPT_PRIV_EXPL over PRIV_EXPL per pair; OPT and SINGLE_STAGE against PRIV_EXPL; the
  extrapolated time of EXH_NAIVE; identical releases of PRIV_EXPL and OPT_PRIV_EXPL.
* E4: the exhaustive searches against k (time at k = 6, 7, first k at the limit), EXH_NAIVE's measured
  and extrapolated times; growth from 10% to all views, with tau, with N.
* E7 at k = 7: the first |Attrs| where the exhaustive searches reach the limit.
A timeout counts at the limit (30 min); EXH_NAIVE's extrapolated times are reported apart.

Usage: python scripts/runtime_numbers.py [results_dir]     (default results/)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
OURS = list(yaml.safe_load(open("configs/experiments.yaml"))["pairs"])
ERICA = ["EA1", "EA2", "EA4", "EC1", "EC2", "EC3", "EH1", "EH2", "EH3", "EH5"]
ORDER = ["adult", "acsincome", "tax", "compas", "law", "meps", "adult_erica", "compas_erica", "healthcare_erica"]
M = ["PRIV_EXPL", "OPT_PRIV_EXPL", "B1", "B2", "OPT", "SINGLE_STAGE", "EXH_ALL", "EXH_NAIVE"]
YEAR = 365.25 * 86400


def tobool(s):
    return s.astype(str).str.lower().eq("true")


def read(rel):
    p = BASE / rel
    if not p.exists():
        print(f"(missing {p})")
        return None
    d = pd.read_csv(p)
    for c in ("timeout", "inferred"):
        if c in d:
            d[c] = tobool(d[c])
    return d


def ds_order(idx):
    return [d for d in ORDER if d in set(idx)]


def report(group: str, pairs: list[str]) -> None:
    print(f"\n######## {group}: {len(pairs)} pairs")
    dp = read("e5/raw/default_point.csv")
    if dp is not None:
        dp = dp[dp.pair.isin(pairs)]
        print(f"E5 pairs measured: {dp.pair.nunique()}")
        per = dp.groupby(["dataset", "pair", "method"]).total_s.median().unstack()
        tab = per.groupby(level=0).mean().reindex(ds_order(per.index.get_level_values(0)))
        print("E5 mean over pairs of the median time (s):")
        print(tab[[m for m in M if m in tab]].to_string(float_format=lambda v: f"{v:.3g}"))
        if {"PRIV_EXPL", "OPT_PRIV_EXPL"} <= set(per):
            sp = per.PRIV_EXPL / per.OPT_PRIV_EXPL
            print(f"OptPEEQ speedup per pair: {sp.min():.1f}-{sp.max():.1f}x, median {sp.median():.1f}x")
        for m in ("OPT", "SINGLE_STAGE"):
            if m in per:
                r = per[m] / per.PRIV_EXPL
                print(f"{m} / PEEQ per pair: {r.min():.2f}-{r.max():.2f}, median {r.median():.2f}")
        if "EXH_ALL" in per and "B2" in per:
            ok = ~dp[dp.method.isin(["B2", "EXH_ALL"])].groupby("pair").timeout.max()
            r = (per.EXH_ALL / per.B2)[ok.reindex(per.index.get_level_values(1)).to_numpy()]
            print(f"EXH_ALL / Exhaustive per pair (no timeout): {r.min():.2f}-{r.max():.2f}, median {r.median():.2f}")
        nv = dp[dp.method == "EXH_NAIVE"]
        if len(nv) and "estimated_s" in nv:
            est = nv.groupby(["dataset", "pair"]).estimated_s.median().groupby(level=0).median()
            print("EXH_NAIVE at the defaults, extrapolated (years, median over pairs):",
                  {d: f"{est[d] / YEAR:.3g}" for d in ds_order(est.index)})
    ide = read("e5/raw/identity.csv")
    if ide is not None:
        ide = ide[ide.pair.isin(pairs)]
        print(f"identical releases (PEEQ vs OptPEEQ): {int(ide.identical_runs.sum())}/{int(ide.runs.sum())} runs, "
              f"{ide.pair.nunique()} pairs")
    e4 = read("e4/raw/runtime.csv")
    if e4 is not None:
        e4 = e4[e4.pair.isin(pairs)]
        print(f"E4 pairs measured: {e4.pair.nunique()}; sweeps: {e4.groupby('sweep').pair.nunique().to_dict()}")
        k = e4[e4.sweep == "k"]
        for m in ("B2", "EXH_ALL"):
            s = k[k.method == m]
            med = s.groupby(["dataset", "pair", "value"]).total_s.median().groupby(["dataset", "value"]).agg(["min", "max"])
            to = s[s.timeout].groupby("dataset").value.min()
            for kk in (6, 7):
                if kk in med.index.get_level_values(1):
                    x = med.xs(kk, level=1)
                    print(f"{m} at k={kk}: per pair {x['min'].min():.3g}-{x['max'].max():.3g} s")
            print(f"{m}: first k at the limit by dataset: {to.reindex(ds_order(to.index)).to_dict()}")
        nv = k[k.method == "EXH_NAIVE"]
        if len(nv):
            meas = nv[~nv.inferred & ~nv.timeout].groupby("value").total_s.agg(["median", "max"])
            print("EXH_NAIVE measured (s) by k:", meas.round(3).to_dict("index"))
            est = nv[nv.inferred].groupby("value").b2_estimated_s.median() / YEAR
            print("EXH_NAIVE extrapolated (years, median) by k:", {int(i): f"{v:.3g}" for i, v in est.items()})

        def growth(sweep, lo, hi, ms=("PRIV_EXPL", "OPT_PRIV_EXPL", "OPT", "SINGLE_STAGE", "B1")):
            s = e4[(e4.sweep == sweep) & ~e4.timeout]
            per = s.groupby(["pair", "value", "method"]).total_s.median().unstack()
            out = {}
            for m in ms:
                if m not in per:
                    continue
                g = (per[m].xs(hi, level=1) / per[m].xs(lo, level=1)).dropna()
                out[m] = f"{g.min():.2f}-{g.max():.2f}x (median {g.median():.2f})"
            print(f"growth {sweep} {lo} -> {hi}:", out)
        growth("view_fraction", 0.1, 1.0)
        growth("data_fraction", 0.1, 1.0)
        t = e4[e4.sweep == "tau"]
        if len(t):
            tmax = t.groupby("pair").value.transform("max")
            t = t.assign(value=np.where(t.value == tmax, -1, t.value))
            e4 = pd.concat([e4[e4.sweep != "tau"], t])
            growth("tau", 15, -1, ("PRIV_EXPL", "OPT_PRIV_EXPL", "B1"))
    for name in ("e7/raw/runtime_k7.csv",):
        e7 = read(name)
        if e7 is None:
            continue
        e7 = e7[e7.pair.isin(pairs)]
        for m in ("B2", "EXH_ALL"):
            s = e7[e7.method == m]
            to = s[s.timeout].groupby("dataset").value.min()
            mx = s.groupby("dataset").value.max()
            print(f"E7 k=7 {m}: first |Attrs| at the limit: {to.reindex(ds_order(to.index)).to_dict()} "
                  f"(largest |Attrs|: {mx.reindex(ds_order(mx.index)).to_dict()})")


HEALTHCARE = ["EH1", "EH2", "EH3", "EH5"]
report("pairs of the paper (ours and Healthcare; the Erica copies of Adult and COMPAS are out, user 2026-11-28)",
       OURS + HEALTHCARE)
report("Healthcare", HEALTHCARE)
