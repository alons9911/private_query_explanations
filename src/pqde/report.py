"""Collect the outputs of E1-E5 into ``results/REPORT.md``."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiments.common import RESULTS_DIR, to_markdown


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def _fmt(x, nd=3):
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _pair_section(pid: str, rep: dict, base: Path) -> list[str]:
    p = rep["pair"]
    prm = rep["parameters"]
    vs = rep["view_stage"]
    syn = " **(synthetic data)**" if p.get("synthetic_data") else ""
    L = [f"### {pid} — {p['dataset']}{syn}", ""]
    L.append(f"* Q1 = `{p['Q1']}` (|Q1| = {p['|Q1|']:,})")
    L.append(f"* Q2 = `{p['Q2']}` (|Q2| = {p['|Q2|']:,}; overlap {p['|Q1 & Q2|']:,})")
    for k, v in p.items():
        if k.startswith("constraint:"):
            paper = p.get("paper_reported", {})
            pp = f" — paper: {paper.get('share_q1')} → {paper.get('share_q2')}" if paper.get("share_q1") is not None else ""
            L.append(f"* {k}: {v['share_Q1']:.1%} → {v['share_Q2']:.1%}{pp}")
    if "refinement_search" in p:
        r = p["refinement_search"]
        L.append(f"* Q' found by the refinement search (predicate distance {r['predicate_distance']:.3f}, "
                 f"{r['n_evaluated']} refinements evaluated)")
    if "selection_rule" in p:
        s = p["selection_rule"]
        L.append(f"* selection rule: `{s['attr']} = '{s['value']}'`, |Q| = {s['size']}, Q_Sigma drops "
                 f"{s['drop_fraction']:.0%}, most uneven over `{s['most_uneven_attr']}` (TVD {s['unevenness_tvd']:.2f})")
    if "conflicts" in p:
        c = p["conflicts"]
        L.append(f"* conflict hypergraph: {c['tuples_in_conflict']} of {p['N']} tuples on {c['edges']} edges")
    L.append(f"* |P| = {prm['|P|']:,}, tau = {prm['tau']}, gamma = {prm['gamma']:.1f}, "
             f"Laplace scale per bin = {prm['laplace_scale_per_bin']:.1f} (sd of released difference "
             f"{prm['sigma_of_released_difference']:.1f})")
    L.append(f"* view stage: overlap of the retained views with the exact top-tau = "
             f"{vs['overlap_with_exact_top_tau']:.2f}")
    qv = vs.get("query_attribute_views", [])
    if qv:
        L.append("* single-atom views on the query attributes (exact rank by Use / coverage / Rep): " + "; ".join(
            f"`{x['view']}` #{x['rank']} ({x['coverage']:.3f} / {x['representativeness']:.2f})" for x in qv[:6]))
    L.append("")
    L.append("| round | view | attribute | bins clearing 2σ | exact |Q1| / |Q2| in view |")
    L.append("|---|---|---|---|---|")
    for e in rep["explanations"]:
        L.append(f"| {e['round']} | `{e['view']}` | {e['attr']} | {', '.join(e['bins_clearing_2sigma']) or '—'} | "
                 f"{e['exact_total_q1']:,} / {e['exact_total_q2']:,} |")
    fig = base / "e1" / pid / "explanations.png"
    if fig.exists():
        L += ["", f"![{pid} released explanations](e1/{pid}/explanations.png)"]
    L.append("")
    return L


def _md(path: Path) -> str | None:
    return path.read_text() if path.exists() else None


def _img(base: Path, rel: str, alt: str) -> list[str]:
    return [f"![{alt}]({rel})", ""] if (base / rel).exists() else []


def build_report(base: Path | None = None) -> Path:
    """Assemble ``results/REPORT.md`` from whatever experiment outputs exist."""
    base = Path(base or RESULTS_DIR)
    L = ["# Results: Private Query Difference Explanations", ""]
    L.append("Generated from the raw data of each experiment (`pqde plot <exp>` rebuilds the figures). Every "
             "experiment varies one parameter and keeps the others at the defaults of `configs/experiments.yaml`; "
             "all experiments use the original statistics route of Section 4.2. Released quantities are "
             "differentially private; `exact_*` fields are non-private diagnostics used only to check statements.")
    L.append("")
    e1 = _read(base / "e1" / "summary.csv")
    if e1 is not None:
        L += ["## The query pairs", "", "Sources of every pair: [docs/PAIRS.md](../docs/PAIRS.md).", ""]
        L.append(to_markdown(e1[["pair", "dataset", "synthetic", "Q1", "Q2", "|Q1|", "|Q2|", "|P|", "tau", "gamma"]],
                             floatfmt="{:.1f}"))
    # ---------------------------------------------------------------- accuracy
    t3 = _md(base / "e2" / "table3_approx_ratio.md")
    if t3:
        meta = json.loads((base / "e2" / "metadata.json").read_text())
        L += ["## E2 — accuracy vs ε", "", f"Mean over {meta.get('trials')} private runs per point.", "",
              "**ApproxRatio** (F_λ with γ_eval = 0) against B1, B2, B3:", "", t3, "",
              "**Set agreement** with the baselines (precision@k = share of the k released explanations that the "
              "baseline also returns; Jaccard on the (view, attribute) sets):", "",
              _md(base / "e2" / "table_set_metrics.md") or "", ""]
        L += _img(base, "e2/eps_ratio_by_dataset.png", "ApproxRatio by dataset")
        L += _img(base, "e2/eps_precision_at_k_by_dataset.png", "precision@k by dataset")
        L += _img(base, "e2/eps_jaccard_by_dataset.png", "Jaccard by dataset")
        L += _img(base, "e2/eps_attr_precision_by_dataset.png", "attribute precision by dataset")
        L += _img(base, "e2/eps_release_quality.png", "release quality")
        L += ["Per-pair panels: `e2/eps_<metric>_by_pair.png`.", ""]
    g = _md(base / "e6" / "ratio_B2_by_gamma.md")
    if g:
        L += ["## E6 — accuracy vs γ", "", "ApproxRatio against B2; columns are γ / γ_Eq.(12) (0 = unsmoothed):", "",
              g, ""]
        L += _img(base, "e6/gamma_ratio_by_dataset.png", "ApproxRatio vs gamma")
        L += _img(base, "e6/gamma_precision_at_k_by_dataset.png", "precision@k vs gamma")
        L += _img(base, "e6/gamma_jaccard_by_dataset.png", "Jaccard vs gamma")
    m = _read(base / "e3" / "margins.csv")
    if m is not None:
        L += ["## E3 — what drives accuracy", "", "**Margins** (round-1 candidates of the exact top-τ views):", ""]
        L.append(to_markdown(m[["pair", "gamma", "smoothed_margin_abs", "smoothed_margin_rel", "unsmoothed_margin_rel",
                                "em_resolution", "margin_over_resolution", "use_gap_over_scale"]], floatfmt="{:.4g}"))
        bs = _read(base / "e3" / "bin_stats.csv")
        if bs is not None:
            L += ["**Bins vs γ:**", "", to_markdown(bs, floatfmt="{:.3g}")]
        for name, title in (("view_stage_overlap.md", "**View stage alone** — overlap of the retained views with the "
                             "exact top-τ, vs ε_P:"),
                            ("budget_split_ratio_B2.md", "**Budget split** — ApproxRatio vs B2 (ε = 1):"),
                            ("budget_split_precision_at_k_B2.md", "**Budget split** — precision@k vs B2 (ε = 1):")):
            t = _md(base / "e3" / name)
            if t:
                L += [title, "", t, ""]
    # ---------------------------------------------------------------- running time
    pts = _read(base / "e4" / "points.csv")
    if pts is not None:
        meta = json.loads((base / "e4" / "metadata.json").read_text())
        L += ["## E4 — end-to-end running time", "",
              f"PRIV_EXPL, B1, B2, B3 on the original route; OPT_PRIV_EXPL = PRIV_EXPL with O1 + O3. Time limit "
              f"{meta.get('timeout_s')} s per run (✕ = timeout). Mean over the pairs of each dataset of the median "
              f"over {meta.get('repeats')} repeats.", ""]
        L += _img(base, "e4/runtime_all_datasets.png", "running time, all datasets")
        for ds in dict.fromkeys(pts.dataset):
            L += _img(base, f"e4/runtime_{ds}.png", f"running time {ds}")
    dp = _md(base / "e5" / "default_point_per_pair.md")
    if dp:
        L += ["## E5 — cost per pair at the defaults, B2 growth, optimisations", "",
              "End-to-end seconds per pair (`speedup OPT` = PRIV_EXPL / OPT_PRIV_EXPL):", "", dp, ""]
        L += _img(base, "e5/fig8a_methods.png", "methods")
        L += _img(base, "e5/fig8b_b2_growth.png", "B2 growth")
        r = _md(base / "e5" / "routes.md")
        if r:
            L += ["**Statistics routes** (PRIV_EXPL end to end, mean over pairs, seconds):", "", r, ""]
            L += _img(base, "e5/routes.png", "routes")
        idt = _md(base / "e5" / "identity.md")
        if idt:
            L += ["**OPT_PRIV_EXPL releases exactly what PRIV_EXPL releases** (same randomness):", "", idt, ""]
    if e1 is not None:
        L += ["## E1 — one release per pair (ε = 1, k = 5)", ""]
        for pid in e1.pair:
            path = base / "e1" / pid / "report.json"
            if path.exists():
                L += _pair_section(pid, json.loads(path.read_text()), base)
    out = base / "REPORT.md"
    out.write_text("\n".join(L) + "\n")
    return out
