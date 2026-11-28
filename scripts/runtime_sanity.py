"""Critical checks of the running-time results, aimed at artefacts of mixing machines.

Container restarts move a job to a new machine; cloud machines differ by up to ~30% in speed, while the
runs of one point on one machine differ by ~2.5%.  The comparisons between methods are protected because
every run times all methods on one machine; these checks verify that, and flag anything odd.

A. Points measured on more than one machine (column ``machine``, rows written by the newer code): the
   speed factor between the machines, and whether every method moved by the same factor (the ratios
   between methods must not depend on the machine).
B. Machine change inside a point, also without the column: per run, the time of every method relative
   to its median over the runs; a run where all methods are faster or slower together (> 15%) marks a
   change of machine (or of load).
C. Machine change along a curve: the statistics build of the original route does not depend on k, eps,
   tau or gamma, so its time must stay flat along those sweeps; a step > 15% marks a change of machine.
D. Invariants: OptPEEQ never slower than PEEQ; NonPrivate within 10% of PEEQ; Exhaustive over all views
   within 25% of Exhaustive where the enumeration dominates (> 60 s); the exhaustive searches do not get
   faster with k or |Attrs|, and once at the limit stay at it; the unpruned search never beats the pruned
   one; identical releases; run-to-run spread (CV) below 15% for runs over 0.5 s.
E. With a second results directory: the same points in both, the ratio of their medians per curve, and
   the points that deviate from their curve's ratio by more than 25%.

Usage: python scripts/runtime_sanity.py RESULTS_DIR [OTHER_RESULTS_DIR]
Writes RESULTS_DIR/sanity_flags.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(sys.argv[1])
OTHER = Path(sys.argv[2]) if len(sys.argv) > 2 else None
FLAT = ("k", "epsilon", "tau", "gamma_mult")  # sweeps along which the original-route build is constant
EXH = ("B2", "EXH_ALL", "EXH_NAIVE")
flags = []


def flag(check, where, detail):
    flags.append({"check": check, "where": where, "detail": detail})


def tobool(s):
    return s.astype(str).str.lower().eq("true")


def load(rel, exp):
    p = BASE / rel
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["timeout"] = tobool(d["timeout"])
    d["exp"] = exp
    if "sweep" not in d:
        d["sweep"] = "default" if exp == "e5" else "n_attrs"
    if "value" not in d:
        d["value"] = 0.0
    return d


frames = [x for x in (load("e4/raw/runtime.csv", "e4"), load("e5/raw/default_point.csv", "e5"),
                      load("e7/raw/runtime.csv", "e7t"), load("e7/raw/runtime_k7.csv", "e7t7")) if x is not None]
if not frames:
    sys.exit(f"no raw running-time data under {BASE}")
D = pd.concat(frames, ignore_index=True)
PT = ["exp", "pair", "sweep", "value"]
print(f"rows {len(D)}, points {D.groupby(PT).ngroups}, pairs {D.pair.nunique()}")

# ---------------------------------------------------------------- A: points on several machines
if "machine" in D:
    m = D.dropna(subset=["machine"])
    multi = m.groupby(PT).machine.nunique()
    multi = multi[multi > 1]
    curves = m.groupby(["exp", "pair", "sweep"]).machine.nunique()
    print(f"A. rows with a machine id: {len(m)}; points on >1 machine: {len(multi)}; "
          f"curves on >1 machine: {int((curves > 1).sum())} of {len(curves)}")
    for key in multi.index:
        g = m.set_index(PT).loc[key].reset_index()
        g = g[~g.timeout & (g.total_s > 0.05)]
        med = g.groupby(["machine", "method"]).total_s.median().unstack(0).dropna()
        if med.shape[1] < 2 or med.empty:
            continue
        a, b = med.columns[:2]
        r = med[b] / med[a]
        fac = r.median()
        spread = float(np.max(np.abs(np.log(r / fac))))
        if spread > np.log(1.15):
            flag("A methods moved differently between machines", str(key),
                 f"machine factor {fac:.2f}; per method {r.round(2).to_dict()}")
else:
    print("A. no machine column (rows written by the older code)")

# ---------------------------------------------------------------- B: machine change inside a point
ok = D[~D.timeout & (D.total_s > 0.05)]
rel = ok.assign(rel=ok.total_s / ok.groupby(PT + ["method"]).total_s.transform("median"))
per_run = rel.groupby(PT + ["repeat"]).rel.median().reset_index()
spread = per_run.groupby(PT).rel.agg(lambda x: x.max() / x.min() if len(x) >= 3 else 1.0)
bad = spread[spread > 1.15]
print(f"B. points whose runs shift together by > 15% (machine or load change): {len(bad)} of {len(spread)}")
for key, v in bad.sort_values(ascending=False).head(15).items():
    runs = per_run.set_index(PT).loc[key].sort_values("repeat")
    flag("B runs of a point shift together", str(key),
         f"max/min {v:.2f}; per run {[round(x, 2) for x in runs.rel]}")

# ---------------------------------------------------------------- C: machine change along a curve
e4 = D[(D.exp == "e4") & D.sweep.isin(FLAT) & (D.method == "PRIV_EXPL")]
if len(e4):
    b = e4.groupby(["pair", "sweep", "value"]).build_s.median()
    steps = 0
    for (pair, sw), s in b.groupby(level=[0, 1]):
        s = s.droplevel([0, 1]).sort_index()
        r = s.max() / s.min()
        if r > 1.15:
            steps += 1
            jump = (s / s.shift(1)).dropna()
            flag("C build time not flat along the curve", f"{pair} {sw}",
                 f"max/min {r:.2f}; largest step {jump.abs().max():.2f} at {jump.idxmax()}; build {s.round(2).to_dict()}")
    print(f"C. curves (k, eps, tau, gamma) whose build time is not flat (> 15%): {steps} of {b.groupby(level=[0, 1]).ngroups}")

# ---------------------------------------------------------------- D: invariants
med = D.groupby(PT + ["method"]).agg(t=("total_s", "median"), to=("timeout", "max"), n=("total_s", "size")).reset_index()
w = med.pivot_table(index=PT, columns="method", values="t")
wto = med.pivot_table(index=PT, columns="method", values="to")
if {"PRIV_EXPL", "OPT_PRIV_EXPL"} <= set(w):
    sp = (w.PRIV_EXPL / w.OPT_PRIV_EXPL).dropna()
    print(f"D. OptPEEQ speedup: min {sp.min():.2f}, median {sp.median():.2f}; points where OptPEEQ is slower: {(sp < 1).sum()}")
    for key, v in sp[sp < 1].items():
        flag("D OptPEEQ slower than PEEQ", str(key), f"speedup {v:.2f}")
if {"PRIV_EXPL", "B1"} <= set(w):
    r = (w.B1 / w.PRIV_EXPL).dropna()
    r = r[w.PRIV_EXPL.reindex(r.index) > 0.05]
    out = r[(r < 0.9) | (r > 1.1)]
    print(f"D. NonPrivate / PEEQ: median {r.median():.2f}; outside [0.9, 1.1]: {len(out)}")
    for key, v in out.items():
        flag("D NonPrivate differs from PEEQ by > 10%", str(key), f"ratio {v:.2f}")
if {"B2", "EXH_ALL"} <= set(w):
    both = (wto.B2 == 0) & (wto.EXH_ALL == 0) & (w.B2 > 60)
    r = (w.EXH_ALL / w.B2)[both]
    out = r[(r < 0.8) | (r > 1.25)]
    print(f"D. Exhaustive (all views) / Exhaustive where the enumeration dominates: median {r.median():.2f}, "
          f"range {r.min():.2f}-{r.max():.2f}; outside [0.8, 1.25]: {len(out)}")
    for key, v in out.items():
        flag("D the two exhaustive searches differ by > 25%", str(key), f"ratio {v:.2f}")
for exp, sw in (("e4", "k"), ("e7t7", "n_attrs"), ("e7t", "n_attrs")):
    for meth in ("B2", "EXH_ALL"):
        s = med[(med.exp == exp) & (med.sweep == sw) & (med.method == meth)]
        for pair, g in s.groupby("pair"):
            g = g.sort_values("value")
            t = g.t.to_numpy()
            dec = np.where((t[1:] < 0.7 * t[:-1]) & (t[:-1] > 5))[0]
            for i in dec:
                flag(f"D {meth} faster at a larger {sw}", f"{exp} {pair}",
                     f"{g.value.iloc[i]:g}: {t[i]:.3g}s -> {g.value.iloc[i + 1]:g}: {t[i + 1]:.3g}s")
            to = g.to.to_numpy().astype(bool)
            if to.any() and not to[np.argmax(to):].all():
                flag(f"D {meth} timeout not monotone in {sw}", f"{exp} {pair}",
                     f"timeouts at {list(g.value[to])}")
if {"EXH_NAIVE", "EXH_ALL"} <= set(w):
    r = (w.EXH_NAIVE / w.EXH_ALL)[(wto.EXH_NAIVE == 0) & (wto.EXH_ALL == 0)].dropna()
    r = r[r.index.get_level_values("value") >= 2]
    print(f"D. unpruned faster than pruned (k >= 2): {(r < 0.9).sum()} of {len(r)} points")
    for key, v in r[r < 0.9].items():
        flag("D unpruned exhaustive faster than pruned", str(key), f"ratio {v:.2f}")
ide = BASE / "e5/raw/identity.csv"
if ide.exists():
    i = pd.read_csv(ide)
    bad_i = i[i.identical_runs != i.runs]
    print(f"D. identical releases: {int(i.identical_runs.sum())}/{int(i.runs.sum())}; pairs with a difference: {len(bad_i)}")
    for r in bad_i.itertuples():
        flag("D OptPEEQ release differs from PEEQ", r.pair, f"{r.identical_runs}/{r.runs}")
cv = ok.groupby(PT + ["method"]).total_s.agg(["mean", "std", "size"])
cv = cv[(cv["size"] >= 3) & (cv["mean"] > 0.5)]
cv["cv"] = cv["std"] / cv["mean"]
hi = cv[cv.cv > 0.15]
print(f"D. run-to-run CV (runs > 0.5 s): median {cv.cv.median():.3f}, 90th pct {cv.cv.quantile(.9):.3f}; "
      f"> 15%: {len(hi)} of {len(cv)}")
for key, r in hi.sort_values("cv", ascending=False).head(15).iterrows():
    flag("D run-to-run spread > 15%", str(key), f"CV {r.cv:.2f}, mean {r['mean']:.3g}s, n {int(r['size'])}")

# ---------------------------------------------------------------- E: against another run
if OTHER is not None:
    o = []
    for rel_, exp in (("e4/raw/runtime.csv", "e4"), ("e5/raw/default_point.csv", "e5"),
                      ("e7/raw/runtime.csv", "e7t"), ("e7/raw/runtime_k7.csv", "e7t7")):
        p = OTHER / rel_
        if p.exists():
            x = pd.read_csv(p)
            x["timeout"] = tobool(x["timeout"])
            x["exp"] = exp
            x["sweep"] = x["sweep"] if "sweep" in x else ("default" if exp == "e5" else "n_attrs")
            x["value"] = x["value"] if "value" in x else 0.0
            o.append(x)
    if o:
        O = pd.concat(o, ignore_index=True)
        f = lambda d: d[~d.timeout & (d.total_s > 0.05)].groupby(PT + ["method"]).total_s.median()
        r = (f(D) / f(O)).dropna().rename("ratio").reset_index()
        r["curve_ratio"] = r.groupby(["exp", "pair", "sweep"]).ratio.transform("median")
        r["dev"] = r.ratio / r.curve_ratio
        out = r[(r.dev < 0.8) | (r.dev > 1.25)]
        print(f"E. points in both runs: {len(r)}; ratio of medians (this / other): median {r.ratio.median():.2f}, "
              f"10-90% {r.ratio.quantile(.1):.2f}-{r.ratio.quantile(.9):.2f}; deviating from their curve > 25%: {len(out)}")
        for row in out.sort_values("dev").head(15).itertuples():
            flag("E deviates from the other run", f"{row.exp} {row.pair} {row.sweep}={row.value:g} {row.method}",
                 f"ratio {row.ratio:.2f} vs curve {row.curve_ratio:.2f}")

F = pd.DataFrame(flags)
F.to_csv(BASE / "sanity_flags.csv", index=False)
print(f"\n{len(F)} flags written to {BASE / 'sanity_flags.csv'}")
if len(F):
    print(F.groupby("check").size().to_string())
