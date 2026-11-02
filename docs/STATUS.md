# Status and next steps (handoff note)

Keeps the state of the work outside the chat context.

## Running now: re-run under paper v21 (started 2026-11-02 ~02:13 IST)
Constants: gamma_R = N/100, Delta_Use = 4/N.  10 runs per pair everywhere; time limit 30 min;
a timed point that hits the limit is run 3 times (nothing inferred).  Dense sweeps, 22 runtime
pairs, eps up to 20, E1 with 10 releases (figures: release 1 with all 5 explanations + stability).

* Local shard (this container): `scripts/run_shard.sh local 4` -> `results_shards/local/`
  (E5 per pair, E1, E2, E6, E3, cases).  Log: `results_shards_local.log`.
* E4 shards in cloud sessions, one dataset per machine, each pushes `results_shards/<name>/`
  to branch `claude/git-repo-experiments-f0705v-shard-<name>`:
  | shard | session | expected |
  |---|---|---|
  | acs | session_01U646mbkQvS45WsTNyuCADG | ~10 h |
  | ipums | session_01U646mYnRNxbxCHf39gWQDL | ~6 h |
  | tax | session_01U646maADqDsytAW6NFEGAW | ~5 h |
  | taxdirty | session_01U646mYqG3EeSV2N3cSiiue | ~5 h |
  | adult | session_01U646mYoRALdiAgsPZcxVDk | ~6 h |
  | hospital | session_01U646mbkoEZuZ7sF2YatrzP | ~6 h |

## When everything is done
1. Fetch the six shard branches; merge `results_shards/*` into `results/` (concatenate the raw
   CSVs of E4/E5 per experiment; E1/E2/E3/E6/cases come from the local shard), then
   `pqde plot e1 e2 e3 e4 e5 e6`, `python -m pqde.paper_figures`, `python -m pqde.paper_tables`.
2. Update `paper/sections/experiments.tex`: all numbers, remove the TODO about old constants,
   case-study figures with all 5 explanations of release 1 + stability across the 10 releases.
   Pending chapter fixes the user discussed (not yet approved): column "Ratio vs B2/B3",
   B1 vs B3 differ only in the gamma they select with, F(B1)/F(B3) as the cost of smoothing,
   "optimum over the exact top-tau candidates", rename "Noise sometimes helps", attribute
   precision (chance level ~0.5) and Jaccard (= p/(2-p), redundant) -- ask before changing.
3. Archive the six worker sessions once their results are merged.

## Decisions already taken by the user
* All experiments on the original route; optimisations only as OPT_PRIV_EXPL (O1 + O3).
* Derived constants (tau, gamma) follow their rules when k, eps or tau vary.
* Contrast pairs = DPXPlain's IPUMS questions, group attributes excluded.
* Erica pairs: Q' = Erica's own refinement that best tells the story; 44 pairs kept fixed.
* Tax CQA: Ni et al. 2024 rules without area_code->state (option b).
* Cite the source of every pair (Table 3 = paper/sections/pairs_table.tex, generated).
* Re-run: whole experiments in parallel, never a single timed run.
