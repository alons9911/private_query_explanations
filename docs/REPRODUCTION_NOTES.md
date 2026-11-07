# Reproduction notes

This file records (1) the choices the stack had to make where the paper is
silent, (2) how the numbers of the last full run (`results/REPORT.md`) compare
with the draft, and (3) which output answers which TODO in the draft.  All
numbers below come from `make all` with the committed configs.

## 1. Choices not fixed by the paper

| Topic | Paper | Here | Where |
|---|---|---|---|
| View attributes, Adult | not listed; `|P| = 1,052` | `workclass, education, occupation, race, gender, hoursPerWeek`, `ℓ = 2` → `|P| = 1,048` (the closest attribute set to 1,052 that contains the attributes of the A2 views quoted in §5.2) | `configs/datasets.yaml` |
| Explanation / reference attributes | `|Attrs| = 10` on Adult | Adult: `age, workclass, education, maritalStatus, occupation, relationship, race, gender, hoursPerWeek, income`; `A_R = Attrs` | idem |
| Bins | six quantile bins for numeric attributes, from public metadata | quantile cut points computed once on the full benchmark file and stored with the dataset (heavy atoms merge bins, e.g. `hoursPerWeek` has 4 bins) | `pqde/data/encode.py` |
| Categorical domains | `Dom(A)` declared by the schema | values of the benchmark file; for Hospital the values of the clean ground truth, typo values go to an `Other` bin | idem, `sources.load_hospital` |
| Tax size | `N = 500,000` | the public benchmark file has 200,000 rows; `target_rows: 500000` up-samples (E4 does so for its N sweep) | `configs/datasets.yaml` |
| StackOverflow | developer survey | the official download host is unreachable from the build machine, so a **synthetic** generator with the same normalised schema was used; every S1–S3 output is flagged `synthetic`. The real survey loader (`_so_from_survey`) is used automatically once `survey_results_public.csv` is in `data/raw/stackoverflow/` | `pqde/data/sources.py` |
| A3, T2, T3 | TBD | chosen here, `Q'` from the ERICA-style search of `pqde/refinement.py` (predicate distance: `|c−c'|/range` for numeric, Jaccard for sets, 1 for a dropped condition; ties by output Jaccard distance) | `configs/pairs.yaml` |
| H2, H3 | rule of §5.1 | implemented literally: single-predicate selections whose `Q_Σ` drops 10–90 % of `Q`, keeping the one whose dropped tuples are most unevenly spread (max TVD over the other attributes) | `pqde/cqa.py: choose_cqa_selection` |
| H1 | `HospitalType = 'Acute Care Hospitals'` | kept as stated although its `Q_Σ` drops 90.4 % (968 → 93), just outside the 10–90 % window of the rule | — |
| "Margin" (§5.3.1) | not defined precisely | `margins.csv` reports the gap between the two best round-1 candidates (smoothed and unsmoothed, absolute and relative) and the gap in units of the exponential-mechanism resolution `2Δ ln|C|/ε_i` | `experiments/e3_drivers.py` |

## 2. Agreement with the draft

Matches (exact or within rounding):

* A1 constraint share 4.7 % → 26.9 %; A2 19.5 % → 30.6 %, `|Q| = 3,055`, `|Q'| = 2,453` (Table 2, §5.2.1).
* View `education = 'Masters'` on A2: coverage 0.068, representativeness 0.53 (§4.1, §5.2.1).
* `τ = 15`, `γ ≈ 150` (Eq. 11–12); release noise s.d. 60 per bin for the difference at `2k/ε_H = 30` (Fig. 3).
* Adult: median non-empty bin holds 20 tuples; `γ` at 0.5 % / 5 % of `N` exceeds 84.8 % / 98.2 % of the bins (draft: 84 % / 98 %).
* B2 (exhaustive) coincides with B3 (greedy) to the last digit on **all twelve** pairs (Prop. 7.1).
* Budget split on A2: `(0.10, 0.55, 0.35)` drops ApproxRatio vs B2 from 0.875 to 0.606 (draft: 0.89 → 0.57); starving the view stage is the one bad choice, as the draft says. No split beats the equal split on every pair (`(0.20, 0.40, 0.40)` is slightly better on A1 and A2 and equal on T1).
* Running time is linear in `k` and `τ`, flat in `ε` and `γ`, and the per-invocation cost is flat in `N` (Fig. 7); B2 grows combinatorially with the candidate pool (Fig. 8).

Differences worth knowing before quoting numbers:

* **A2 view rank and accuracy.** With the view attributes above, `education = 'Masters'` ranks **6th** by `Use` (draft: 13th), so the first stage keeps it easily and A2 reaches ApproxRatio 0.916 vs B2 at `ε = 1` (draft Table 3: 0.612). The A2 view stage remains the hardest of all pairs (`use_gap_over_scale = 0.31`, retained/top-15 overlap 0.81 at `ε_P = 1/3`), so the qualitative claim "A2 is hard because its candidates are close" holds; the magnitude depends on `P`.
* **T1 on the public tax file.** On the 200 k benchmark file `HasChild` is independent of `MaritalStatus`, so `Q` already has 49.9 % `HasChild = 'Y'` and `Q'` 49.8 % (draft: 3.5 % → 50.1 %). The constraint is therefore not violated by `Q` on this file, and the "single parents" story of §5.2.2 cannot be reproduced on it; the draft's tax data must come from a different generator run. T1 is kept as a pair (the framework does not need the constraint) and T2 is a tax pair where the constraint does bind (0 % → 49.8 %).
* **Tax bins.** Median non-empty bin 898 tuples at `N = 200 k` (draft: 3,897 at 500 k); share of bins below `γ` at 0.5 % / 5 % of `N`: 65 % / 95 % (draft: 30 % / 94 %).
* **Runtime.** The cache build here is one grouped `bincount` per (attribute set, attribute, population) — the "one pass + per-tuple matching" route the draft lists as a possible optimisation — so it takes 0.05 s on Adult and 0.5–0.8 s on Tax instead of the 16.7–23.2 s of Fig. 7. The per-invocation mechanism takes ≈0.5–1 ms (draft 8.1 ms).
* **Hospital.** 902 of the 1,000 tuples lie on a conflict hyperedge (a single typo in a hospital's zip, phone or city puts all of that hospital's rows in conflict), so every `Q_Σ` is small. At `ε = 1` the view stage is close to random (`N = 1,000` makes `Δ_Use = 7/4000`): ApproxRatio vs B2 is 0.83 / 0.85 / 0.18 for H1 / H2 / H3, and 0.93 / 0.98 / 0.88 at `ε = 5`.

**Optimisations (OPT_PRIV_EXPL).** O1 computes every view of one attribute set
with one grouped pass (21 passes instead of 1,048 on Adult); O3 materialises the
histograms of a scored view with one combined pass over a 4-way population code
(Q1 only / Q2 only / both / neither).  Both are pure reorganisations of exact
server-side computation: identical numbers, identical releases for identical
randomness (checked in tests and in E5), unchanged privacy analysis.  All other
experiments use the original route.

An observation the draft states (Eq. 10) but may want to stress: at `γR = N`
every summand of Eq. (2) is non-negative, so `Rep_N(p, D) = (2m + N) / (2(m + N))`
for **every** view, independent of the attribute distributions (unit test
`test_rep_collapses_at_gamma_R_equals_N`). With the default `γR`, `Use` is thus a
function of the view size and the two output counts only.  Two Adult views of
almost the same size (1,580 and 1,585 tuples) get the same Rep (0.5157) although
their distributional similarity to D (1 − TVD) is 0.931 and 0.713, so the
"typical region" guard of §3.2 does not act at γR = N.

## 3. Draft TODOs and where the answer is

| TODO in the draft | Output |
|---|---|
| A2: full list of retained views; do they match the exact top-15? | `results/e1/A2/report.json → view_stage.retained` (with exact ranks) and `overlap_with_exact_top_tau`; ranking of all views in `views_by_use.csv` |
| T1: how many of the τ retained views are conditioned on `MaritalStatus='S'`, and its rank by `Use` | `results/e1/T1/report.json → view_stage.retained_atom_counts` (none in the last run) and `query_attribute_views` (`MaritalStatus='S'` ranks 25th) |
| Verify the case-study sentences against exact histograms | every explanation in `report.json` carries `exact_h1/exact_h2`, exact shares and totals next to the noisy values |
| A1/A2/T1 figures with all k panels | `results/e1/<pair>/explanations.png` always shows all k released panels |
| A3, T2, T3: pick pairs and run ERICA | `configs/pairs.yaml` + `refinement_search` block in `pqde pairs A3 T2 T3` |
| H1–H3: run, report `|Q|`, `|Q_Σ|`, views, histograms | `results/e1/H{1,2,3}/report.json`, `explanations.png` |
| StackOverflow `N`, `|Attrs|`, survey year | 2024 schema, `|Attrs| = 10`; the last run used the synthetic stand-in (`N = 65,437`) — rerun after placing the survey CSV |
| Re-run quality and runtime with `τ = min(3k,|P|)` and `γ` by Eq. (12) | defaults of `configs/experiments.yaml`; `results/e2`, `results/e4`, `results/e5` |
| View stage in isolation (overlap with the exact top-τ, lowest `Use` retained) | `results/e3/view_stage.csv`, `view_stage_overlap.png` |
| Re-check the `γ` paragraph | `results/e3/bin_stats.csv`, `gamma_sweep.csv` (the Eq. (12) value is at or near the peak of ApproxRatio on A1, A2; T1 is flat above it) |
| Runtime of the CQA and StackOverflow pairs; end-to-end time incl. cache build | `results/e5/runtime_per_pair.csv` (`cache_build_s`, `private_ms`, `end_to_end_s`) |
| Utility guarantees (Alon TODO in §4.2) | not addressed (theory) |

## Contrast pairs (IPUMS-CPS, DPXPlain's questions)

A contrast pair compares two disjoint sub-populations, Q1 = σ_φ1(D) and
Q2 = σ_φ2(D) with φ1 ∧ φ2 unsatisfiable, neither derived from the other (the
setting of contrast-set mining, emerging patterns, Sarawagi's DIFF operator,
DIFF/MacroBase, Roy & Suciu, and DPXPlain).  The pairs I1–I17 are the group
comparisons of DPXPlain's experiments on its IPUMS-CPS extract (I1 = its default
question SEX Male vs Female; I2–I17 its control questions), with DPXPlain's
aggregate AVG(INCTOT).

Every view on an attribute mentioned by φ1 or φ2 is one-sided by construction
(one output is empty in it), and that attribute's own histogram only restates
the two groups; both are therefore excluded for contrast pairs
(`exclude_group_attrs`, default for `kind: contrast`): the group attribute is
neither a view attribute nor an explanation attribute (it stays a reference
attribute of Rep).

Open design point: HD_γ compares counts, so when the two groups differ much in
size (e.g. I8, White 899k vs Black 136k) the score of a view grows with the size
gap in every bin, not only with differences in distribution.  For contrasts a
size-normalised variant may be the more natural object; refinement and CQA pairs
are unaffected (their outputs overlap and the count difference is the change).

## Tax CQA constraints (option b)

The CQA pairs on the dirty Tax file use the published Tax rules of Ni et al.
(PVLDB 17(10), 2024; `configs/benchmarks/ni2024_rules/tax`) **without**
`area_code -> state`: under subset-repair semantics that rule, together with the
file's 600 state typos, puts 82% of the tuples in conflict (every area-code group
containing one typo), which empties the consistent answers; the rules were
written for cell repair.  With the remaining seven rules 3.9% of the tuples are
in conflict (Alaska 52%, Alabama 29%, Rhode Island 13%, every other state
≤ 11%).  The pairs C1–C3 were re-selected under these rules with US Census
division predicates and the paper's rule (Q_Σ drops 10–90% of Q, unevenly),
plus a DP visibility check.  The earlier C1–C3 (state sets losing AR / NJ
entirely) relied on our own FD choice and are superseded.
