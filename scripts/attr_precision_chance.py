"""Chance level of attribute precision at the defaults (results/e2/attr_precision_chance.csv).

For every pair: the optimum R (B3 = B2) over the candidates of the exact top-tau views, and
random sets of k candidates drawn uniformly from that same pool; the chance level is the mean
attribute precision of a random set against R (multiset overlap of the attributes / k).
"""

from collections import Counter

import numpy as np
import pandas as pd

from pqde.baselines import b3, exact_top_views
from pqde.experiments.common import default_cache, experiments_config, make_params, stable_key

cfg = experiments_config()
d = cfg["defaults"]
rows = []
for pid in cfg["pairs"]:
    cache = default_cache(pid, d)
    p = make_params(d, cache.n_views, len(cache.explain_attrs))
    ref = Counter(a for _, a in b3(cache, p, float(d.get("gamma_eval", 0.0))))
    views = exact_top_views(cache, p.tau)
    pool = [a for v in views for a in cache.explain_attrs if cache.valid[a][v]]
    rng = np.random.default_rng([int(d["seed"]), stable_key(pid)])
    vals = [sum((Counter(pool[i] for i in rng.choice(len(pool), p.k, replace=False)) & ref).values()) / p.k
            for _ in range(5000)]
    rows.append({"pair": pid, "dataset": cache.ds.name, "pool": len(pool), "chance_attr_precision": float(np.mean(vals))})
    print(pid, rows[-1]["chance_attr_precision"], flush=True)
out = pd.DataFrame(rows)
out.to_csv("results/e2/attr_precision_chance.csv", index=False)
print(out.groupby("dataset").chance_attr_precision.mean().round(3).to_dict())
