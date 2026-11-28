"""Figures for the experiments section of the paper, redrawn from the raw CSVs.

Sized for the ACM two-column format (column 3.33 in, text width 7.0 in) and
written as PDF into ``paper/figures/exp/``.  Every number in a figure comes from
``results/<exp>/raw/*.csv`` (or the summaries the experiment wrote next to them),
so ``python -m pqde.paper_figures`` can be re-run whenever the results change.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

from . import plotting as P  # noqa: E402  (palette and base style)
from .experiments import e4_scalability  # noqa: E402

import os  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / os.environ.get("PQDE_RESULTS", "results")  # e.g. results_preview (provisional runs)


def _method_names() -> dict[str, str]:
    """Display names of the methods, read from paper/macros.tex (\\PrivExpl, \\Bone, ...), so that a
    rename there reaches the legends once the figures are redrawn."""
    import re

    tex = (ROOT / "paper" / "macros.tex").read_text()
    pat = r"\\newcommand\{\\(\w+)\}\{\\(?:textsf|ensuremath)\{(?:\\mathsf\{)?([^{}]+)\}"
    return {m.group(1): m.group(2) for m in re.finditer(pat, tex)}


NAME = _method_names()
OUT = ROOT / os.environ.get("PQDE_FIG_OUT", "paper/figures/exp")

DS_ORDER = ["adult", "acsincome", "tax", "compas", "law", "meps"]  # refinement pairs only (2026-11-27)
# CQA and contrast datasets, out of the experiments for now: "tax_dirty", "hospital", "ipums"
DS_TITLE = {"adult": "Adult", "acsincome": "ACSIncome", "tax": "Tax", "compas": "COMPAS", "law": "Law Students",
            "meps": "MEPS", "tax_dirty": "Tax-dirty (CQA)",
            "hospital": "Hospital (CQA)", "ipums": "IPUMS-CPS (contrast)"}
SURF = "#ffffff"
# C4 is a copy of H1 and R6 a copy of T2 (two searches returned the same pair); each is counted once
EXCLUDE = {"C4", "R6"}

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 6.5, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "legend.fontsize": 6.5, "lines.linewidth": 1.4, "lines.markersize": 3.5, "grid.linewidth": 0.5,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5,
    "ytick.major.size": 2.5, "pdf.fonttype": 42,
})


def _save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.pdf"
    fig.savefig(p, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(p.with_suffix(".png"), dpi=200, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return p


def _drop(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df.pair.isin(EXCLUDE)] if "pair" in df else df


def _datasets(df: pd.DataFrame) -> list[str]:
    have = set(df.dataset)
    return [d for d in DS_ORDER if d in have]


def _logx(ax, xs):
    xs = np.asarray(xs, dtype=float)
    if (xs <= 0).any():
        pos = xs[xs > 0]
        ax.set_xscale("symlog", linthresh=float(pos.min()), linscale=0.4)
    else:
        ax.set_xscale("log")


# ----------------------------------------------------------------------------- quality (E2 + E6)

QUALITY_SERIES = [  # (column, label, colour, marker, linestyle)
    ("ratio_B3_mean", "ApproxRatio vs filtered optimum", P.BLUE, "o", "-"),
    ("ratio_B1_mean", "ApproxRatio vs B1", P.BLUE, "o", ":"),
    ("attr_precision_B3_mean", "attribute precision", P.ORANGE, "s", "-"),
    ("precision_at_k_B3_mean", "precision@k", P.AQUA, "^", "-"),
]


def _quality_row(axes, summ: pd.DataFrame, dss: list[str], xlabel: str, logx: bool, first_row: bool,
                 xfmt=None):
    for j, ds in enumerate(dss):
        ax = axes[j]
        sub = summ[summ.dataset == ds].groupby("value", as_index=False).mean(numeric_only=True).sort_values("value")
        for col, lab, c, mk, ls in QUALITY_SERIES:
            ax.plot(sub.value, sub[col], color=c, marker=mk, linestyle=ls, label=lab,
                    markerfacecolor=SURF if ls == ":" else c)
        if logx:
            _logx(ax, sub.value)
        top = float(np.nanmax(sub[[c for c, *_ in QUALITY_SERIES]].to_numpy()))
        ax.set_ylim(0, max(1.1, top + 0.08))  # keep every point (ratios to B1 can exceed 1) inside the frame
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.axhline(1.0, color=P.MUTED, linewidth=0.5, zorder=0)
        if j:
            ax.set_yticklabels([])
        if first_row:
            ax.set_title(f"{DS_TITLE[ds]} ({summ[summ.dataset == ds].pair.nunique()})")
        ax.set_xlabel(xlabel)
        if xfmt:
            xfmt(ax, sub.value)


def _rescored(name: str) -> pd.DataFrame:
    """Rows of results/rescored/<name>.csv (scored against the brute force at the default gamma)."""
    acc = ROOT / os.environ.get("PQDE_ACC_RESULTS", "results")  # accuracy: always the main results by default
    df = pd.read_csv(acc / "rescored" / f"{name}.csv")
    if "dataset" not in df or df.dataset.isna().any():  # the B1 rows carry the pair only
        df["dataset"] = df.pair.map(pd.read_csv(acc / "rescored" / "bf.csv").set_index("pair").dataset)
    return _drop(df)


def _curve(df: pd.DataFrame, x: str, col: str) -> pd.DataFrame:
    """Per dataset and x: mean over the pairs of the per-pair mean."""
    pp = df.groupby(["dataset", "pair", x], as_index=False)[col].mean()
    return pp.groupby(["dataset", x], as_index=False)[col].mean()


# (source, x column, value column, label, colour, marker, linestyle)
BF_SERIES_EPS = [("e2", "value", "ratio_BF", NAME["sys"], P.BLUE, "o", "-"),
                 ("e2_b1", "value", "ratio_BF", NAME['Bone'], P.BLUE, "o", ":"),
                 ("fixed", "epsilon", "ratio_BF", NAME["sys"] + r", $\gamma$ fixed", P.MAGENTA, "D", "--"),
                 ("single", "epsilon", "ratio_BF", NAME["SingleStage"], P.AQUA, "^", "--"),
                 ("e2", "value", "attr_at_k_BF", f"attribute@k ({NAME['sys']})", P.ORANGE, "s", "-")]
BF_SERIES_GAMMA = [("e6", "value", "ratio_BF", NAME["sys"], P.BLUE, "o", "-"),
                   ("e6_b1", "value", "ratio_BF", NAME['Bone'], P.BLUE, "o", ":"),
                   ("e6", "value", "attr_at_k_BF", f"attribute@k ({NAME['sys']})", P.ORANGE, "s", "-")]


def fig_quality() -> Path:
    """ApproxRatio against the brute force (default gamma) and attribute@k, against eps and gamma."""
    src = {"e2": _rescored("e2"), "e2_b1": _rescored("e2_b1"), "e6": _rescored("e6"), "e6_b1": _rescored("e6_b1")}
    comp = _rescored("e8_competitors")
    src["single"] = comp[comp.method == "SingleStage"]
    src["fixed"] = _rescored("e8_fixed_gamma")
    dss = _datasets(src["e2"])
    fig, axes = plt.subplots(2, len(dss), figsize=(7.05, 2.75), squeeze=False, sharex="row")
    rows = [(BF_SERIES_EPS, r"privacy budget $\epsilon$", [0.1, 1, 10], ["0.1", "1", "10"]),
            (BF_SERIES_GAMMA, r"$\gamma$ / Eq. (14) value", [0, 0.1, 1, 10], ["0", ".1", "1", "10"])]
    for r, (series, xlabel, ticks, ticklabels) in enumerate(rows):
        for j, ds in enumerate(dss):
            ax = axes[r, j]
            for name, x, col, lab, c, mk, ls in series:
                cv = _curve(src[name][src[name].dataset == ds], x, col).sort_values(x)
                ax.plot(cv[x], cv[col], color=c, marker=mk, linestyle=ls, label=lab,
                        markerfacecolor=SURF if ls != "-" else c)
                _logx(ax, cv[x])
            ax.set_xticks(ticks)
            ax.set_xticklabels(ticklabels)
            ax.set_ylim(0, 1.05)
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.axhline(1.0, color=P.MUTED, linewidth=0.5, zorder=0)
            ax.axvspan(0.85, 1.18, color=P.MUTED, alpha=0.18, linewidth=0, zorder=0)
            if j:
                ax.set_yticklabels([])
            if r == 0:
                ax.set_title(f"{DS_TITLE[ds]} ({src['e2'][src['e2'].dataset == ds].pair.nunique()})")
            ax.set_xlabel(xlabel)
        axes[r, 0].set_ylabel("score")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 1.06))
    fig.tight_layout(h_pad=0.6, w_pad=0.4)
    return _save(fig, "quality")


# ----------------------------------------------------------------------------- view stage (E3)

def fig_view_stage() -> Path:
    vs = _drop(pd.read_csv(RES / "e3" / "view_stage_summary.csv"))
    fig, ax = plt.subplots(figsize=(3.3, 1.75))
    colours = [P.BLUE, P.ORANGE, P.AQUA, P.YELLOW, P.MAGENTA, "#6250d6"]
    markers = ["o", "s", "^", "D", "P", "v"]
    for i, ds in enumerate(_datasets(vs)):
        sub = vs[vs.dataset == ds].groupby("eps_P", as_index=False).overlap.mean()
        ax.plot(sub.eps_P, sub.overlap, color=colours[i], marker=markers[i], label=DS_TITLE[ds].split(" (")[0])
    ax.set_xscale("log")
    ax.axvline(1 / 3, color=P.MUTED, linewidth=0.6, linestyle="--", zorder=0)
    ax.set_xlabel(r"view-stage budget $\epsilon_P$ (default $1/3$)")
    ax.set_ylabel(r"overlap with exact top-$\tau$")
    ax.set_ylim(0, 1.03)
    ax.legend(ncol=2, loc="lower right", handlelength=1.5, columnspacing=0.8)
    fig.tight_layout()
    return _save(fig, "view_stage")


# ----------------------------------------------------------------------------- running time (E4)

SWEEPS = [("k", r"$k$", False), ("data_fraction", r"$N$ (fraction)", False), ("epsilon", r"$\epsilon$", True),
          ("view_fraction", r"$|\mathcal{P}|$ (fraction)", False), ("tau", r"$\tau$", True),
          ("gamma_mult", r"$\gamma$ / Eq. (14)", True)]
# B3 is not used in the paper; PQDE_RT_METHODS (comma-separated) overrides the methods drawn
RT_METHODS = tuple(os.environ.get("PQDE_RT_METHODS", "PRIV_EXPL,B1,B2,OPT_PRIV_EXPL").split(","))
RT_LABEL = {"PRIV_EXPL": NAME["sys"], "B1": NAME["Bone"], "B2": NAME["Btwo"], "B3": NAME["Bthree"],
            "OPT_PRIV_EXPL": NAME["sysopt"], "OPT": NAME["BF"], "SINGLE_STAGE": NAME["SingleStage"],
            "EXH_ALL": NAME.get("TopKExh", "TopKExhaustive"), "EXH_NAIVE": NAME.get("FullExh", "FullExhaustive")}


def _rt_panel(ax, sub: pd.DataFrame, x: str, logx: bool, limit: float, logy: bool = True):
    for m in RT_METHODS:
        d = sub[sub.method == m].sort_values(x)
        if d.empty:
            continue
        to = d.timeout.astype(bool)
        c, mk = P.METHOD_COLORS[m], P.METHOD_MARKERS[m]
        ax.plot(d[x][~to], d.total_s[~to], color=c, marker=mk, label=RT_LABEL[m],
                linewidth=1.8 if m == "PRIV_EXPL" else 1.2, zorder=3 if m == "PRIV_EXPL" else 2,
                linestyle="-")
        if to.any():
            xs = list(d[x][~to].tail(1)) + list(d[x][to])
            ys = list(d.total_s[~to].tail(1)) + [limit] * int(to.sum())
            ax.plot(xs, ys, color=c, linestyle=":", linewidth=1.0)
            ax.plot(d[x][to], [limit] * int(to.sum()), linestyle="none", marker="x", color=c, markersize=5,
                    markeredgewidth=1.4, label=f"{RT_LABEL[m]} timeout")
    if logy:
        ax.set_yscale("log")
    else:
        ax.set_ylim(bottom=0)
    if logx:
        _logx(ax, sub[x])


def fig_runtime_grid(raw_path: Path | None = None) -> Path:
    raw = pd.read_csv(raw_path or RES / "e4" / "raw" / "runtime.csv")
    raw = _drop(raw).copy()
    # tau = "all" is |P| of each pair, which differs between the pairs of a dataset (contrasts drop
    # the group attribute): put it at one point, the mean |P| of the dataset
    is_all = (raw.sweep == "tau") & (raw.value == raw.groupby("pair").P.transform("max"))
    raw.loc[is_all, "value"] = raw.loc[is_all, "dataset"].map(
        raw[is_all].groupby("dataset").value.mean().round())
    pts = e4_scalability.points(raw)
    limit = float(json.loads((RES / "e4" / "metadata.json").read_text()).get("timeout_s", 60)) \
        if (RES / "e4" / "metadata.json").exists() else 60.0
    dss = _datasets(pts)
    keep = os.environ.get("PQDE_RT_SWEEPS")  # e.g. k,data_fraction,view_fraction,tau (eps, gamma: no effect on time)
    sweeps = [s for s in SWEEPS if s[0] in set(pts.sweep) and (not keep or s[0] in keep.split(","))]
    EXH = ["B2", "EXH_ALL", "EXH_NAIVE", "EXH_TOPTAU"]
    # PQDE_RT_SPLIT_K=1: k in two columns, the other methods (linear axis) and the exhaustive searches (log axis)
    split_k = bool(os.environ.get("PQDE_RT_SPLIT_K")) and any(s[0] == "k" for s in sweeps)
    cols = []  # (data sweep, label, log x, methods: "all" / "fast" / "exh")
    for sw, xl, logx in sweeps:
        if sw == "k" and split_k:
            cols += [(sw, xl, logx, "fast"), (sw, xl + ", exhaustive searches", logx, "exh")]
        else:
            cols.append((sw, xl, logx, "all"))
    # PQDE_RT_SCALE=linear: a linear y axis of its own in every panel but k (log: the exhaustive searches),
    # so that the growth of the other methods shows; default: log, one y axis per row
    linear = os.environ.get("PQDE_RT_SCALE", "log") == "linear"
    fig, axes = plt.subplots(len(dss), len(cols), figsize=(7.05, 1.12 * len(dss) + 0.35), squeeze=False,
                             sharey=False if linear else "row")
    plain = FuncFormatter(lambda v, _: f"{v:g}")
    xticks = {"k": [2, 4, 6, 8, 10], "epsilon": [0.1, 1, 10], "tau": [5, 50, 500], "gamma_mult": [0, 0.1, 1, 10]}
    for i, ds in enumerate(dss):
        for j, (sw, xl, logx, which) in enumerate(cols):
            ax = axes[i, j]
            sub = pts[(pts.dataset == ds) & (pts.sweep == sw)].rename(columns={"value": sw})
            if sw == "data_fraction":
                sub = sub[sub[sw] <= 1.0]
            logy = not linear or (sw == "k" and which != "fast")
            if which == "fast" or (os.environ.get("PQDE_RT_EXH_K_ONLY") and sw != "k"):
                sub = sub[~sub.method.isin(EXH)]  # exhaustive searches in their own k column (or the k column only)
            elif which == "exh":
                sub = sub[sub.method.isin(EXH)]
            _rt_panel(ax, sub, sw, logx, limit, logy=logy)
            if logy:
                ax.axhline(limit, color=P.MUTED, linewidth=0.5, linestyle=":", zorder=0)
                ax.yaxis.set_major_formatter(plain)
                ax.yaxis.set_minor_formatter(NullFormatter())
            else:
                ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=4))
                ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            if sw in xticks:
                ax.set_xticks(xticks[sw])
                ax.xaxis.set_major_formatter(plain)
                ax.xaxis.set_minor_formatter(NullFormatter())
            if sw == "gamma_mult":
                ax.set_xlim(left=0)
            if i == 0:
                ax.set_title(xl)
            if i == len(dss) - 1:
                ax.set_xlabel(xl)
            if j == 0:
                ax.set_ylabel(DS_TITLE[ds].split(" (")[0] + "\ntime (s)", fontsize=6.5)
    handles, labels = [], []
    for ax in axes.ravel():
        for h, lab in zip(*ax.get_legend_handles_labels()):
            if lab not in labels:
                handles.append(h)
                labels.append(lab)
    jlog = next((j for j, c in enumerate(cols) if not linear or (c[0] == "k" and c[3] != "fast")), None)
    for i in range(len(dss) if jlog is not None else 0):  # y ticks of the log column: 1-3-10 steps, or decades
        lo, hi = axes[i, jlog].get_ylim()
        subs = (1.0,) if hi / max(lo, 1e-12) > 1e4 else (1.0, 3.0)
        axes[i, jlog].yaxis.set_major_locator(LogLocator(base=10, subs=subs, numticks=12))
        axes[i, jlog].yaxis.set_major_formatter(plain)
    rows = 1 if len(labels) <= 7 else 2  # many methods: the legend takes two rows
    fig.tight_layout(h_pad=0.25, w_pad=0.3, rect=(0, 0, 1, 0.975 if rows == 1 else 0.95))
    fig.legend(handles, labels, loc="upper center", ncol=-(-len(labels) // rows), bbox_to_anchor=(0.5, 1.01))
    return _save(fig, "runtime_grid")


# ----------------------------------------------------------------------------- E5: methods, B2 growth

def fig_runtime_methods() -> Path:
    dp = _drop(pd.read_csv(RES / "e5" / "raw" / "default_point.csv"))
    per_pair = dp.groupby(["dataset", "pair", "method"], as_index=False).agg(total_s=("total_s", "median"),
                                                                             timeout=("timeout", "max"))
    g = per_pair.groupby(["dataset", "method"], as_index=False).agg(total_s=("total_s", "mean"),
                                                                    timeout=("timeout", "mean"))
    dss = _datasets(g)
    methods = ([m for m in RT_METHODS if m in set(g.method)] if "PQDE_RT_METHODS" in os.environ
               else ["PRIV_EXPL", "OPT_PRIV_EXPL", "B1", "B2", "B3"])
    growth = _drop(pd.read_csv(RES / "e5" / "raw" / "b2_growth.csv"))
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.05, 1.75), gridspec_kw={"width_ratios": [1.9, 1]})
    w = 0.8 / len(methods)
    x = np.arange(len(dss))
    for i, m in enumerate(methods):
        vals = [float(g[(g.dataset == d) & (g.method == m)].total_s.mean()) for d in dss]
        tos = [float(g[(g.dataset == d) & (g.method == m)].timeout.mean()) for d in dss]
        bars = a.bar(x + (i - (len(methods) - 1) / 2) * w, vals, w * 0.88, color=P.METHOD_COLORS[m], label=RT_LABEL[m])
        for bx, t in zip(bars, tos):
            if t > 0:
                bx.set_hatch("////")
                bx.set_edgecolor(SURF)
    a.set_yscale("log")
    a.set_xticks(x)
    a.set_xticklabels([DS_TITLE[d].split(" (")[0] for d in dss])
    a.set_ylabel("end-to-end time (s)")
    a.legend(ncol=min(len(methods), 5), loc="upper center", bbox_to_anchor=(0.5, 1.2 if len(methods) <= 5 else 1.45),
             handlelength=1.2, columnspacing=0.9)
    a.grid(axis="x", visible=False)
    colours = [P.BLUE, P.ORANGE, P.AQUA, P.YELLOW, P.MAGENTA, "#6250d6"]
    markers = ["o", "s", "^", "D", "P", "v"]
    for i, ds in enumerate(_datasets(growth)):
        sub = growth[growth.dataset == ds].groupby("pool_size", as_index=False).agg(
            b2=("b2_total_s", "mean"), to=("timeout", "max"))
        ok = ~sub.to.astype(bool)
        b.plot(sub.pool_size[ok], sub.b2[ok], color=colours[i], marker=markers[i],
               label=DS_TITLE[ds].split(" (")[0])
        if (~ok).any():
            b.plot(sub.pool_size[~ok], sub.b2[~ok], linestyle="none", marker="x", color=colours[i], markersize=5)
    b.set_yscale("log")
    b.set_xlabel("B2 candidate pool size")
    b.set_ylabel("B2 time (s)")
    b.legend(ncol=2, fontsize=5.5, loc="lower right", handlelength=1.2, columnspacing=0.6)
    fig.tight_layout(w_pad=1.0)
    return _save(fig, "runtime_methods")


# ----------------------------------------------------------------------------- E7: |Attrs|

def fig_attrs() -> Path:
    """Top: end-to-end time against |Attrs| (median of the 10 runs, one per attribute order, mean over
    the runtime pairs). Bottom: accuracy against |Attrs| (40 runs per point, mean over all pairs)."""
    rt = _drop(pd.read_csv(RES / "e7" / "raw" / "runtime.csv"))
    acc = _rescored("e7")
    limit = 1800.0
    per = rt.groupby(["dataset", "pair", "value", "method"], as_index=False).agg(
        total_s=("total_s", "median"), timeout=("timeout", "max"))
    pts = per.groupby(["dataset", "value", "method"], as_index=False).agg(total_s=("total_s", "mean"),
                                                                       timeout=("timeout", "max"))
    asum = acc.groupby(["dataset", "pair", "value"], as_index=False)[["ratio_BF", "attr_at_k_BF"]].mean()
    dss = [d for d in DS_ORDER if d in set(pts.dataset) | set(asum.dataset)]
    fig, axes = plt.subplots(2, len(dss), figsize=(7.05, 2.9), squeeze=False)
    plain = FuncFormatter(lambda v, _: f"{v:g}")
    k7_path = RES / "e7" / "raw" / "runtime_k7.csv"
    k7 = None
    if k7_path.exists():  # B2 at k = 7, where its search grows fastest with |Attrs|
        r7 = _drop(pd.read_csv(k7_path))
        k7m = os.environ.get("PQDE_K7_METHOD", "B2")  # the exhaustive search drawn at k = 7
        r7 = r7[r7.method == k7m].groupby(["dataset", "pair", "value"], as_index=False).agg(
            total_s=("total_s", "median"), timeout=("timeout", "max"))
        k7 = r7.groupby(["dataset", "value"], as_index=False).agg(total_s=("total_s", "mean"), timeout=("timeout", "max"))
    for j, ds in enumerate(dss):
        ax = axes[0, j]
        sub = pts[pts.dataset == ds].rename(columns={"value": "n"})
        _rt_panel(ax, sub, "n", False, limit)
        allt = list(sub.total_s)
        if k7 is not None and (k7.dataset == ds).any():
            d7 = k7[k7.dataset == ds].sort_values("value")
            to = d7.timeout.astype(bool)
            k7m = os.environ.get("PQDE_K7_METHOD", "B2")
            c = P.METHOD_COLORS[k7m]
            ax.plot(d7.value[~to], d7.total_s[~to], color=c, linestyle="--", marker="^", markerfacecolor=SURF,
                    linewidth=1.0, label=RT_LABEL[k7m] + ", $k=7$")
            if to.any():
                ax.plot(list(d7.value[~to].tail(1)) + list(d7.value[to]), list(d7.total_s[~to].tail(1)) + [limit] * int(to.sum()),
                        color=c, linestyle=":", linewidth=1.0)
                ax.plot(d7.value[to], [limit] * int(to.sum()), linestyle="none", marker="x", color=c, markersize=5,
                        markeredgewidth=1.4, label=f"{RT_LABEL[k7m]} timeout")
            allt += list(d7.total_s)
        lo, hi = float(min(allt)) / 1.5, float(max(allt)) * 1.5
        if hi / lo < 10:  # at least one decade, so that run-to-run noise does not read as a trend
            mid = (lo * hi) ** 0.5
            lo, hi = mid / 10 ** 0.5, mid * 10 ** 0.5
        ax.set_ylim(lo, hi)
        wide = np.log10(hi / lo) > 2.5  # over several decades, label the decades only
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0,) if wide else (1.0, 2.0, 5.0), numticks=10))
        ax.yaxis.set_major_formatter(plain)
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_title(f"{DS_TITLE[ds]}")
        if j == 0:
            ax.set_ylabel("time (s)")
        ax = axes[1, j]
        sub = asum[asum.dataset == ds].groupby("value", as_index=False).mean(numeric_only=True).sort_values("value")
        for col, lab, c, mk in (("ratio_BF", f"ApproxRatio ({NAME['sys']})", P.BLUE, "o"),
                                ("attr_at_k_BF", f"attribute@k ({NAME['sys']})", P.ORANGE, "s")):
            ax.plot(sub.value, sub[col], color=c, marker=mk, label=lab)
        ax.set_ylim(0, 1.1)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.axhline(1.0, color=P.MUTED, linewidth=0.5, zorder=0)
        if j:
            ax.set_yticklabels([])
        ax.set_xlabel(r"$|\mathit{Attrs}|$")
        for a in axes[:, j]:
            a.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=5))
    def legend_of(axs):
        hs, ls = [], []
        for ax in axs:
            for h, lab in zip(*ax.get_legend_handles_labels()):
                if lab not in ls:
                    hs.append(h)
                    ls.append(lab)
        return hs, ls

    fig.tight_layout(h_pad=1.6, w_pad=0.3, rect=(0, 0.04, 1, 0.95))
    fig.legend(*legend_of(axes[0]), loc="upper center", ncol=5, bbox_to_anchor=(0.5, 1.02), fontsize=6)
    fig.legend(*legend_of(axes[1]), loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04), fontsize=6)
    return _save(fig, "attrs")


# ----------------------------------------------------------------------------- case studies

# long category names of the case-study panels, shortened so that every tick label is distinct
LABEL_ABBREV = {
    "Associate's degree, academic program": "Assoc. (academic)",
    "Associate's degree, occupational/vocational program": "Assoc. (vocational)",
    "High school diploma or equivalent": "High school",
    "Some college but no degree": "Some college",
    "Wage/salary, private": "Private wage/salary",
    "Self-employed, not incorporated": "Self-empl. (not inc.)",
    "Self-employed, incorporated": "Self-empl. (inc.)",
    "Local government employee": "Local government",
    "State government employee": "State government",
    "Federal government employee": "Federal government",
}


def _bin_label(b: str, n: int = 20) -> str:
    """Interval bins with large endpoints in k-notation, e.g. (66685, 199999] -> (66.7k, 200k]."""
    import re

    if str(b) in LABEL_ABBREV:
        return LABEL_ABBREV[str(b)]

    m = re.fullmatch(r"([\[(])\s*([-\d.]+),\s*([-\d.]+)([\])])", str(b))
    if m:
        def k(x: str) -> str:
            v = float(x)
            if abs(v) >= 1000:
                v = round(v / 1000, 1)
                return (f"{v:g}" if v < 100 else f"{round(v):d}") + "k"
            return f"{v:g}"
        return f"{m.group(1)}{k(m.group(2))}, {k(m.group(3))}{m.group(4)}"
    return P._short(str(b), n)


def fig_case(pid: str, rounds: list[int] | None, name: str, q_names=("Q", "Q'"), subdir: str = "e1",
             width: float = 7.05, max_bins: int = 6) -> Path:
    """Released (noisy) histograms of the explanations of release 1 (all k unless ``rounds``), exact
    counts as ticks; each panel title says in how many of the releases the explanation appears."""
    rep = json.loads((RES / subdir / pid / "report.json").read_text())
    expl = [e for e in rep["explanations"] if rounds is None or e["round"] in rounds]
    n_rel = rep.get("releases", {}).get("n", 1)
    fig, axes = plt.subplots(1, len(expl), figsize=(width, 1.75), squeeze=False)
    axes[0, 0].set_ylabel("count", fontsize=6)
    for ax, e in zip(axes[0], expl):
        bins = e["bins"]
        h1, h2 = np.asarray(e["noisy_h1"]), np.asarray(e["noisy_h2"])
        x1, x2 = np.asarray(e["exact_h1"]), np.asarray(e["exact_h2"])
        nz = np.flatnonzero((x1 + x2) > 0)
        order = np.sort(nz[np.argsort(-np.abs(x1 - x2)[nz], kind="stable")[:max_bins]])
        xs = np.arange(len(order))
        ax.bar(xs - 0.2, h1[order], 0.38, color=P.BLUE, label=f"{q_names[0]} (released)")
        ax.bar(xs + 0.2, h2[order], 0.38, color=P.ORANGE, label=f"{q_names[1]} (released)")
        ax.plot(xs - 0.2, x1[order], linestyle="none", marker="_", color=P.INK, markersize=6, markeredgewidth=1.0)
        ax.plot(xs + 0.2, x2[order], linestyle="none", marker="_", color=P.INK, markersize=6, markeredgewidth=1.0,
                label="exact (not released)")
        ax.set_xticks(xs)
        ax.set_xticklabels([_bin_label(bins[i]) for i in order], rotation=40, ha="right", fontsize=5.2)
        parts = [P._short(x, 24) for x in str(e["view"]).split(" AND ")]
        title = ("\n".join(parts[:-1] + [parts[-1] + f" by {e['attr']}"]) if len(parts) > 1
                 else f"{parts[0]}\nby {e['attr']}")
        if n_rel > 1 and "share_of_releases_with_this_explanation" in e:
            title = f"({e['round']}) " + title + f"\nin {round(e['share_of_releases_with_this_explanation'] * n_rel)}/{n_rel} releases"
        ax.set_title(title, fontsize=5.6)
        ax.grid(axis="x", visible=False)
        ax.axhline(0, color=P.MUTED, linewidth=0.5)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.12), handlelength=1.2)
    fig.tight_layout(w_pad=0.4)
    return _save(fig, name)


CASES = [("A2", "case_a2", ("$Q_1$", "$Q_2$")), ("ACS_Q1C1", "case_acs", ("$Q_1$", "$Q_2$")),
         ("CO1", "case_co1", ("$Q_1$", "$Q_2$"))]
# CQA and contrast case studies, out of the chapter for now:
# CASES = [("A2", "case_a2", ("$Q_1$", "$Q_2$")), ("ACS_Q1C1", "case_acs", ("$Q_1$", "$Q_2$")),
#          ("C1", "case_c1", ("$Q_1$", r"$Q_2=Q_\Sigma$")), ("I1", "case_i1", ("$Q_1$ (men)", "$Q_2$ (women)"))]


def fig_cases() -> list[Path]:
    """The case-study figure: all explanations of the first of the ten releases, one row per pair
    (user, 2026-11-28: one compact figure instead of one per pair; fig_case draws the old ones)."""
    return [fig_cases_compact("pair", None, 7.05, "cases", cases=tuple(pid for pid, _, _ in CASES))]


def main() -> None:
    for fn in (fig_quality, fig_view_stage, fig_runtime_methods, fig_runtime_grid, fig_cases):
        try:
            print(fn())
        except FileNotFoundError as e:
            print(f"skip {fn.__name__}: {e}")


if __name__ == "__main__":
    main()


# ----------------------------------------------------------------------------- compact case studies (one figure)

ATTR_SHORT = {"OCCP_bucket": "occupation", "RAC1P": "race", "RELP": "relationship", "SCHL": "education",
              "WKHP": "hours", "COW": "worker class", "decile_score": "risk score", "priors_count": "priors",
              "maritalStatus": "marital status", "is_recid": "reoffended", "hoursPerWeek": "hours"}
CASE_TITLE = {"A2": "A2 (Adult)", "ACS_Q1C1": "S1 (ACSIncome)", "CO1": "C1 (COMPAS)"}
BIN_SHORT = {"Prof-specialty": "Prof-spec.", "Exec-managerial": "Exec-man.", "Adm-clerical": "Adm-cler.",
             "Tech-support": "Tech-supp.", "Married-civ-spouse": "Married", "Married-spouse-absent": "Married-abs.", "Never-married": "Never-marr.",
             "Not-in-family": "Not-in-fam.", "Other-relative": "Other-rel.", "Self-emp-not-inc": "Self-emp.",
             "Self-emp-inc": "Self-emp-inc", "reference-person": "householder", "biological-child": "child",
             "unmarried-partner": "partner", "housemate-roommate": "roommate", "some college": "some coll.",
             "African-American": "Afr.-Amer.", "other-race": "other", "two-or-more": "two+"}


def _short_view(view: str) -> str:
    import re
    parts = []
    for cond in str(view).split(" AND "):
        m = re.match(r"\s*(\w+)\s*=\s*'?([^']*)'?\s*$", cond)
        parts.append(f"{ATTR_SHORT.get(m.group(1), m.group(1))}={m.group(2)}" if m else cond)
    return ", ".join(parts)


def _kfmt(v, _):
    v = float(v)
    if abs(v) >= 1e6:
        return f"{v / 1e6:g}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"


def fig_cases_compact(mode: str = "pair", top: int | None = None, width: float = 7.05, name: str = "cases",
                      cases=("A2", "ACS_Q1C1", "CO1"), max_bins: int = 6, subdir: str = "e1") -> Path:
    """All case studies in one figure, one row per pair and one small panel per explanation of release 1.

    mode="pair": the released histograms of Q1 and Q2 side by side, exact counts as ticks.
    mode="change": one bar per bin, the released change Q2 - Q1 (orange: more in Q2, blue: more in Q1),
    the exact change as a tick.  ``top``: only the explanations in the most releases (in release order).
    The number of releases with the same explanation is a badge in the corner of each panel.
    """
    reps = {pid: json.loads((RES / subdir / pid / "report.json").read_text()) for pid in cases}
    sel = {}
    for pid, rep in reps.items():
        ex = rep["explanations"]
        if top:
            keep = sorted(ex, key=lambda e: -e.get("share_of_releases_with_this_explanation", 0))[:top]
            ex = [e for e in ex if e in keep]
        sel[pid] = ex
    ncol = max(len(v) for v in sel.values())
    panel_h = 1.05 if mode == "pair" else 0.95
    fig, axes = plt.subplots(len(cases), ncol, figsize=(width, panel_h * len(cases) + 0.35), squeeze=False)
    for i, pid in enumerate(cases):
        n_rel = reps[pid].get("releases", {}).get("n", 1)
        for j in range(ncol):
            ax = axes[i, j]
            if j >= len(sel[pid]):
                ax.axis("off")
                continue
            e = sel[pid][j]
            bins = e["bins"]
            h1, h2 = np.asarray(e["noisy_h1"]), np.asarray(e["noisy_h2"])
            x1, x2 = np.asarray(e["exact_h1"]), np.asarray(e["exact_h2"])
            nz = np.flatnonzero((x1 + x2) > 0)
            order = np.sort(nz[np.argsort(-np.abs(x1 - x2)[nz], kind="stable")[:max_bins]])
            xs = np.arange(len(order))
            if mode == "pair":
                ax.bar(xs - 0.2, h1[order], 0.38, color=P.BLUE, label="$Q_1$ (released)")
                ax.bar(xs + 0.2, h2[order], 0.38, color=P.ORANGE, label="$Q_2$ (released)")
                ax.plot(xs - 0.2, x1[order], ls="none", marker="_", color=P.INK, ms=4.5, mew=0.9)
                ax.plot(xs + 0.2, x2[order], ls="none", marker="_", color=P.INK, ms=4.5, mew=0.9,
                        label="exact (not released)")
            else:
                d = (h2 - h1)[order]
                ax.bar(xs, d, 0.62, color=[P.ORANGE if v >= 0 else P.BLUE for v in d])
                ax.plot(xs, (x2 - x1)[order], ls="none", marker="_", color=P.INK, ms=6, mew=0.9)
                ax.axhline(0, color=P.INK, lw=0.5)
            ax.set_xticks(xs)
            ax.set_xticklabels([BIN_SHORT.get(str(bins[i_]), _bin_label(bins[i_], 12)) for i_ in order], rotation=35,
                               ha="right", rotation_mode="anchor", fontsize=4.8)
            ax.tick_params(axis="x", length=0, pad=1)
            ax.tick_params(axis="y", labelsize=4.8, length=1.5, pad=1)
            ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=3))
            ax.yaxis.set_major_formatter(FuncFormatter(_kfmt))
            ax.grid(axis="x", visible=False)
            view = _short_view(e["view"])
            if len(view) > 25 * (width - 0.4) / ncol:  # narrow panels: one condition per line
                view = view.replace(", ", ",\n")
            ax.set_title(f"{view}\nby {ATTR_SHORT.get(e['attr'], e['attr'])}",
                         fontsize=5.0, pad=1.5, loc="left", linespacing=1.05)
            if n_rel > 1 and "share_of_releases_with_this_explanation" in e:
                ax.set_title(f"{round(e['share_of_releases_with_this_explanation'] * n_rel)}/{n_rel}",
                             fontsize=4.8, pad=1.5, loc="right", color=P.MUTED)
            if j == 0:
                ax.set_ylabel(CASE_TITLE.get(pid, pid) + ("\ncount" if mode == "pair" else "\nchange"),
                              fontsize=5.6)
    if mode == "pair":
        h, lab = axes[0, 0].get_legend_handles_labels()
    else:
        from matplotlib.patches import Patch
        h = [Patch(color=P.ORANGE), Patch(color=P.BLUE),
             matplotlib.lines.Line2D([], [], ls="none", marker="_", color=P.INK, ms=6, mew=0.9)]
        lab = ["more in $Q_2$ (released)", "more in $Q_1$ (released)", "exact change (not released)"]
    fig.tight_layout(h_pad=0.35, w_pad=0.25, rect=(0, 0, 1, 1 - 0.22 / fig.get_figheight()))
    fig.legend(h, lab, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0), fontsize=5.6, handlelength=1.2,
               frameon=False)
    return _save(fig, name)
