from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _read_jsonl(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame()
    # Flatten nested "spec" dict.
    df = pd.json_normalize(rows)
    return df


def _savefig(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def plot_runtime_sweeps(results_dir: Path, out_dir: Path) -> None:
    """
    Slide 42: runtime vs tuples/algorithm/k/#predicates/epsilon/tau.
    """

    sns.set_theme(style="whitegrid")

    sweep_files = [
        ("runtime_vs_tuples.jsonl", "spec.n_tuples", "runtime vs #tuples"),
        ("runtime_vs_k.jsonl", "spec.k", "runtime vs k"),
        ("runtime_vs_num_predicates.jsonl", "spec.max_values_per_predicate_attr", "runtime vs #predicates (limit)"),
        ("runtime_vs_epsilon.jsonl", "spec.epsilon", "runtime vs epsilon"),
        ("runtime_vs_tau.jsonl", "spec.tau", "runtime vs tau"),
    ]

    for fname, xcol, title in sweep_files:
        df = _read_jsonl(results_dir / fname)
        if df.empty:
            continue
        plt.figure(figsize=(7, 4))
        sns.lineplot(data=df.sort_values(xcol), x=xcol, y="runtime_s", marker="o", errorbar="sd")
        plt.title(title)
        plt.xlabel(xcol.replace("spec.", ""))
        plt.ylabel("runtime (s)")
        _savefig(out_dir / fname.replace(".jsonl", ".png"))

    # Algorithm comparison (bar chart)
    df = _read_jsonl(results_dir / "runtime_vs_algorithm.jsonl")
    if not df.empty:
        plt.figure(figsize=(8, 4))
        sns.barplot(data=df, x="spec.algorithm", y="runtime_s")
        plt.title("runtime vs algorithm")
        plt.xlabel("algorithm")
        plt.ylabel("runtime (s)")
        plt.xticks(rotation=20, ha="right")
        _savefig(out_dir / "runtime_vs_algorithm.png")


def plot_quality_heatmaps(results_dir: Path, out_dir: Path) -> None:
    """
    Slide 43: heatmap of output quality vs initial predicates, tau, algorithm, epsilon.

    We generate:
    - For each algorithm and predicate-limit: heatmap over (tau x epsilon) for avg_selected_hd
    - For private-explanations only: heatmap over (tau x epsilon) for avg_noisy_hist_mae
    """

    sns.set_theme(style="white")
    df = _read_jsonl(results_dir / "quality_heatmap_grid.jsonl")
    if df.empty:
        return

    # Ensure numeric types
    for c in ["spec.tau", "spec.epsilon", "spec.max_values_per_predicate_attr", "avg_selected_hd", "avg_noisy_hist_mae"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["pred_limit"] = df["spec.max_values_per_predicate_attr"].fillna(-1).astype(int)
    df["algorithm"] = df["spec.algorithm"].astype(str)

    # Heatmaps for avg_selected_hd (all algorithms)
    for alg in sorted(df["algorithm"].unique()):
        dfa = df[df["algorithm"] == alg]
        for lim in sorted(dfa["pred_limit"].unique()):
            dfl = dfa[dfa["pred_limit"] == lim]
            pivot = dfl.pivot_table(
                index="spec.tau",
                columns="spec.epsilon",
                values="avg_selected_hd",
                aggfunc="mean",
            ).sort_index()
            if pivot.empty:
                continue
            plt.figure(figsize=(8, 4.5))
            sns.heatmap(pivot, annot=True, fmt=".3f", cmap="viridis")
            plt.title(f"avg_selected_hd heatmap — alg={alg}, pred_limit={lim}")
            plt.xlabel("epsilon")
            plt.ylabel("tau")
            _savefig(out_dir / f"heatmap_avg_selected_hd__alg={alg}__pred_limit={lim}.png")

    # Heatmaps for avg_noisy_hist_mae (private only)
    dfa = df[df["algorithm"] == "private-explanations"].copy()
    if not dfa.empty and "avg_noisy_hist_mae" in dfa.columns:
        for lim in sorted(dfa["pred_limit"].unique()):
            dfl = dfa[dfa["pred_limit"] == lim]
            pivot = dfl.pivot_table(
                index="spec.tau",
                columns="spec.epsilon",
                values="avg_noisy_hist_mae",
                aggfunc="mean",
            ).sort_index()
            if pivot.empty:
                continue
            plt.figure(figsize=(8, 4.5))
            sns.heatmap(pivot, annot=True, fmt=".3f", cmap="magma_r")
            plt.title(f"avg_noisy_hist_mae heatmap — alg=private-explanations, pred_limit={lim}")
            plt.xlabel("epsilon")
            plt.ylabel("tau")
            _savefig(out_dir / f"heatmap_avg_noisy_hist_mae__pred_limit={lim}.png")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate visualizations for experiments (slides 41–43).")
    ap.add_argument("--results", default="results", help="Directory containing *.jsonl outputs from pqr.experiments")
    ap.add_argument("--out", default=None, help="Output directory for plots (default: <results>/plots)")
    args = ap.parse_args()

    results_dir = Path(args.results)

    # If results_dir contains suite subdirectories (e.g. results/<dataset>/<label>/),
    # generate plots for each leaf directory that contains the expected JSONL files.
    def is_leaf(d: Path) -> bool:
        return any((d / f).exists() for f in ("runtime_vs_algorithm.jsonl", "quality_heatmap_grid.jsonl"))

    leaves = [results_dir] if is_leaf(results_dir) else [p for p in results_dir.rglob("*") if p.is_dir() and is_leaf(p)]
    if not leaves:
        raise SystemExit(f"No experiment outputs found under: {results_dir}")

    for leaf in leaves:
        out_dir = Path(args.out) if args.out else (leaf / "plots")
        out_dir.mkdir(parents=True, exist_ok=True)
        plot_runtime_sweeps(leaf, out_dir)
        plot_quality_heatmaps(leaf, out_dir)
        print(f"Wrote plots to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()

