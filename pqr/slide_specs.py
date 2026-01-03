from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .experiments import AlgorithmName, RunSpec


def _cond(attr: str, op: str, value: Any) -> dict[str, Any]:
    return {"attr": attr, "op": op, "value": value}


def slide41_suite(*, ipums_csv: str | None, stackoverflow_csv: str | None) -> list[RunSpec]:
    """
    Slide 41 “Experiments” table: datasets + specific query pairs + expected explanation attributes.

    Notes:
    - IPUMS-CPS typically requires manual download / export; you must provide `ipums_csv`.
    - StackOverflow survey can be downloaded publicly, but file naming and column names vary by year;
      you must provide `stackoverflow_csv` (or download it in Colab and pass the path).

    Default settings (from slide 41):
    - K = 3
    - Tau = 50
    - epsilon = 1
    - predicates = all combinations of A1=v1 AND A2=v2  (we implement pairwise view generation)
    - # trials = 10 (configure via CLI `--repeats 10`)
    """

    specs: list[RunSpec] = []

    if ipums_csv:
        # IPUMS-CPS (downsampled to 100k tuples in the slides)
        base = dict(
            dataset_csv=ipums_csv,
            dataset_name="ipums_cps",
            predicate_view_mode="pairwise",
            # A reasonable default predicate attribute set; adjust for your IPUMS extract.
            predicate_attrs=["SEX", "AGE", "RACE", "EDUC", "INCTOT", "UHRSWORK"],
            max_values_per_predicate_attr=50,
            algorithm=AlgorithmName.PRIVATE,
            k=3,
            tau=50,
            epsilon=1.0,
        )

        # Q1: Full time vs part time
        specs.append(
            RunSpec(
                **base,
                label="Q1_full_time_vs_part_time",
                q1={"conditions": [_cond("EMPSTAT", "==", "Employed"), _cond("UHRSWORK", ">=", 35)]},
                q2={"conditions": [_cond("EMPSTAT", "==", "Employed"), _cond("UHRSWORK", "<", 35)]},
                attributes=["UHRSWORK", "SEX", "AGE", "EDUC", "INCTOT"],
            )
        )
        # Q2: With/without higher education
        specs.append(
            RunSpec(
                **base,
                label="Q2_higher_ed_vs_not",
                q1={
                    "conditions": [
                        _cond("EMPSTAT", "==", "Employed"),
                        _cond("EDUC", ">=", "Bachelor''s degree"),
                    ]
                },
                q2={
                    "conditions": [
                        _cond("EMPSTAT", "==", "Employed"),
                        _cond("EDUC", "<", "Bachelor''s degree"),
                    ]
                },
                attributes=["SEX", "AGE", "EDUC", "INCTOT", "RACE"],
            )
        )
        # Q3: High income vs low income
        specs.append(
            RunSpec(
                **base,
                label="Q3_high_income_vs_low_income",
                q1={"conditions": [_cond("EMPSTAT", "==", "Employed"), _cond("INCTOT", ">=", 60000)]},
                q2={"conditions": [_cond("EMPSTAT", "==", "Employed"), _cond("INCTOT", "<", 30000)]},
                attributes=["SEX", "AGE", "EDUC", "INCTOT", "RACE"],
            )
        )

    if stackoverflow_csv:
        base = dict(
            dataset_csv=stackoverflow_csv,
            dataset_name="stack_overflow_survey",
            predicate_view_mode="pairwise",
            # Slide 41 suggests these as key axes; adjust to match your survey CSV column names.
            predicate_attrs=["DevType", "Country", "YearsCodePro", "CompanySize", "WorkRemote", "UsingAI", "Satisfaction"],
            max_values_per_predicate_attr=50,
            algorithm=AlgorithmName.PRIVATE,
            k=3,
            tau=50,
            epsilon=1.0,
        )

        # Q4: Professional vs non-professional
        specs.append(
            RunSpec(
                **base,
                label="Q4_pro_vs_non_pro",
                q1={"conditions": [_cond("YearsCodePro", ">=", 10)]},
                q2={"conditions": [_cond("YearsCodePro", "<", 4)]},
                attributes=["DevType", "CodeLanguage"],
            )
        )
        # Q5: Remote vs on-site
        specs.append(
            RunSpec(
                **base,
                label="Q5_remote_vs_on_site",
                q1={"conditions": [_cond("WorkRemote", "==", "Fully remote")]},
                q2={"conditions": [_cond("WorkRemote", "==", "On-Site")]},
                attributes=["DevType", "Country", "YearsCodePro", "CompanySize"],
            )
        )
        # Q6: Impact of using AI tools on satisfaction
        specs.append(
            RunSpec(
                **base,
                label="Q6_ai_impact_on_satisfaction",
                q1={"conditions": [_cond("Satisfaction", ">", 5), _cond("UsingAI", "==", "yes")]},
                q2={"conditions": [_cond("Satisfaction", ">", 5), _cond("UsingAI", "==", "no")]},
                attributes=["DevType", "CodeLanguage", "YearsCodePro", "Country"],
            )
        )

    return specs

