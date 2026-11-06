# Status and next steps (handoff note)

Keeps the state of the work outside the chat context.

## Running now: E7, |Attrs| (started 2026-11-06 ~20:57 IST)
Explanation attributes only (views, reference attributes fixed); 2 .. all usable attributes
(extra_explain_attrs); 10 random nested orders per pair (user's decisions).
* Runtime (e7t) in 6 cloud sessions, one dataset each, branch `...-e7-<name>`, dir
  `results_shards/e7-<name>`; check with `scripts/shards_status.sh e7`.
  acs session_01U646masakNHqcuvtD3XmYL (~1.5 h), ipums session_01U646mZwW6yoEUvYuc4qmiY,
  tax session_01U646mcYcXjShf6JNguuRjw, taxdirty session_01U646maG8J3kBq2VU5mYXJu,
  adult session_01U646mYrPFcKGomH1cjVWKW, hospital session_01U646mbyH5CbdQRy8NNV1QP.
* Accuracy (e7a) locally: `scripts/run_shard.sh e7-local 4` -> `results_shards/e7-local`.
* When done: fetch the 6 branches, `python scripts/merge_shards.py e7t e7a`, add a figure
  (runtime row + accuracy row per dataset) and a paragraph to the chapter.

## Re-run under paper v21: complete (2026-11-02)
Constants gamma_R = N/100, Delta_Use = 4/N; 10 runs per pair; time limit 30 min (3 runs per timed-out
point); dense sweeps; 22 runtime pairs; eps up to 20; E1 with 10 releases.
* Raw outputs per shard in `results_shards/` (local: E1, E2, E3, E6, cases, E5; one E4 shard per
  dataset, each run in its own cloud session); `scripts/merge_shards.py` assembled `results/`.
* Chapter updated (`paper/sections/experiments.tex`, figures `paper/figures/exp/`, Table 3 generated).
* Worker sessions (idle, results merged; archive only after the user agrees):
  acs session_01U646mbkQvS45WsTNyuCADG, ipums session_01U646mYnRNxbxCHf39gWQDL,
  tax session_01U646maADqDsytAW6NFEGAW, taxdirty session_01U646mYqG3EeSV2N3cSiiue,
  adult session_01U646mYoRALdiAgsPZcxVDk, hospital session_01U646mbkoEZuZ7sF2YatrzP.

## Open points (ask the user before changing)
* Chapter fixes discussed, not approved: column "Ratio vs B2/B3"; B1 vs B3 differ only in the gamma
  they select with; F(B1)/F(B3) as the cost of smoothing (Adult 0.79); "optimum over the exact top-tau
  candidates"; rename "Noise sometimes helps"; attribute precision (chance ~0.5) and Jaccard
  (= p/(2-p), redundant).
* ACSIncome: ratio vs B2/B3 > 1 at gamma >= 3x -> views outside the exact top-tau hold better
  explanations; which views, and why Use ranks them below tau (TODO in the chapter).
* Absolute times differ between machines (up to 1.7x, Tax); compare methods within a machine only.

## Decisions already taken by the user
* All experiments on the original route; optimisations only as OPT_PRIV_EXPL (O1 + O3).
* Derived constants (tau, gamma) follow their rules when k, eps or tau vary.
* Contrast pairs = DPXPlain's IPUMS questions, group attributes excluded.
* Erica pairs: Q' = Erica's own refinement that best tells the story; 44 pairs kept fixed.
* Tax CQA: Ni et al. 2024 rules without area_code->state (option b).
* Cite the source of every pair (Table 3 = paper/sections/pairs_table.tex, generated).
* Re-run: whole experiments in parallel, never a single timed run.
