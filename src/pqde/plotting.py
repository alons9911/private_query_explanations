"""Paper-style static figures (matplotlib, PNG + PDF).

Colours follow a validated categorical palette: slot 1 (blue) is always Q1/Q,
slot 2 (orange) always Q2/Q'; the baseline lines use the first three slots,
which stay distinguishable for colour-blind readers in any pairing.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
BASELINE_COLORS = {"B1": BLUE, "B2": ORANGE, "B3": AQUA}
BASELINE_LABELS = {"B1": "vs B1 (eps -> inf)", "B2": "vs B2 (exhaustive optimum)", "B3": "vs B3 (greedy non-private)"}
MARKERS = {"B1": "o", "B2": "s", "B3": "^"}

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.frameon": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "lines.linewidth": 2.0,
    "lines.markersize": 5,
    "font.size": 8,
})


def _save(fig, path: Path) -> list[Path]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for ext in (".png", ".pdf"):
        p = path.with_suffix(ext)
        fig.savefig(p, dpi=170, bbox_inches="tight")
        out.append(p)
    plt.close(fig)
    return out


def _short(label: str, n: int = 18) -> str:
    return label if len(label) <= n else label[: n - 1] + "…"


def plot_explanations(explanations: list[dict], title: str, path: Path, q1_name: str = "Q", q2_name: str = "Q'",
                      max_bins: int = 14) -> list[Path]:
    """Figures 4/5: one panel per released explanation, paired noisy bars per bin."""
    k = len(explanations)
    if k == 0:
        return []
    cols = min(k, 5)
    rows = int(np.ceil(k / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 2.7 * rows), squeeze=False)
    for ax, e in zip(axes.ravel(), explanations):
        bins = list(e["bins"])
        h1 = np.asarray(e["noisy_h1"], float)
        h2 = np.asarray(e["noisy_h2"], float)
        if len(bins) > max_bins:  # keep the bins where the release shows the largest difference
            keep = np.argsort(-np.abs(h1 - h2), kind="stable")[:max_bins]
            bins, h1, h2 = [bins[i] for i in keep], h1[keep], h2[keep]
            sub = f"\n({max_bins} of {len(e['bins'])} bins, largest |difference| first)"
        else:
            sub = ""
        x = np.arange(len(bins))
        w = 0.4
        ax.bar(x - w / 2 - 0.01, np.maximum(h1, 0), w, color=BLUE, label=f"{q1_name} (noisy, DP)")
        ax.bar(x + w / 2 + 0.01, np.maximum(h2, 0), w, color=ORANGE, label=f"{q2_name} (noisy, DP)")
        ax.set_xticks(x, [_short(b) for b in bins], rotation=55, ha="right")
        ax.set_title(f"{_short(e['view'], 48)}\nattribute = {e['attr']}{sub}", fontsize=7.5)
        ax.set_ylabel("noisy count")
        ax.grid(axis="x", visible=False)
    for ax in axes.ravel()[k:]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(title, fontsize=9, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.legend(handles, labels, loc="upper right", ncol=2, bbox_to_anchor=(1.0, 1.0))
    return _save(fig, path)


def plot_release_leaves(e: dict, sigma_diff: float, path: Path, title: str) -> list[Path]:
    """Figure 3: per-bin difference of the two released histograms against the 2-sigma noise band."""
    d = np.asarray(e["noisy_h1"], float) - np.asarray(e["noisy_h2"], float)
    order = np.argsort(-np.abs(d))
    bins = [e["bins"][i] for i in order]
    d = np.abs(d[order])
    fig, ax = plt.subplots(figsize=(4.6, 0.32 * len(bins) + 1.0))
    y = np.arange(len(bins))[::-1]
    strong = d >= 2 * sigma_diff
    ax.barh(y, d, color=np.where(strong, BLUE, "#c9c8c3"), height=0.7)
    ax.axvline(2 * sigma_diff, color=INK2, linestyle="--", linewidth=1)
    ax.text(2 * sigma_diff, -0.9, "  2 sigma of the release noise", color=INK2, fontsize=7, va="top")
    for yi, v, s in zip(y, d, strong):
        ax.text(v, yi, f" {v:.0f}" + (f" ({v / sigma_diff:.0f} sigma)" if s else ""), va="center", fontsize=7, color=INK2)
    ax.set_yticks(y, [_short(b, 22) for b in bins])
    ax.set_xlabel("|difference| between the two released histograms (tuples)")
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return _save(fig, path)


def plot_approx_ratio(summary: pd.DataFrame, pairs: list[str], path: Path, titles: dict | None = None) -> list[Path]:
    """Figure 6: ApproxRatio vs eps against B1, B2, B3 (one panel per pair)."""
    n = len(pairs)
    cols = min(n, 3)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 2.8 * rows), squeeze=False)
    for ax, pid in zip(axes.ravel(), pairs):
        sub = summary[summary.pair == pid].sort_values("epsilon")
        for b in ("B1", "B2", "B3"):
            col = f"ratio_{b}_mean"
            if col not in sub:
                continue
            ax.plot(sub.epsilon, sub[col], marker=MARKERS[b], color=BASELINE_COLORS[b], label=BASELINE_LABELS[b],
                    markerfacecolor=SURFACE if b == "B2" else BASELINE_COLORS[b], markeredgewidth=1.5)
        ax.axhline(1.0, color=MUTED, linestyle=":", linewidth=1)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.08)
        ax.set_xlabel("privacy budget eps")
        ax.set_ylabel("ApproxRatio")
        ax.set_title((titles or {}).get(pid, pid))
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    axes.ravel()[0].legend(loc="lower right")
    fig.suptitle("ApproxRatio of the released set against each baseline (gamma_eval = 0)", fontsize=9)
    fig.tight_layout()
    return _save(fig, path)


def plot_lines(df: pd.DataFrame, x: str, ys: list[tuple[str, str]], path: Path, title: str, xlabel: str,
               ylabel: str, logx: bool = False, hue: str | None = None, ylim=None) -> list[Path]:
    """Generic small-multiple line chart: one panel, one line per (column, label) or per hue value."""
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    colors = [BLUE, ORANGE, AQUA, "#eda100", "#e87ba4", "#008300"]
    if hue is not None:
        for i, (h, sub) in enumerate(df.groupby(hue, sort=False)):
            col, _ = ys[0]
            sub = sub.sort_values(x)
            ax.plot(sub[x], sub[col], marker="o", color=colors[i % len(colors)], label=str(h))
    else:
        for i, (col, label) in enumerate(ys):
            d = df.sort_values(x)
            ax.plot(d[x], d[col], marker="o", color=colors[i % len(colors)], label=label)
    if logx:
        if (df[x] <= 0).any():
            ax.set_xscale("symlog", linthresh=1e-3)
        else:
            ax.set_xscale("log")
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if hue is not None or len(ys) > 1:
        ax.legend()
    fig.tight_layout()
    return _save(fig, path)


def plot_scalability(panels: dict[str, pd.DataFrame], path: Path, title: str) -> list[Path]:
    """Figure 7: running time against k, N, eps, |P|, tau and gamma (one panel each).

    Every panel plots the per-invocation mechanism time; build time of the cache
    (where it varies) is a separate panel row, never a second y-axis.
    """
    spec = [
        ("k", "k", "number of explanations k", False),
        ("N", "N", "database size N (rows)", False),
        ("epsilon", "epsilon", "privacy budget eps", True),
        ("P", "P", "view pool |P|", False),
        ("tau", "tau_percent", "tau as % of |P|", True),
        ("gamma", "gamma_percent", "gamma as % of N", False),
    ]
    spec = [s for s in spec if s[0] in panels]
    fig, axes = plt.subplots(2, len(spec), figsize=(2.9 * len(spec), 4.8), squeeze=False)
    for j, (key, x, xl, logx) in enumerate(spec):
        df = panels[key].sort_values(x)
        ax = axes[0, j]
        ax.plot(df[x], df["mechanism_ms"], marker="o", color=BLUE)
        ax.set_title(f"vs {xl}")
        ax.set_ylabel("mechanism time per run (ms)")
        ax.set_ylim(0, max(df["mechanism_ms"].max() * 1.2, 1e-3))
        if logx:
            ax.set_xscale("log")
        ax2 = axes[1, j]
        if "build_s" in df and df["build_s"].notna().any() and key in ("N", "P"):
            ax2.plot(df[x], df["build_s"], marker="s", color=MUTED)
            ax2.set_ylabel("one-off cache build (s)")
            ax2.set_ylim(0, df["build_s"].max() * 1.2)
            ax2.set_xlabel(xl)
            if logx:
                ax2.set_xscale("log")
        else:
            ax2.axis("off")
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    return _save(fig, path)


def plot_runtime(methods: pd.DataFrame, b2: pd.DataFrame, path: Path) -> list[Path]:
    """Figure 8: per-invocation cost of each method and the growth of B2."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.2, 3.0))
    order = ["private", "B1", "B3", "B2"]
    m = methods.set_index("method").reindex([o for o in order if o in set(methods.method)])
    colors = {"private": BLUE, "B1": "#8a8984", "B3": AQUA, "B2": ORANGE}
    a.bar(range(len(m)), m["ms"], color=[colors[i] for i in m.index], width=0.6)
    a.set_xticks(range(len(m)), ["private (Alg. 1)" if i == "private" else i for i in m.index])
    a.set_yscale("log")
    a.set_ylabel("time per invocation (ms, log)")
    a.set_title("(a) per-invocation cost (median over pairs)")
    for i, v in enumerate(m["ms"]):
        a.text(i, v, f"{v:,.0f}" if v >= 100 else f"{v:.3g}", ha="center", va="bottom", fontsize=7, color=INK2)
    a.grid(axis="x", visible=False)
    b.plot(b2.pool_size, b2.seconds, marker="o", color=ORANGE, label="B2 exhaustive")
    if "private_s" in b2:
        b.axhline(float(b2.private_s.iloc[0]), color=BLUE, linestyle="--", linewidth=1.2, label="private algorithm")
    b.set_yscale("log")
    b.set_xlabel("candidate pool size")
    b.set_ylabel("running time (s, log)")
    b.set_title("(b) B2 exhaustive blows up combinatorially")
    b.legend()
    fig.tight_layout()
    return _save(fig, path)


# =========================================================================== v2 figures
# Method identity is fixed across every figure (colour follows the method):
# slot 1 blue = PRIV_EXPL, slot 2 orange = B1, slot 3 aqua = B2, slot 4 yellow = B3,
# each with its own marker so identity never rests on colour alone.

YELLOW = "#eda100"
MAGENTA = "#e87ba4"
METHOD_COLORS = {"PRIV_EXPL": BLUE, "B1": ORANGE, "B2": AQUA, "B3": YELLOW, "OPT_PRIV_EXPL": MAGENTA}
METHOD_MARKERS = {"PRIV_EXPL": "o", "B1": "s", "B2": "^", "B3": "D", "OPT_PRIV_EXPL": "P"}
RUNTIME_METHODS = ("PRIV_EXPL", "OPT_PRIV_EXPL", "B1", "B2", "B3")
DATASET_TITLES = {"adult": "Adult", "tax": "Tax", "tax_dirty": "Tax (dirty, CQA)", "hospital": "Hospital",
                  "stackoverflow": "StackOverflow", "ipums": "IPUMS-CPS (contrast)"}


def _ds_title(ds: str, synthetic: dict | None) -> str:
    t = DATASET_TITLES.get(ds, ds)
    return t + (" [synthetic]" if synthetic and synthetic.get(ds) else "")


def _xscale(ax, x, logx: bool):
    if not logx:
        return
    if (np.asarray(x) <= 0).any():
        pos = np.asarray(x)[np.asarray(x) > 0]
        ax.set_xscale("symlog", linthresh=float(pos.min()) if len(pos) else 1e-3)
        ax.set_xlim(left=0)
    else:
        ax.set_xscale("log")


def plot_accuracy_grid(summary: pd.DataFrame, by_ds: dict, metric: str, label: str, path: Path, *, xlabel: str,
                       logx: bool, synthetic: dict | None = None) -> list[Path]:
    """One row per dataset, one panel per pair; lines = PRIV_EXPL measured against B1, B2, B3."""
    ncol = max(len(v) for v in by_ds.values())
    fig, axes = plt.subplots(len(by_ds), ncol, figsize=(2.55 * ncol, 2.3 * len(by_ds)), squeeze=False)
    for i, (ds, pids) in enumerate(by_ds.items()):
        for j in range(ncol):
            ax = axes[i, j]
            if j >= len(pids):
                ax.axis("off")
                continue
            sub = summary[summary.pair == pids[j]].sort_values("value")
            for b in ("B1", "B2", "B3"):
                ax.plot(sub.value, sub[f"{metric}_{b}_mean"], marker=METHOD_MARKERS[b], color=METHOD_COLORS[b],
                        markersize=4, linewidth=1.6, linestyle="--" if b == "B3" else "-", label=f"vs {b}")
            _xscale(ax, sub.value, logx)
            if metric == "ratio":
                ax.axhline(1.0, color=MUTED, linestyle=":", linewidth=1)
                ax.set_ylim(0, max(1.1, float(np.nanmax(sub[[f"ratio_{b}_mean" for b in ("B1", "B2", "B3")]].to_numpy())) * 1.05))
            else:
                ax.set_ylim(0, 1.05)
            ax.set_title(pids[j] if j else f"{_ds_title(ds, synthetic)} — {pids[j]}", fontsize=7.5)
            if j == 0:
                ax.set_ylabel(label)
            if i == len(by_ds) - 1 or j >= len(list(by_ds.values())[min(i + 1, len(by_ds) - 1)]):
                ax.set_xlabel(xlabel)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.suptitle(f"PRIV_EXPL: {label} against each baseline", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.legend(handles, labels, loc="upper right", ncol=3)
    return _save(fig, path)


def plot_accuracy_datasets(summary: pd.DataFrame, by_ds: dict, metric: str, label: str, path: Path, *, xlabel: str,
                           logx: bool, synthetic: dict | None = None) -> list[Path]:
    """One panel per dataset (mean over its pairs); lines = against B1, B2, B3."""
    fig, axes = plt.subplots(1, len(by_ds), figsize=(3.0 * len(by_ds), 2.6), squeeze=False)
    for j, (ds, pids) in enumerate(by_ds.items()):
        ax = axes[0, j]
        sub = summary[summary.pair.isin(pids)].groupby("value", as_index=False).mean(numeric_only=True)
        for b in ("B1", "B2", "B3"):
            ax.plot(sub.value, sub[f"{metric}_{b}_mean"], marker=METHOD_MARKERS[b], color=METHOD_COLORS[b],
                    linestyle="--" if b == "B3" else "-", label=f"vs {b}")
        _xscale(ax, sub.value, logx)
        if metric == "ratio":
            ax.axhline(1.0, color=MUTED, linestyle=":", linewidth=1)
            top = float(np.nanmax(sub[[f"ratio_{b}_mean" for b in ("B1", "B2", "B3")]].to_numpy()))
            ax.set_ylim(0, max(1.1, top * 1.05))
        else:
            ax.set_ylim(0, 1.05)
        ax.set_title(f"{_ds_title(ds, synthetic)} ({len(pids)} pairs)")
        ax.set_xlabel(xlabel)
        if j == 0:
            ax.set_ylabel(label)
    axes[0, 0].legend(loc="lower right")
    fig.suptitle(f"PRIV_EXPL: {label} against each baseline, mean over the pairs of each dataset", fontsize=9)
    fig.tight_layout()
    return _save(fig, path)


def plot_release_quality(summary: pd.DataFrame, by_ds: dict, path: Path, *, xlabel: str, logx: bool,
                         synthetic: dict | None = None) -> list[Path]:
    """Two rows: relative L1 error of the released histograms, and sign agreement of the released differences."""
    fig, axes = plt.subplots(2, len(by_ds), figsize=(3.0 * len(by_ds), 4.8), squeeze=False)
    for j, (ds, pids) in enumerate(by_ds.items()):
        sub = summary[summary.pair.isin(pids)].groupby("value", as_index=False).mean(numeric_only=True)
        for i, (col, lab) in enumerate((("hist_rel_l1_mean", "relative L1 error of the release"),
                                        ("diff_sign_acc_mean", "sign agreement of H1 - H2"))):
            ax = axes[i, j]
            ax.plot(sub.value, sub[col], marker="o", color=BLUE)
            _xscale(ax, sub.value, logx)
            ax.set_ylim(0, max(1.05, float(np.nanmax(sub[col])) * 1.1) if i == 0 else 1.05)
            if i == 0:
                ax.set_title(f"{_ds_title(ds, synthetic)} ({len(pids)} pairs)")
            if j == 0:
                ax.set_ylabel(lab)
            if i == 1:
                ax.set_xlabel(xlabel)
    fig.suptitle("PRIV_EXPL: quality of the released histograms (mean over pairs)", fontsize=9)
    fig.tight_layout()
    return _save(fig, path)


RUNTIME_SWEEPS = [("k", "number of explanations k", False), ("data_fraction", "database size N", False),
                  ("epsilon", "privacy budget eps", True), ("view_fraction", "view pool |P|", False),
                  ("tau", "views kept tau", True), ("gamma_mult", "gamma / gamma_Eq.(12)", True)]


def _runtime_panel(ax, sub: pd.DataFrame, x: str, logx: bool) -> None:
    """Five methods; a timed-out point is drawn at the time limit with an open 'x' and a dashed segment."""
    for m in RUNTIME_METHODS:
        d = sub[sub.method == m].sort_values(x)
        if d.empty:
            continue
        ok, to = d[~d.timeout.astype(bool)], d[d.timeout.astype(bool)]
        ax.plot(ok[x], ok.total_s, marker=METHOD_MARKERS[m], color=METHOD_COLORS[m], markersize=4,
                linewidth=2.2 if m == "PRIV_EXPL" else 1.6, label=m, zorder=3 if m == "PRIV_EXPL" else 2)
        if len(to):
            xs = list(ok[x].tail(1)) + list(to[x])
            ys = list(ok.total_s.tail(1)) + list(to.total_s)
            ax.plot(xs, ys, color=METHOD_COLORS[m], linestyle="--", linewidth=1.1)
            ax.plot(to[x], to.total_s, linestyle="none", marker="x", color=METHOD_COLORS[m], markersize=6,
                    markeredgewidth=1.8, label=f"{m} timeout")
    if sub.timeout.astype(bool).any():
        ax.axhline(float(sub[sub.timeout.astype(bool)].total_s.max()), color=MUTED, linestyle=":", linewidth=0.8)
    ax.set_yscale("log")
    _xscale(ax, sub[x], logx)


def plot_runtime_row(points: pd.DataFrame, dataset: str, path: Path, synthetic: bool = False) -> list[Path]:
    """One dataset: one panel per varied parameter, end-to-end time of the four methods."""
    sweeps = [s for s in RUNTIME_SWEEPS if s[0] in set(points.sweep)]
    fig, axes = plt.subplots(1, len(sweeps), figsize=(2.75 * len(sweeps), 2.7), squeeze=False)
    for j, (sw, xl, logx) in enumerate(sweeps):
        sub = points[(points.dataset == dataset) & (points.sweep == sw)].rename(columns={"value": sw})
        _runtime_panel(axes[0, j], sub, sw, logx)
        axes[0, j].set_xlabel(xl)
        if sw == "data_fraction":
            n_full = sub["N"].max() / max(sub[sw].max(), 1e-9)
            axes[0, j].set_xlabel(f"{xl} (fraction of {n_full:,.0f})")
        if sw == "view_fraction":
            axes[0, j].set_xlabel(f"{xl} (fraction of all views)")
        if j == 0:
            axes[0, j].set_ylabel("end-to-end time (s, log)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    for ax in axes[0, 1:]:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)
    title = DATASET_TITLES.get(dataset, dataset) + (" [synthetic data]" if synthetic else "")
    fig.suptitle(f"{title}: end-to-end running time (mean over the dataset's pairs)", fontsize=9, x=0.3)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.legend(handles, labels, loc="upper right", ncol=5, fontsize=6.5)
    return _save(fig, path)


def plot_runtime_grid(points: pd.DataFrame, path: Path, synthetic: dict | None = None) -> list[Path]:
    datasets = list(dict.fromkeys(points.dataset))
    sweeps = [s for s in RUNTIME_SWEEPS if s[0] in set(points.sweep)]
    fig, axes = plt.subplots(len(datasets), len(sweeps), figsize=(2.6 * len(sweeps), 2.2 * len(datasets)),
                             squeeze=False)
    for i, ds in enumerate(datasets):
        for j, (sw, xl, logx) in enumerate(sweeps):
            sub = points[(points.dataset == ds) & (points.sweep == sw)].rename(columns={"value": sw})
            _runtime_panel(axes[i, j], sub, sw, logx)
            if i == 0:
                axes[i, j].set_title(f"vs {xl}", fontsize=8)
            if i == len(datasets) - 1:
                axes[i, j].set_xlabel(xl)
            if j == 0:
                axes[i, j].set_ylabel(f"{_ds_title(ds, synthetic)}\ntime (s, log)", fontsize=7.5)
    handles, labels = [], []
    for ax in axes.ravel():
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h)
                labels.append(l)
    fig.suptitle("End-to-end running time; rows = datasets, columns = the varied parameter", fontsize=9, x=0.3)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.legend(handles, labels, loc="upper right", ncol=5, fontsize=7)
    return _save(fig, path)


def plot_method_bars(table: pd.DataFrame, path: Path, title: str, synthetic: dict | None = None) -> list[Path]:
    """Grouped bars: datasets on the x axis, one bar per method (end-to-end, log scale)."""
    datasets = list(dict.fromkeys(table.dataset))
    methods = [m for m in RUNTIME_METHODS if m in set(table.method)]
    fig, ax = plt.subplots(figsize=(1.6 * len(datasets) + 1.5, 3.0))
    w = 0.8 / len(methods)
    for i, m in enumerate(methods):
        vals = [float(table[(table.dataset == d) & (table.method == m)].total_s.mean()) for d in datasets]
        ax.bar(np.arange(len(datasets)) + (i - (len(methods) - 1) / 2) * (w + 0.01), vals, w,
               color=METHOD_COLORS[m], label=m)
    ax.set_xticks(range(len(datasets)), [_ds_title(d, synthetic) for d in datasets], rotation=15)
    ax.set_yscale("log")
    ax.set_ylabel("end-to-end time (s, log)")
    ax.set_title(title)
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=5, fontsize=6.5)
    fig.tight_layout()
    return _save(fig, path)


def plot_b2_growth(growth: pd.DataFrame, path: Path, synthetic: dict | None = None) -> list[Path]:
    """B2 end-to-end time against the candidate pool, one panel per dataset, PRIV_EXPL as reference."""
    datasets = list(dict.fromkeys(growth.dataset))
    fig, axes = plt.subplots(1, len(datasets), figsize=(2.9 * len(datasets), 2.7), squeeze=False)
    for j, ds in enumerate(datasets):
        ax = axes[0, j]
        sub = growth[growth.dataset == ds].groupby("pool_size", as_index=False).mean(numeric_only=True)
        ax.plot(sub.pool_size, sub.b2_total_s, marker=METHOD_MARKERS["B2"], color=METHOD_COLORS["B2"], label="B2")
        if "timeout" in sub and (sub.timeout > 0).any():
            t = sub[sub.timeout > 0]
            ax.plot(t.pool_size, t.b2_total_s, linestyle="none", marker="x", color=METHOD_COLORS["B2"],
                    markersize=6, markeredgewidth=1.8, label="B2 timeout")
        ax.plot(sub.pool_size, sub.priv_total_s, marker=METHOD_MARKERS["PRIV_EXPL"], color=METHOD_COLORS["PRIV_EXPL"],
                label="PRIV_EXPL")
        ax.set_yscale("log")
        ax.set_xlabel("B2 candidate pool size")
        ax.set_title(_ds_title(ds, synthetic))
        if j == 0:
            ax.set_ylabel("end-to-end time (s, log)")
    axes[0, 0].legend()
    fig.suptitle("B2 grows combinatorially with its candidate pool (end to end, k = 5)", fontsize=9)
    fig.tight_layout()
    return _save(fig, path)


def plot_routes(table: pd.DataFrame, path: Path, synthetic: dict | None = None) -> list[Path]:
    """End-to-end PRIV_EXPL time per statistics route (grouped bars per dataset)."""
    datasets = list(dict.fromkeys(table.dataset))
    routes = list(dict.fromkeys(table.route))
    colors = [MUTED, "#c9c8c3", BLUE, "#6250d6", AQUA, ORANGE]
    fig, ax = plt.subplots(figsize=(1.7 * len(datasets) + 1.5, 3.0))
    w = 0.8 / len(routes)
    for i, r in enumerate(routes):
        vals = [float(table[(table.dataset == d) & (table.route == r)].total_s.mean()) for d in datasets]
        ax.bar(np.arange(len(datasets)) + (i - (len(routes) - 1) / 2) * (w + 0.01), vals, w, color=colors[i % len(colors)],
               label=r)
    ax.set_xticks(range(len(datasets)), [_ds_title(d, synthetic) for d in datasets], rotation=15)
    ax.set_yscale("log")
    ax.set_ylabel("PRIV_EXPL end-to-end (s, log)")
    ax.set_title("PRIV_EXPL end to end by statistics route: original (Section 4.2) vs O1 and O1 + O3")
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=6.5)
    fig.tight_layout()
    return _save(fig, path)
