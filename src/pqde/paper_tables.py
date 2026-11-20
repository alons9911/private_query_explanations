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
    ("adult", r"Adult~\cite{adult-uci}: refinements under representation constraints (ours); A2 is the running example of Section~\ref{sec:introduction}."),
    ("acsincome", r"ACSIncome~\cite{DingHMS21}: queries, constraints and refinements of Erica~\cite{LMSJ23}."),
    ("tax", r"Tax~\cite{BohannonFGJK07,MahdaviAFMOST19}: refinements under representation constraints (ours)."),
    ("tax_dirty", r"Tax-dirty~\cite{MahdaviAFMOST19}: consistent answers under the Tax rules of~\cite{NiMZWLY24} (ours)."),
    ("hospital", r"Hospital~\cite{rekatsinas2017}: consistent answers under $\texttt{HospitalName}\to\texttt{ZipCode}$, $\texttt{HospitalName}\to\texttt{PhoneNumber}$, $\texttt{ZipCode}\to\texttt{City}$ (ours)."),
    ("ipums", r"IPUMS-CPS~\cite{TaoGMR22}: the questions of DPXPlain~\cite{TaoGMR22}; the attribute that defines the groups is excluded from views and explanation attributes."),
]

# paper IDs: one letter per dataset, numbered in table order (internal pair ids stay as in configs/pairs.yaml)
PREFIX = {"adult": "A", "acsincome": "S", "tax": "T", "tax_dirty": "D", "hospital": "H", "ipums": "I"}


def display_ids() -> dict[str, str]:
    cfg = yaml.safe_load((ROOT / "configs" / "experiments.yaml").read_text())
    P = yaml.safe_load((ROOT / "configs" / "pairs.yaml").read_text())
    count: dict[str, int] = {}
    out = {}
    for pid in cfg["pairs"]:
        if pid in DUPLICATES:
            continue
        ds = P[pid]["dataset"]
        count[ds] = count.get(ds, 0) + 1
        out[pid] = f"{PREFIX[ds]}{count[ds]}"
    return out


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
    t = display_ids()[pid]
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
        rows[r.dataset].append((_id(pid), _sql(r.Q1, lab), _sql(r.Q2, lab), _constraint(P[pid].get("constraints"), lab)))
    total = sum(len(v) for v in rows.values())

    def part(groups, first: bool) -> list[str]:
        """The first part (refinement pairs) has a constraint column; the second (CQA and contrasts) has none."""
        with_constraint = any(row[3] != "--" for g, _ in groups for row in rows[g])
        cap = (rf"The {total} query pairs of the experiments, by dataset. Bold: the case studies of Section~\ref{{sec:usecase-results}}. "
               r"ACS codes are shown by name; "
               r"\texttt{SCHL} 16 = high-school diploma, 19 = some college, 21 = bachelor's, 22 = master's, 23 = professional degree.") \
            if first else r"The query pairs of the experiments (continued)."
        L = [r"\begin{table*}[t]", r"\centering", r"\scriptsize"]
        if not first:
            L.append(r"\ContinuedFloat")
        L += [rf"\caption{{{cap}}}"]
        if first:
            L.append(r"\label{tab:pairs}")
        L += [r"\setlength{\tabcolsep}{3pt}", r"\renewcommand{\arraystretch}{1.08}",
              (r"\begin{tabularx}{\textwidth}{@{}l>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}p{4.4cm}@{}}"
               if with_constraint else
               r"\begin{tabularx}{\textwidth}{@{}l>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X@{}}"),
              r"\toprule", r"ID & $Q_1$ & $Q_2$ & Constraint\\" if with_constraint else r"ID & $Q_1$ & $Q_2$\\"]
        ncol = 4 if with_constraint else 3
        for g, head in groups:
            if not rows[g]:
                continue
            L += [r"\midrule", rf"\multicolumn{{{ncol}}}{{@{{}}p{{\textwidth}}@{{}}}}{{\emph{{{head}}}}}\\[1pt]"]
            L += [" & ".join(row[:ncol]) + r" \\" for row in rows[g]]
        L += [r"\bottomrule", r"\end{tabularx}", r"\end{table*}"]
        return L

    lines = ["% generated by `python -m pqde.paper_tables` from configs/ and results/e1/summary.csv -- do not edit"]
    lines += part(GROUPS[:3], True) + [""] + part(GROUPS[3:], False)
    OUT.write_text("\n".join(lines) + "\n")
    return OUT


ATTR_OUT = ROOT / "paper" / "sections" / "attributes_table.tex"
DS_NAMES = {"adult": "Adult", "acsincome": "ACSIncome", "tax": "Tax", "tax_dirty": "Tax-dirty",
            "hospital": "Hospital", "ipums": "IPUMS-CPS"}


def attributes_table() -> Path:
    """Appendix table: per dataset, the view attributes and the explanation (= reference) attributes
    with their number of bins; the attributes added only in the |Attrs| experiment in italics."""
    from .data import load_dataset

    cfg = yaml.safe_load((ROOT / "configs" / "datasets.yaml").read_text())
    tt = lambda a: r"\texttt{" + a.replace("_", r"\_") + "}"
    rows = []
    for ds, name in DS_NAMES.items():
        c = cfg[ds]
        data = load_dataset(ds)
        expl = list(c["explain_attrs"])
        extra = [a for a in (c.get("extra_explain_attrs") or []) if a not in expl]
        items = [f"{tt(a)} ({len(data.domains[a])})" for a in expl]
        items += [r"\emph{" + f"{tt(a)} ({len(data.domains[a])})" + "}" for a in extra if a in data.domains]
        rows.append(f"{name} & " + ", ".join(tt(a) for a in c["view_attrs"]) + " & " + ", ".join(items) + r" \\")
    L = ["% generated by `python -m pqde.paper_tables` from configs/datasets.yaml -- do not edit",
         r"\begin{table*}[t]", r"\centering", r"\scriptsize",
         r"\caption{Attributes of the experiments. Views are conjunctions of at most two conditions on the view "
         r"attributes; the explanation and the reference attributes coincide (number of bins in parentheses). "
         r"In italics: the attributes added only in the experiment on $|\Attrs|$ (Section~\ref{subsec:attrs}). "
         r"On IPUMS-CPS the attribute that defines the two groups of a question is removed from both lists.}",
         r"\label{tab:attributes}", r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabularx}{\textwidth}{@{}l>{\raggedright\arraybackslash}p{4.6cm}>{\raggedright\arraybackslash}X@{}}",
         r"\toprule", r"Dataset & View attributes & Explanation and reference attributes (bins)\\", r"\midrule",
         *rows, r"\bottomrule", r"\end{tabularx}", r"\end{table*}"]
    ATTR_OUT.write_text("\n".join(L) + "\n")
    return ATTR_OUT


if __name__ == "__main__":
    print(pairs_table())
    print(attributes_table())
