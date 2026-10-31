"""pqde -- Private Query Difference Explanations.

Reproduction of the algorithms and experiments of the paper
"Private Query Difference Explanations":

* :mod:`pqde.measures`    HD_gamma, Rep, Cov, Use, Div, F_w (Section 3.2)
* :mod:`pqde.stats`       one-off statistics cache over views (Section 4.2)
* :mod:`pqde.mechanisms`  Laplace, exponential and one-shot top-k mechanisms (Section 2.5)
* :mod:`pqde.algorithm`   Algorithms 1 and 2 (Section 4)
* :mod:`pqde.baselines`   B1-B3 and ApproxRatio (Section 5.1)
* :mod:`pqde.refinement`  ERICA-style query refinement (Definition 2.5)
* :mod:`pqde.cqa`         conflict-hypergraph consistent answers (Definition 2.7)
* :mod:`pqde.pairs`       the twelve query pairs of Table 2
* :mod:`pqde.experiments` E1-E5
"""

from .algorithm import Params, Result, explain
from .stats import StatsCache, build_cache

__version__ = "0.1.0"
__all__ = ["Params", "Result", "explain", "StatsCache", "build_cache", "__version__"]
