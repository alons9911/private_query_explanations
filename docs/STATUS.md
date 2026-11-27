# Status and next steps (handoff note)

Keeps the state of the work outside the chat context.

## 2026-11-27 evening: HANDOFF (the user sees this session in English; a new session may continue)
Read this section first.  The user writes in Hebrew and wants answers in Hebrew.
* Paper: paper/ = the user's Overleaf version (zip "Private_Query_Refinement_5", copied 2026-11-27)
  + our refinement-only experiments chapter, figures, appendix tables, 3 bib entries (COMPAS, LSAC, MEPS),
  and `\input{sections/pairs_table}` in the appendix.  User: do NOT change sections/introduction.tex or
  Example B.2 in sections/appendix.tex for now (B.2 cites fig:case-c1, now commented out -> "Figure ??").
  Upload package for Overleaf: docs/overleaf_update.zip (rebuild it after changes; Overleaf does not unzip).
* Names (macros.tex, the user's): \sys = PEEQ, \sysopt = OptPEEQ, \Bone = NonPrivate, \BF = OPT (the
  non-private optimum over all views, computed exactly by greedy), \Btwo = Exhaustive (exhaustive search over
  the retained views).  Figure legends read these from paper/macros.tex (src/pqde/paper_figures.py NAME).
* Open decisions (ask the user, Hebrew):
  1. Erica's own pairs (pilot, results/erica_pilot/scores.csv, scripts/erica_pilot_*.py, pairs EA*/EC*/EH*):
     PEEQ 0.54-0.82 of OPT where the refinement changes hundreds of tuples (EA2, EC1, EC2), ~random where it
     changes tens (EA1, EC3, all Healthcare, N = 887).  User (2026-11-27 21:00): run the experiments on
     them now, decide later whether they go in the paper ("maybe only the running times").  Until then
     their results stay OUT of results/ and of the chapter.
  2. Contributions bullet of the introduction: user said "not yet".
* Quality suite on Erica's 10 pairs (EA1 EA2 EA4 EC1 EC2 EC3 EH1 EH2 EH3 EH5): running locally,
  `python -m pqde run e2 e3 e6 e8 | e7a e7g --pairs ... --out results_erica` (gitignored; logs
  results_erica/q1.log, q2.log).  When done: copy the raw CSVs to results/erica_pairs/ (committed), and
  summarise with their own script; do NOT append them to results/.
* Runtime rerun, RUNNING since 2026-11-27 21:17 (approved option a + the user's 21:00 go-ahead): every
  method of pqde.runner -- PRIV_EXPL (PEEQ), OPT_PRIV_EXPL (OptPEEQ), B1 (NonPrivate), B2 (Exhaustive), B3,
  OPT, SINGLE_STAGE, EXH_ALL (exhaustive over every view, pruned) and EXH_NAIVE (unpruned; E4 k sweep and
  E5 default point only; extrapolated, recorded as timeout + inferred, when its first block says it cannot
  fit in 30 min).  Methods without a view stage build without Use (stats rep="none") and pay for every
  view's histograms.  E4, E5, E7t, E7t7 on the 36 refinement pairs + Erica's 10.  12 cloud shards rt-1..12
  (tag pqde-rt, branches ...-rt-<n>, `scripts/shards_status.sh rt`; plan scripts/plan_runtime_shards.py,
  estimated ~32 h each, 1,500 process-hours in all).  Sessions: rt-1 session_01U646mbbEX3ZMekyoEYEhpW,
  rt-2 ..mYV6bZmAsH3QAAGRdV, rt-3 ..mcC7Vy6YNGeQhYJY8J, rt-4 ..maCX112GxzmvmUSoEy, rt-5 ..mbHYeTPcSDGUKifcmj,
  rt-6 ..mbXR5h1gsxCmbdpDYd, rt-7 ..mb572zPWHUN71WUGPZ, rt-8 ..maCBu4hm9MuJXpYZxD, rt-9 ..mYpHFm9PiYEHqRiEaW,
  rt-10 ..mZwjW8ruvGCNRwzaig, rt-11 ..mb8g6ZnDrwNgydVwZQ, rt-12 ..maJGX1JpTCk582CJfA (prefix session_01U646).
  When done: fetch the branches into results_shards/, merge (`scripts/merge_shards.py --shard 'rt-*'
  e4 e5 e7t e7t7`; keep Erica's pairs out of the paper's figures until the user decides), redraw Figure 11,
  rewrite the runtime paragraph, remove its \alon note.
* PREVIEW of the runtime rerun, RUNNING since 2026-11-27 21:36 (user chose option a: results within ~10 h
  for writing, the full rerun above continues and replaces them later): configs/experiments_preview.yaml
  (3 repeats per point, E7 3 attribute orders, early_stop_factor 2 for B2/EXH_ALL: stop after the first
  block when it says > 2x the time left; estimate within 10-16% of actual), E4 one job per (pair, sweep).
  12 cloud shards pv-1..12 (tag pqde-pv, branches ...-pv-<n>, `scripts/shards_status.sh pv`, plan
  scripts/plan_preview_shards.py, est. 6.3 h).  Sessions (prefix session_01U646): pv-1 mZEcyBPskN7uS4DVPG,
  pv-2 md7GK7UDEASmAAJhqd, pv-3 mcuz9yCpjG9nksJqbR, pv-4 mYxUscqpdKa4YEdckX, pv-5 mbYNP3iA3JFiu5X8zc,
  pv-6 maMmN7BAB8AT5c54wb, pv-7 maLftCki2CKHyPTUVk, pv-8 mbBoNLAB4KE9suQWvo, pv-9 mcAt5rKCemfxVBBAy6,
  pv-10 mYy6pVpTo4PVkHpkpx, pv-11 mcsQseSvEMspNhYTNq, pv-12 mYwpgLnTpataST7z7o.  When done: merge into a
  SEPARATE directory (not results/), draft the runtime paragraph and Figure 11 from it, marked provisional.
* Still running (old 5-method runtime, superseded by the rerun above): shards new-3, fix-1..3
  (`scripts/shards_status.sh new|fix`).  Ask the user before stopping or archiving them.
* Overleaf Git: credential for git.overleaf.com saved but refused (probably saved as a bearer token; needs
  username "git" + token as password).  The user pasted a token in the chat: advise revoking it.

## 2026-11-27: refinement-only experiments (user: query refinement is the main use case)
* Later the same day (user: 1 yes, 2 replace, 3 a, 4 replace): refine() now tightens every changed
  condition over all data values and dominating_refinements() checks Erica's minimality; L3, L5, M2,
  M5, T4 (R5) tightened, A1 and T1 replaced (A1's draft Q' dropped a condition; T1's Q satisfied its
  constraint).  A2 is not minimal either (education unchanged and hoursPerWeek >= 40 dominates it):
  user chose (a), keep A2 and change the introduction's wording (not "Erica produced Q2") -- the
  intro lives in the user's Overleaf, so the sentence is given to the user to paste.
* Quality of the 7 pairs: scripts/fix_pairs_quality.sh (results_fix/, appended); runtime: shards
  fix-1..3 (tag pqde-fix7), `scripts/shards_status.sh fix`; their stale rows were dropped from
  results/e4, e5 and e7 runtime CSVs.  Merge later with priority to fix-*.
* Chapter: refinement only (36 pairs, 6 datasets), CQA/contrast commented out (not deleted); case
  studies A2, S1, C1 (CO1); experiments.yaml pairs = 36 refinement pairs (old list commented);
  figures/tables from DS_ORDER = adult, acsincome, tax, compas, law, meps.  Numbers from
  scripts/chapter_numbers.py.  B1 at eps = 1 is e2_b1 rows with value == 1 (the file has one row per eps).
* User decisions: COMPAS with our pairs, MEPS (healthcare), Law Students yes, Erica's Adult pairs no,
  keep Tax.  Contrast (IPUMS) and CQA (Tax-dirty, Hospital) pairs leave the experiments.
* Prior-work pairs checked (Erica repos JinyangLi01/query_refinement, alons9911/Query_refinement;
  Rodeo): COMPAS |Q1| ~100, Healthcare N = 887 (|Q1| 42-178), Erica's Adult 295-1,379 -- too small
  under DP.  Loaders: compas (ProPublica, PII dropped), law (Rodeo; sex 2 = male), meps (HC-181,
  both 2015 panels, 35,427; meps.ahrq.gov allowed in the environment).
* 15 new pairs approved: CO1-CO5 (COMPAS), L1-L5 (Law), M1-M5 (MEPS) in configs/pairs.yaml, from
  scripts/search_refinement_pairs.py (selection by data criteria only; view-stage accuracy reported,
  not used to select).
* Quality on the new pairs: run with --out results_new, appended by scripts/append_pairs.py (e2, e3,
  e6, e8 done; e7a/e7g running locally); rescore_bruteforce.py now merges per pair.
* Runtime: 6 cloud shards new-1..6 (tag pqde-new15), `scripts/shards_status.sh new`:
  new-1 session_01U646mZVd7ZErMCHn9UWHWn, new-2 session_01U646mcHVCxjAemRBgYmV4k,
  new-3 session_01U646mYyVPmimbNYMgLTJ9k, new-4 session_01U646mcocfvcRXhaE2z57iq,
  new-5 session_01U646ma1dAXokDXoQexKbF1, new-6 session_01U646mckYdZacLKVbLrkuNF.
  When done: fetch the branches into results_shards/, `python scripts/merge_shards.py --shard
  'eqbins-*' --shard 'all44-*' --shard 'new-*' e4 e5 e7t e7t7`, redraw.
* Then: experiments.yaml pairs/datasets to the 36 refinement pairs, case studies (A2, S1 + COMPAS),
  chapter update (remove IPUMS-CPS, Tax-dirty, Hospital; new headline numbers).

## 2026-11-26: third reviewer pass of Section 5 (user: apply all 34 comments; N-bar option A)
* experiments.tex rewritten per the review: numbers given their measure, aggregation and source;
  setup moved out of the case studies; 5.3 reordered (comparison, view stage, where the noise
  costs, tau, split, eps, gamma, lambda, |Attrs|, runtime); Runtime stays a paragraph (user).
* N-bar = |D| (option A): the Default setting says the dataset size is treated as public, as under
  the bounded relation of Sec. 3 (subsec:ideal-sensitivity).
* Figures: runtime_grid and attrs show OptPrivExpl instead of the undefined B3.
* scripts/review_numbers.py (resumable) writes results/rescored/review_numbers.csv and
  coverage_tau.csv: coverage of BF and per tau, best HD_gamma of the exact top-tau, output sizes,
  median bin support.  All 44 pairs done; every number of the chapter is filled from them.
  Table 4 per-tau rows average all 44 pairs with tau >= |P| read as all views (ApproxRatio at
  tau = 1000: 0.87, was 0.86 over the pairs with |P| > 1000).  BF's own coverage is 0.15.
* The old "median bin 17 tuples" on Adult does not reproduce (median bin support of the explained
  candidates: Adult 456, ACSIncome ~4,000, Hospital 23); the gamma paragraph no longer ties the
  gain to bin size, since IPUMS (18k) gains less than ACSIncome.

## 2026-11-25 ~02:10 UTC: running time on all 44 pairs merged
Shards all44-* (8 cloud workers, the 22 pairs not timed before) done; results/e4, results/e5 and
results/e7/raw/runtime*.csv now cover all 44 pairs (`merge_shards.py --shard 'eqbins-*' --shard
'all44-*' e4 e5 e7t e7t7`).  The pairs of a dataset ran on up to three machines; the methods of a
pair always on one.  Quality is scored against the one-stage brute force at the default gamma
(results/rescored, scripts/rescore_bruteforce.py).  The abstract is sections/abstract.tex.

## 2026-11-15 ~12:45 UTC: running time on the equal-width bins merged
All eqbins shards done (E4, E7 at k = 5 and 7, E5) and merged into results/e4, results/e5 and
results/e7/raw/runtime*.csv (`python scripts/merge_shards.py --shard 'eqbins-*' e4 e5 e7t e7t7`);
runtime_grid and attrs redrawn (attrs now with B2 at k = 7), Performance numbers updated, the \alon
note on the bins removed.  The whole chapter is now on the equal-width bins.  The old-bin k = 7 run
(results_shards branches ...-e7k7-<name>) finished too and is superseded; it is not merged.
Worker sessions can be archived once the user agrees.

## 2026-11-15 ~03:40 UTC: reviewer pass of Section 5 (user: "review as a reviewer and fix")
* Done and pushed: reviewer comments applied to paper/sections/experiments.tex, number audit applied,
  appendix table paper/sections/attributes_table.tex (generated by `python -m pqde.paper_tables`),
  case-study and quality figures redrawn (`pqde.paper_figures.fig_cases`, `fig_quality`).
* E8 (src/pqde/experiments/e8_review.py, results/e8/, view profile results/e8/view_profile.csv):
  fixed-gamma eps sweep, lambda, competitors (Table tab:competitors, user: report with a coverage
  axis) and tau are in the chapter; no "Sign acc." column (user: no).  Earlier open point, resolved:
  competitors (SingleStage beats the algorithm on F0 on all 44 pairs: 1.67 vs 0.85 of the filtered
  optimum, 1.57 vs 0.89 smoothed, but its views cover 0.52x as much of the outputs; OptAll is an
  artifact of gamma_eval = 0) and the tau results; and whether to add a "Sign acc." column to Table 4.
  Placeholder: \alon{[E8 running] ...} in the References paragraph.
* Reminders for the user: N-bar = |D| is outside Prop. 4.2 as stated (removal of a tuple from D not
  covered); Section 4 still says |P| = 1,052 and points to 5.4 for tau.
* Cloud containers restart every 1-2 h: E4/E7t/E7t7 now resume from their raw CSVs (commit 1bd33e9);
  all runtime workers were told to fetch the three files and relaunch without cleaning.
  E5 (equal bins) moved to a cloud worker: session_01U646maMtoiiod49oi5NoQc, branch ...-eqbins-e5,
  dir results_shards/eqbins-e5-local.  E8 worker: session_01U646maNhv1WNoWUndLCbvN (done).

## Running now: equal-width bins (approved 2026-11-15)
Bins in configs/datasets.yaml (`bins:`); |P| Adult 1144, ACSIncome 1084, Tax 2106, Tax-dirty 2300,
Hospital 502, IPUMS 1124.  User: draft the chapter now with case studies + accuracy on the new bins
and the running time measured on the old (quantile) bins, stated in the text; update later.
* Local: `rebin-local` (E1, cases, E2, E3, E6, E7a, E7g) -> merge with
  `python scripts/merge_shards.py --shard rebin-local e1 e2 e3 e6 cases e7a e7g`; then
  `scripts/after_rebin_e5.sh` runs `eqbins-e5-local` (E5); then rerun scripts/attr_precision_chance.py.
* Cloud (tag pqde-eqbins), check with `scripts/shards_status.sh eqbins-e4` / `eqbins-e7`:
  eqbins-e4-acs session_01U646maVpJNHCSbrJKT49E7, -ipums session_01U646mc7pXtzv8j1tgVp3CB,
  -tax session_01U646mbfQHgeiV8dBqKrPut, -taxdirty session_01U646mbmZdLL5USTwe5VmrD,
  -adult session_01U646mbrneQVwXJbDu9Zyep, -hospital session_01U646mZukSAysns7c5R6c15;
  eqbins-e7-acs session_01U646maZtsX9u6FYPhN7bVS, -ipums session_01U646mZMQWz99MJN9mR7Dx6,
  -tax session_01U646md5nGZtisbQepW6zZ8, -taxdirty session_01U646mbrTZQTJNa9MvuNtTa,
  -adult session_01U646mZehZsGGhrhEdvcFmJ, -hospital session_01U646maTaci4DvpodofDRej.
* The old-bin k=7 run (e7k7-*) keeps running (user: do not stop it).
* When all done: merge running time from the eqbins shards (`--shard 'eqbins-*'`), redraw, update
  the chapter so everything is on the new bins.

## Running now: E7 at k = 7 (started 2026-11-15 ~01:05 IST)
Running time against |Attrs| at k = 7 (tau = 21) on all 22 runtime pairs, same rules (10 runs,
30-min limit, 3 runs on timeout), to show B2 crossing the limit (expected at 11 attributes on Adult
and ACSIncome).  6 cloud sessions, branch `...-e7k7-<name>`, dir `results_shards/e7k7-<name>`,
check with `scripts/shards_status.sh e7k7`:
acs session_01U646magbT82u5c5AmUY89f (~11 h), ipums session_01U646mbTRhyP3Ax7ttttXVi,
tax session_01U646mbUyEcKxcAQFxmHpRM, taxdirty session_01U646mbScqieXtGXLWG7STj,
adult session_01U646mabfHFHHxRNd8HHb5M (~10 h), hospital session_01U646magz2ErFugt8fjmtMU.
When done: fetch the 6 branches into results_shards/, `python scripts/merge_shards.py e7t7`
(-> results/e7/raw/runtime_k7.csv), add k = 7 to the attrs figure, update the paragraph on
exhaustive search in the chapter, compile, commit; ask the user before archiving the sessions.

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
