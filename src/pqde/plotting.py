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
        if len(bins) > max_bins:  # keep the bins with the largest released mass
            keep = np.sort(np.argsort(-(np.abs(h1) + np.abs(h2)))[:max_bins])
            bins, h1, h2 = [bins[i] for i in keep], h1[keep], h2[keep]
        x = np.arange(len(bins))
        w = 0.4
        ax.bar(x - w / 2 - 0.01, np.maximum(h1, 0), w, color=BLUE, label=f"{q1_name} (noisy, DP)")
        ax.bar(x + w / 2 + 0.01, np.maximum(h2, 0), w, color=ORANGE, label=f"{q2_name} (noisy, DP)")
        ax.set_xticks(x, [_short(b) for b in bins], rotation=55, ha="right")
        ax.set_title(f"{_short(e['view'], 48)}\nattribute = {e['attr']}", fontsize=7.5)
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
