"""Experiment drivers E1-E5 (Section 5)."""

from . import e1_case_studies, e2_accuracy, e3_drivers, e4_scalability, e5_runtime

EXPERIMENTS = {
    "e1": e1_case_studies,
    "e2": e2_accuracy,
    "e3": e3_drivers,
    "e4": e4_scalability,
    "e5": e5_runtime,
}
