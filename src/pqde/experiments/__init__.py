"""Experiment drivers (Section 5).  Each module has ``run(cfg, ...)`` and, where it
produces figures from raw data, ``plot(cfg, base)``."""

from . import case_studies, e1_case_studies, e2_accuracy, e3_drivers, e4_scalability, e5_runtime, e6_gamma, pair_search

EXPERIMENTS = {
    "e1": e1_case_studies,
    "e2": e2_accuracy,
    "e3": e3_drivers,
    "e4": e4_scalability,
    "e5": e5_runtime,
    "e6": e6_gamma,
    "search": pair_search,
    "cases": case_studies,
}
