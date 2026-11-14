# Status and next steps (handoff note)

Keeps the state of the work outside the chat context.

## E7, |Attrs|: complete (2026-11-06)
Merged into results/e7 (runtime 22 pairs, accuracy 44 pairs); figure paper/figures/exp/attrs.pdf;
chapter: paragraph "What the exhaustive search depends on" (Scalability) and subsection "The Number
of Attributes" (Quality).  Worker sessions (archived 2026-11-14):
acs session_01U646masakNHqcuvtD3XmYL, ipums session_01U646mZwW6yoEUvYuc4qmiY,
tax session_01U646mcYcXjShf6JNguuRjw, taxdirty session_01U646maG8J3kBq2VU5mYXJu,
adult session_01U646mYrPFcKGomH1cjVWKW, hospital session_01U646mbyH5CbdQRy8NNV1QP.
E7g (gamma fixed at its default) done: curves change by <= 0.04, so gamma is not the cause; the effect
is which attributes are added (HD sums over bins: wide attributes with large bins -- ACS POBP/ST --
raise accuracy; nativeCountry on Adult, many tiny bins, widens the smoothing gap). Open: cap wide
attributes or normalise HD by the number of bins (TODO in chapter).

## Re-run under paper v21: complete (2026-11-02)
Constants gamma_R = N/100, Delta_Use = 4/N; 10 runs per pair; time limit 30 min (3 runs per timed-out
point); dense sweeps; 22 runtime pairs; eps up to 20; E1 with 10 releases.
* Raw outputs per shard in `results_shards/` (local: E1, E2, E3, E6, cases, E5; one E4 shard per
  dataset, each run in its own cloud session); `scripts/merge_shards.py` assembled `results/`.
* Chapter updated (`paper/sections/experiments.tex`, figures `paper/figures/exp/`, Table 3 generated).
* Worker sessions (archived 2026-11-14):
  acs session_01U646mbkQvS45WsTNyuCADG, ipums session_01U646mYnRNxbxCHf39gWQDL,
  tax session_01U646maADqDsytAW6NFEGAW, taxdirty session_01U646mYqG3EeSV2N3cSiiue,
  adult session_01U646mYoRALdiAgsPZcxVDk, hospital session_01U646mbkoEZuZ7sF2YatrzP.

## Open points
* Chapter fixes applied 2026-11-14 (user approved): "Ratio vs B2/B3", B1 vs B3 differ only in gamma,
  F(B1)/F(B3) column (cost of smoothing), "optimum over the exact top-tau views", "Smoothing moves the
  target", Jaccard dropped (= p/(2-p)), attribute precision kept with its chance level
  (results/e2/attr_precision_chance.csv, scripts/attr_precision_chance.py).
* ACSIncome: ratio vs B2/B3 > 1 at large gamma -> views outside the exact top-tau (TODO in chapter).
* Wide attributes dominate HD (TODO in chapter).
* Absolute times differ between machines (up to 1.7x, Tax); compare methods within a machine only.
* The 12 worker sessions were archived on 2026-11-14 (user agreed); their results are in results_shards/.

## Decisions already taken by the user
* All experiments on the original route; optimisations only as OPT_PRIV_EXPL (O1 + O3).
* Derived constants (tau, gamma) follow their rules when k, eps or tau vary.
* Contrast pairs = DPXPlain's IPUMS questions, group attributes excluded.
* Erica pairs: Q' = Erica's own refinement that best tells the story; 44 pairs kept fixed.
* Tax CQA: Ni et al. 2024 rules without area_code->state (option b).
* Cite the source of every pair (Table 3 = paper/sections/pairs_table.tex, generated).
* Re-run: whole experiments in parallel, never a single timed run.
