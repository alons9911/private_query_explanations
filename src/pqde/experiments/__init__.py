"""Experiment drivers E1-E5 (Section 5)."""

from . import case_studies, e1_case_studies, e2_accuracy, e3_drivers, e4_scalability, e5_runtime, pair_search

EXPERIMENTS = {
    "e1": e1_case_studies,
    "e2": e2_accuracy,
    "e3": e3_drivers,
    "e4": e4_scalability,
    "e5": e5_runtime,
    "search": pair_search,
    "cases": case_studies,
}
