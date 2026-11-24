"""Accuracy metrics for a released explanation set (Section 5.3.1 and beyond ApproxRatio).

Set-level comparisons against a reference set ``R`` (B1, B2 or B3) with
``|E| = |R| = k`` explanations ``(view, attribute)``:

* ``approx_ratio``   F_lambda(E) / F_lambda(R) with gamma_eval = 0 (the paper's metric)
* ``jaccard``        |E ∩ R| / |E ∪ R|
* ``precision_at_k`` |E ∩ R| / k  (= recall at k, since both sets have k members)
* ``attr_precision`` multiset overlap of the explained attributes / k -- partial
                     credit for explaining the right attribute in another view
* ``view_jaccard``   Jaccard of the sets of views used

Release-level metrics on the noisy histograms themselves:

* ``hist_rel_l1``    sum |noisy - exact| / sum exact over both outputs and all bins
* ``diff_sign_acc``  among bins whose exact difference H1 - H2 is non-zero, the
                     share whose released difference has the same sign
"""

from __future__ import annotations

from collections import Counter
from typing import Hashable, Sequence

import numpy as np

SET_METRICS = ("jaccard", "precision_at_k", "attr_precision", "view_jaccard")


def set_metrics(released: Sequence[tuple[Hashable, str]], reference: Sequence[tuple[Hashable, str]],
                k: int | None = None) -> dict:
    E, R = set(released), set(reference)
    k = k or max(len(R), 1)
    inter = len(E & R)
    union = len(E | R)
    ae, ar = Counter(a for _, a in released), Counter(a for _, a in reference)
    ve, vr = {v for v, _ in released}, {v for v, _ in reference}
    return {
        "jaccard": inter / union if union else float("nan"),
        "precision_at_k": inter / k,
        "attr_precision": sum((ae & ar).values()) / k,
        "view_jaccard": len(ve & vr) / len(ve | vr) if (ve | vr) else float("nan"),
    }


def release_metrics(explanations) -> dict:
    """Error of the released histograms (explanations of a :class:`pqde.algorithm.Result`)."""
    num = den = 0.0
    agree = total = 0
    for e in explanations:
        num += np.abs(e.noisy_h1 - e.exact_h1).sum() + np.abs(e.noisy_h2 - e.exact_h2).sum()
        den += e.exact_h1.sum() + e.exact_h2.sum()
        d_ex = e.exact_h1 - e.exact_h2
        d_no = e.noisy_h1 - e.noisy_h2
        nz = d_ex != 0
        agree += int((np.sign(d_no[nz]) == np.sign(d_ex[nz])).sum())
        total += int(nz.sum())
    return {"hist_rel_l1": num / den if den else float("nan"),
            "diff_sign_acc": agree / total if total else float("nan")}
