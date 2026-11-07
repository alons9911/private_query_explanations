"""LaTeX tables for the experiments section, generated from the configs and the results.

``python -m pqde.paper_tables`` writes ``paper/sections/pairs_table.tex``: every
query pair of the experiments with its two queries, its constraint, its output
sizes and, per dataset, where the pairs come from.  ACS codes are shown by name.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper" / "sections" / "pairs_table.tex"

# pairs that duplicate another pair: shown once, counted once
DUPLICATES = {"C4": "H1", "R6": "T2"}
CASE_STUDIES = {"A2", "ACS_Q1C1", "C1", "I1"}

GROUPS = [
    ("adult", r"Adult~\cite{adult-uci}. A1 and A2 (the running example) from the earlier draft; A3 and R1--R4: $Q'$ from our refinement search."),
    ("acsincome", r"ACSIncome~\cite{DingHMS21}. Queries $Q_i$, constraint sets $C_j$ and refined queries $Q'$ of Erica~\cite{LMSJ23}; $Q'$ is one of the minimal refinements Erica returned."),
    ("tax", r"Tax~\cite{BohannonFGJK07,MahdaviAFMOST19}. T1 from the earlier draft; T2, T3 and R5: $Q'$ from our refinement search (R6 of the case-study search is the same pair as T2)."),
    ("tax_dirty", r"Tax-dirty~\cite{MahdaviAFMOST19}, CQA. $\Sigma$ = the Tax rules of~\cite{NiMZWLY24} without $\texttt{AreaCode}\to\texttt{State}$; $Q$ = US Census divisions picked by our selection rule."),
    ("hospital", r"Hospital~\cite{rekatsinas2017}, CQA. $\Sigma=\{\texttt{HospitalName}\to\texttt{ZipCode}, \texttt{HospitalName}\to\texttt{PhoneNumber}, \texttt{ZipCode}\to\texttt{City}\}$; H1 from the earlier draft, H2 and H3 by our selection rule."),
    ("ipums", r"IPUMS-CPS~\cite{TaoGMR22}, contrasts. The questions of DPXPlain (I1 is its default question); the attribute that defines the groups is excluded from the views and the explanation attributes."),
]


def _labels() -> dict:
    ds = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text())
    return ds["acsincome"].get("value_labels", {})


def _sql(s: str, labels: dict) -> str:
    s = str(s)
    if s.startswith("Q_Sigma("):
        return r"$Q_\Sigma$"

    def lab(m):  # ACS codes -> names, e.g. COW IN ('3', '4') -> COW IN (local-gov, state-gov)
        attr, rest = m.group(1), m.group(2)
        table = labels.get(attr, {})
        return attr + re.sub(r"'?(\d+)'?", lambda x: table.get(x.group(1), x.group(1)), rest)

    if labels:
        s = re.sub(r"\b(COW|MAR|RAC1P|RELP)(\s*(?:=\s*'?\d+'?|IN\s*\([^)]*\)))", lab, s)
    s = s.replace("''", "\x00").replace("'", "").replace("\x00", "'")
    s = s.replace("Rate <= 3.2016153", "Rate <= 3.2")
    s = s.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")
    s = s.replace("$", r"\$").replace("#", r"\#")
    s = s.replace(" >= ", r"$\,\ge\,$").replace(" <= ", r"$\,\le\,$").replace(" > ", r"$\,>\,$").replace(" < ", r"$\,<\,$")
    s = s.replace("<20K", r"$<$20K").replace(">60K", r"$>$60K")
    s = s.replace(" AND ", r" $\wedge$ ")
    return r"\texttt{" + s + "}"


def _constraint(cs, labels: dict) -> str:
    if not cs:
        return "--"
    out = []
    for c in cs:
        if "min_share" in c or "max_share" in c:
            sh = c.get("min_share", c.get("max_share"))
            op = r"$\ge$" if "min_share" in c else r"$\le$"
            if "where" in c:
                what = _sql(c["where"], labels)
            elif "values" in c:
                what = _sql(f"{c['attr']} IN (" + ", ".join(c["values"]) + ")", labels)
            else:
                what = _sql(f"{c['attr']} = {c['value']}", labels)
            out.append(f"{op}{sh * 100:.0f}\\% {what}")
        else:
            n = c.get("min_count", c.get("max_count"))
            op = r"$\ge$" if "min_count" in c else r"$\le$"
            out.append(f"{op}{n:,} {_sql(c['where'], labels)}".replace(",", "{,}"))
    return "; ".join(out)


def _id(pid: str) -> str:
    t = pid.replace("ACS_", "")
    t = re.sub(r"^Q(\d)C(\d)$", r"$Q_\1C_\2$", t)
    return r"\textbf{" + t + "}" if pid in CASE_STUDIES else t


def pairs_table() -> Path:
    cfg = yaml.safe_load((ROOT / "configs" / "experiments.yaml").read_text())
    P = yaml.safe_load((ROOT / "configs" / "pairs.yaml").read_text())
    s = pd.read_csv(ROOT / "results" / "e1" / "summary.csv").set_index("pair")
    labels = _labels()
    pids = [p for p in cfg["pairs"] if p not in DUPLICATES]
    rows = {g: [] for g, _ in GROUPS}
    for pid in pids:
        r = s.loc[pid]
        lab = labels if r.dataset == "acsincome" else {}
        n1, n2 = int(r["|Q1|"]), int(r["|Q2|"])
        sizes = (f"{n1:,} / {n2:,}" if P[pid].get("kind") == "contrast" else f"{n1:,}$\\to${n2:,}").replace(",", "{,}")
        rows[r.dataset].append(f"{_id(pid)} & {_sql(r.Q1, lab)} & {_sql(r.Q2, lab)} & "
                               f"{_constraint(P[pid].get('constraints'), lab)} & {sizes} \\\\")
    total = sum(len(v) for v in rows.values())

    def part(groups, first: bool) -> list[str]:
        cap = (rf"The {total} query pairs of the experiments, by dataset. Bold: the case studies of Section~\ref{{sec:usecase-results}}. "
               r"$|Q_1|\to|Q_2|$: output sizes ($|Q_1|$ / $|Q_2|$ for contrasts). ACS codes are shown by name; "
               r"\texttt{SCHL} 16 = high-school diploma, 19 = some college, 21 = bachelor's, 22 = master's, 23 = professional degree.") \
            if first else r"The query pairs of the experiments (continued)."
        L = [r"\begin{table*}[t]", r"\centering", r"\scriptsize"]
        if not first:
            L.append(r"\ContinuedFloat")
        L += [rf"\caption{{{cap}}}"]
        if first:
            L.append(r"\label{tab:pairs}")
        L += [r"\setlength{\tabcolsep}{3pt}", r"\renewcommand{\arraystretch}{1.08}",
              r"\begin{tabularx}{\textwidth}{@{}l>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}p{3.6cm}r@{}}",
              r"\toprule", r"ID & $Q_1$ & $Q_2$ & Constraint & $|Q_1|\to|Q_2|$\\"]
        for g, head in groups:
            if not rows[g]:
                continue
            L += [r"\midrule", rf"\multicolumn{{5}}{{@{{}}p{{\textwidth}}@{{}}}}{{\emph{{{head}}}}}\\[1pt]"]
            L += rows[g]
        L += [r"\bottomrule", r"\end{tabularx}", r"\end{table*}"]
        return L

    lines = ["% generated by `python -m pqde.paper_tables` from configs/ and results/e1/summary.csv -- do not edit"]
    lines += part(GROUPS[:3], True) + [""] + part(GROUPS[3:], False)
    OUT.write_text("\n".join(lines) + "\n")
    return OUT


if __name__ == "__main__":
    print(pairs_table())
