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

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results"
OUT = ROOT / "paper" / "figures" / "exp"

DS_ORDER = ["adult", "acsincome", "tax", "tax_dirty", "hospital", "ipums"]
DS_TITLE = {"adult": "Adult", "acsincome": "ACSIncome", "tax": "Tax", "tax_dirty": "Tax-dirty (CQA)",
            "hospital": "Hospital (CQA)", "ipums": "IPUMS-CPS (contrast)"}
SURF = "#ffffff"
# C4 is a copy of H1 kept for the case-study set; it would count H1 twice in the Hospital averages
EXCLUDE = {"C4"}

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
    ("ratio_B3_mean", "ApproxRatio vs B2/B3", P.BLUE, "o", "-"),
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
        ax.set_ylim(0, 1.04)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        if j:
            ax.set_yticklabels([])
        if first_row:
            ax.set_title(f"{DS_TITLE[ds]} ({summ[summ.dataset == ds].pair.nunique()})")
        ax.set_xlabel(xlabel)
        if xfmt:
            xfmt(ax, sub.value)


def fig_quality() -> Path:
    e2 = _drop(pd.read_csv(RES / "e2" / "summary.csv"))
    e6 = _drop(pd.read_csv(RES / "e6" / "summary.csv"))
    dss = _datasets(e2)
    fig, axes = plt.subplots(2, len(dss), figsize=(7.05, 2.75), squeeze=False, sharex="row")

    def eps_ticks(ax, v):
        ax.set_xticks([0.1, 1, 5])
        ax.set_xticklabels(["0.1", "1", "5"])

    def g_ticks(ax, v):
        ax.set_xticks([0, 0.1, 1, 10])
        ax.set_xticklabels(["0", ".1", "1", "10"])

    _quality_row(axes[0], e2, dss, r"privacy budget $\epsilon$", True, True, eps_ticks)
    _quality_row(axes[1], e6, dss, r"$\gamma$ / Eq. (14) value", True, False, g_ticks)
    for ax in axes[1]:
        ax.axvline(1.0, color=P.MUTED, linewidth=0.6, linestyle="--", zorder=0)
    for ax in axes[0]:
        ax.axvline(1.0, color=P.MUTED, linewidth=0.6, linestyle="--", zorder=0)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.06))
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
RT_METHODS = ("PRIV_EXPL", "B1", "B2", "B3")
RT_LABEL = {"PRIV_EXPL": "PrivExpl", "B1": "B1", "B2": "B2", "B3": "B3", "OPT_PRIV_EXPL": "OptPrivExpl"}


def _rt_panel(ax, sub: pd.DataFrame, x: str, logx: bool, limit: float):
    for m in RT_METHODS:
        d = sub[sub.method == m].sort_values(x)
        if d.empty:
            continue
        to = d.timeout.astype(bool)
        c, mk = P.METHOD_COLORS[m], P.METHOD_MARKERS[m]
        ax.plot(d[x][~to], d.total_s[~to], color=c, marker=mk, label=RT_LABEL[m],
                linewidth=1.8 if m == "PRIV_EXPL" else 1.2, zorder=3 if m == "PRIV_EXPL" else 2,
                linestyle="--" if m == "B3" else "-")
        if to.any():
            xs = list(d[x][~to].tail(1)) + list(d[x][to])
            ys = list(d.total_s[~to].tail(1)) + [limit] * int(to.sum())
            ax.plot(xs, ys, color=c, linestyle=":", linewidth=1.0)
            ax.plot(d[x][to], [limit] * int(to.sum()), linestyle="none", marker="x", color=c, markersize=5,
                    markeredgewidth=1.4, label=f"{RT_LABEL[m]} timeout")
    ax.set_yscale("log")
    if logx:
        _logx(ax, sub[x])


def fig_runtime_grid(raw_path: Path | None = None) -> Path:
    raw = pd.read_csv(raw_path or RES / "e4" / "raw" / "runtime.csv")
    pts = e4_scalability.points(_drop(raw))
    limit = float(json.loads((RES / "e4" / "metadata.json").read_text()).get("timeout_s", 60)) \
        if (RES / "e4" / "metadata.json").exists() else 60.0
    dss = _datasets(pts)
    sweeps = [s for s in SWEEPS if s[0] in set(pts.sweep)]
    fig, axes = plt.subplots(len(dss), len(sweeps), figsize=(7.05, 1.12 * len(dss) + 0.35), squeeze=False,
                             sharey="row")
    plain = FuncFormatter(lambda v, _: f"{v:g}")
    xticks = {"epsilon": [0.1, 1, 5], "tau": [5, 15, 60], "gamma_mult": [0, 0.1, 1, 10]}
    for i, ds in enumerate(dss):
        for j, (sw, xl, logx) in enumerate(sweeps):
            ax = axes[i, j]
            sub = pts[(pts.dataset == ds) & (pts.sweep == sw)].rename(columns={"value": sw})
            if sw == "data_fraction":
                sub = sub[sub[sw] <= 1.0]
            _rt_panel(ax, sub, sw, logx, limit)
            ax.axhline(limit, color=P.MUTED, linewidth=0.5, linestyle=":", zorder=0)
            ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 3.0)))
            ax.yaxis.set_major_formatter(plain)
            ax.yaxis.set_minor_formatter(NullFormatter())
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
    fig.tight_layout(h_pad=0.25, w_pad=0.3, rect=(0, 0, 1, 0.975))
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), bbox_to_anchor=(0.5, 1.01))
    return _save(fig, "runtime_grid")


# ----------------------------------------------------------------------------- E5: methods, B2 growth

def fig_runtime_methods() -> Path:
    dp = _drop(pd.read_csv(RES / "e5" / "raw" / "default_point.csv"))
    per_pair = dp.groupby(["dataset", "pair", "method"], as_index=False).agg(total_s=("total_s", "median"),
                                                                             timeout=("timeout", "max"))
    g = per_pair.groupby(["dataset", "method"], as_index=False).agg(total_s=("total_s", "mean"),
                                                                    timeout=("timeout", "mean"))
    dss = _datasets(g)
    methods = ["PRIV_EXPL", "OPT_PRIV_EXPL", "B1", "B2", "B3"]
    growth = _drop(pd.read_csv(RES / "e5" / "raw" / "b2_growth.csv"))
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.05, 1.75), gridspec_kw={"width_ratios": [1.9, 1]})
    w = 0.16
    x = np.arange(len(dss))
    for i, m in enumerate(methods):
        vals = [float(g[(g.dataset == d) & (g.method == m)].total_s.mean()) for d in dss]
        tos = [float(g[(g.dataset == d) & (g.method == m)].timeout.mean()) for d in dss]
        bars = a.bar(x + (i - 2) * w, vals, w * 0.88, color=P.METHOD_COLORS[m], label=RT_LABEL[m])
        for bx, t in zip(bars, tos):
            if t > 0:
                bx.set_hatch("////")
                bx.set_edgecolor(SURF)
    a.set_yscale("log")
    a.set_xticks(x)
    a.set_xticklabels([DS_TITLE[d].split(" (")[0] for d in dss])
    a.set_ylabel("end-to-end time (s)")
    a.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.2), handlelength=1.2, columnspacing=0.9)
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


# ----------------------------------------------------------------------------- case studies

def _bin_label(b: str, n: int = 12) -> str:
    """Interval bins with large endpoints in k-notation, e.g. (66685, 199999] -> (66.7k, 200k]."""
    import re

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


def fig_case(pid: str, rounds: list[int], name: str, q_names=("Q", "Q'"), subdir: str = "e1",
             width: float = 3.33, max_bins: int = 8) -> Path:
    """Released (noisy) histograms of selected explanations of one released run, exact counts as ticks."""
    rep = json.loads((RES / subdir / pid / "report.json").read_text())
    expl = [e for e in rep["explanations"] if e["round"] in rounds]
    fig, axes = plt.subplots(1, len(expl), figsize=(width, 1.45), squeeze=False)
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
        ax.set_title("\n".join(parts[:-1] + [parts[-1] + f" by {e['attr']}"]) if len(parts) > 1
                     else f"{parts[0]}\nby {e['attr']}", fontsize=5.6)
        ax.grid(axis="x", visible=False)
        ax.axhline(0, color=P.MUTED, linewidth=0.5)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.12), handlelength=1.2)
    fig.tight_layout(w_pad=0.4)
    return _save(fig, name)


def main() -> None:
    for fn in (fig_quality, fig_view_stage, fig_runtime_methods, fig_runtime_grid):
        try:
            print(fn())
        except FileNotFoundError as e:
            print(f"skip {fn.__name__}: {e}")


if __name__ == "__main__":
    main()
