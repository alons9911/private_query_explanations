# private_query_explanations

Experiment stack for the paper **"Private Query Difference Explanations"**
(`Private_Query_Refinement.pdf`).  The repository re-implements the
algorithms of the paper and runs every experiment of Section 5 on the four
datasets, producing the paper's tables and figures plus the measurements the
draft still lists as TODO.

```
pip install -e ".[test]"      # numpy, pandas, matplotlib, pyyaml (+ pytest)
make data                     # download Adult, Tax, Hospital (+ StackOverflow if reachable)
make test                     # unit tests, incl. empirical checks of the sensitivity bounds
make all                      # E1-E6 + case studies + results/REPORT.md (about 2 hours, mostly E4)
```

`results/` is committed, so the numbers and figures of the last full run can be
read without running anything: start at [`results/REPORT.md`](results/REPORT.md).

**Case studies.** [`docs/CASE_STUDIES.md`](docs/CASE_STUDIES.md) presents six
refinement pairs (R1–R6) and four CQA pairs (C1–C4) chosen by a pair search
for the paper's motivation, with the explanations the private algorithm
releases on them (`pqde run search`, then `pqde run cases`).

## What is implemented

| Paper | Code |
|---|---|
| Predicates, `Q(D) = σ_φ(D)` (§2.1) | `pqde/query.py` — a small SQL-WHERE parser/evaluator |
| Predicate views `P`, `ℓ ≤ 2` (Def. 2.1) | `pqde/views.py` |
| Public bins, 6 quantile bins for numeric attributes (§2.3, §5.1) | `pqde/data/encode.py` |
| `HD_γ` (Def. 3.4, Eq. 1), `Rep_{γR}` (Def. 3.5, Eq. 2–3), `Cov` (Eq. 5), `Use` (Eq. 8), `Div` (Eq. 6), `F_w` (Def. 3.6, Eq. 7) | `pqde/measures.py` |
| One-off statistics cache: view sizes, `Rep`, `Use`, the three histograms of every candidate (§4.2 "Complexity") | `pqde/stats.py` |
| Laplace (Def. 2.14), exponential (Def. 2.15), one-shot top-k (Def. 2.16) | `pqde/mechanisms.py` |
| **Algorithm 1** (budget split, `γR = N`, `τ = min(3k,|P|)` Eq. 11, `γ = 2 ln(τ|Attrs|) k/ε_S` Eq. 12, private view selection with `Δ = 7/(4|D|)`) | `pqde/algorithm.py: explain` |
| **Algorithm 2** (k rounds of `ExpMech` on `HD_γ · λ^Counts[A]` with `Δ = 1/(1+γ)`, `Laplace(2k/ε_H)` paired release; optional difference release `Laplace(k/ε_H)`) | `pqde/algorithm.py: find_top_k_explanations` |
| Baselines B1 (`ε→∞`, constants held), B2 (exhaustive over size-k subsets, top-k per attribute), B3 (exact top-τ + greedy), ApproxRatio with `γ_eval = 0` (§5.1) | `pqde/baselines.py` |
| Query refinement under output constraints (Def. 2.4–2.5), ERICA-style search used to fill the pairs the paper leaves TBD | `pqde/refinement.py` |
| Consistent query answering via the conflict hypergraph for FDs (Def. 2.6–2.7) and the H1–H3 selection rule (§5.1) | `pqde/cqa.py` |
| The twelve query pairs (Table 2) | `configs/pairs.yaml`, `pqde/pairs.py` |

### Experiments (Section 5)

| ID | Question | Driver | Main outputs |
|---|---|---|---|
| E1 | One release per pair (§5.2): what the queries say, which views the first stage keeps, what the released histograms say | `experiments/e1_case_studies.py` | `results/e1/<pair>/report.json`, `explanations.png` (Fig. 4/5), `release_leaves.png` (Fig. 3) |
| E2 | Accuracy vs. ε against B1–B3: ApproxRatio, Jaccard, precision@k, attribute precision@k, view Jaccard, release error (§5.3.1) | `experiments/e2_accuracy.py` | `results/e2/table3_approx_ratio.md`, `table_set_metrics.md`, `eps_<metric>_by_{dataset,pair}.png` |
| E3 | What drives accuracy: margins, bins vs γ, the view stage alone, the budget split | `experiments/e3_drivers.py` | `results/e3/*.md`, `view_stage_<dataset>.png` |
| E4 | End-to-end running time of PRIV_EXPL, OPT_PRIV_EXPL, B1, B2, B3 vs. k, N, ε, \|P\|, τ, γ, one row of panels per dataset, with a time limit per run (§5.3.2) | `experiments/e4_scalability.py` | `results/e4/runtime_<dataset>.png`, `runtime_all_datasets.png` |
| E5 | End-to-end cost per pair at the defaults, B2 growth, statistics routes (original vs O1 vs O1+O3), identity of OPT_PRIV_EXPL and PRIV_EXPL | `experiments/e5_runtime.py` | `results/e5/default_point_per_pair.md`, `routes.md`, `identity.md`, `fig8*.png` |
| E6 | Accuracy vs. the smoothing constant γ (multiples of Eq. (12), 0 = unsmoothed) | `experiments/e6_gamma.py` | `results/e6/ratio_B2_by_gamma.md`, `gamma_<metric>_by_{dataset,pair}.png` |
| search | Which pairs best show the motivation: hidden drift, drift inside the constrained group, unexplained aggregate change, CQA drop/unevenness, DP visibility | `experiments/pair_search.py`, `search.py`, `configs/pair_search.yaml` | `results/pair_search/*.csv` |
| cases | Case studies R1–R6, C1–C4: release, stability over 40 runs, ApproxRatio | `experiments/case_studies.py` | `results/case_studies/`, `docs/CASE_STUDIES.md` |

## Datasets

| Dataset | Source | N | Notes |
|---|---|---|---|
| Adult | UCI census extract (train + test); falls back to a GitHub mirror when UCI is unreachable | 48,842 | |
| Tax | Tax benchmark of the data-cleaning literature (BigDaMa/raha copy, clean version) | 200,000 | the paper quotes N = 500,000; set `target_rows: 500000` in `configs/datasets.yaml` to up-sample (E4 does so for its N sweep) |
| StackOverflow | Developer Survey 2024 (`survey_results_public.csv`) | ≈65k | if the official file cannot be downloaded, a **synthetic** generator with the same normalised schema is used and every output is flagged `synthetic` — put the CSV in `data/raw/stackoverflow/` to use the real survey |
| Tax (dirty) | the same 200k tuples with injected errors (BigDaMa/raha `dirty.csv`), formatting differences normalised; FDs `Zip→City`, `Zip→State`, `(State, MaritalStatus)→Single/MarriedExemp`, `(State, HasChild)→ChildExemp`, `(State, Salary)→Rate` | 200,000 | used for the CQA case studies C1–C3 |
| Hospital | HoloClean hospital benchmark (dirty), FDs `HospitalName→ZipCode`, `HospitalName→PhoneNumber`, `ZipCode→City` | 1,000 | categorical domains declared by the clean file; typos fall into `Other` |

The public schema of every dataset (explanation attributes, reference
attributes, view attributes, bins) lives in `configs/datasets.yaml`.

## Command line

```
pqde data                         # fetch + describe the datasets
pqde pairs A2 T1                  # resolve pairs (sizes, constraint shares, how Q' / Q_Sigma was made)
pqde explain A2 --epsilon 1 --seed 0      # one private run, printed
pqde run e2 --pairs A1 A2 T1 --trials 40  # one experiment, any subset of pairs
pqde run e1 e2 e3 e4 e5 e6 --quick --out results/_scratch   # smoke run
pqde plot e2 e4                   # rebuild figures from the saved raw data only (no re-run)
pqde all                          # everything + results/REPORT.md
```

Library use:

```python
from pqde.pairs import resolve_pair
from pqde import explain, Params

pair = resolve_pair("A2")                  # or build masks yourself and call pqde.build_cache
cache = pair.cache()                       # exact statistics on the trusted server
res = explain(cache, Params(k=5, epsilon=1.0), rng=0)
for e in res.explanations:                 # only view, attribute and noisy histograms are released
    print(e.view_label, e.attr, e.noisy_h1.round(), e.noisy_h2.round())
```

## Parameters (Section 5.1 defaults, `configs/experiments.yaml`)

Every experiment starts from one `defaults` block and changes only the
parameter it studies: the whole dataset, every public view, `k = 5`,
`λ = 0.5`, `ε = 1` split equally between view selection, explanation selection
and histogram release.  The derived constants follow the algorithm's rules
(also when k, ε or τ is the varied parameter): `τ = min(3k, |P|)`,
`γ = 2 ln(τ|Attrs|) k / ε_S`, `γR = N`.  40 private runs per accuracy point,
metric `F_λ` with `γ_eval = 0`, time limit 60 s per timed run.  All randomness
is seeded (`defaults.seed`).

## Raw data and figures

Each experiment writes one row per run to `results/<exp>/raw/*.csv` (for the
accuracy experiments including the released set and the retained views), and
builds its figures only from those files: `pqde plot <exp>` re-draws them
without re-running anything.

## Methods compared and the optimisations

| method | what it is |
|---|---|
| `PRIV_EXPL` | Algorithm 1, statistics by the route of Section 4.2 (one pass per view; histograms only for the views scored) |
| `OPT_PRIV_EXPL` | the same algorithm with O1 (views constraining the same attributes computed together in one grouped pass) and O3 (the three histograms of a scored view in one combined pass) |
| `B1`, `B2`, `B3` | the baselines of Section 5.1, on the original route |

O1 and O3 compute exactly the same numbers, so the mechanisms receive
identical inputs and the release has the same distribution (the privacy
analysis is unchanged); `tests/test_stats_modes.py` and E5 check that both
methods release identical outputs for the same randomness.  Every experiment
other than the running-time comparison uses the original route.  The closed
form of Rep at `γR = N` (Eq. (10)) is not used as an optimisation: at
`γR = N`, Rep depends only on the view size (see the reproduction notes).

## Reproduction notes

See [`docs/REPRODUCTION_NOTES.md`](docs/REPRODUCTION_NOTES.md) for the
places where this stack had to make a choice the paper leaves open (view
attributes, A3/T2/T3, H2/H3, the margin definition), where its numbers differ
from the draft, and which of the draft's TODOs each output answers.

## Layout

```
configs/      datasets.yaml (public schema) · pairs.yaml (Table 2) · experiments.yaml (grids)
src/pqde/     the library (see table above) + experiments/ + cli.py + report.py
tests/        unit tests (measures, cache, mechanisms, algorithm, sensitivity bounds, CQA, refinement, paper numbers)
results/      outputs of the last full run (CSV / JSON / PNG / PDF) and REPORT.md
data/raw/     downloaded datasets (git-ignored)
```
