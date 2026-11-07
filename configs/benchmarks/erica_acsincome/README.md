# Erica's ACSIncome benchmark

Copied verbatim from the artifact repository of J. Li, Y. Moskovitch,
J. Stoyanovich, H. V. Jagadish, "Query Refinement for Diversity Constraint
Satisfaction", PVLDB 17(2), 2023 (github.com/JinyangLi01/query_refinement,
`Experiment/ACSIncome/whole_data/`):

* `q{1..4}/q{i}.json` — the queries Q1^A–Q4^A of the paper's Figure 2;
* `q{i}/constraint_{relax1,contract1,refine1}.json` — the cardinality constraints
  (Figure 3: C1–C3 for Q1, Q2; C4–C6 for Q3; C7–C9 for Q4), with bounds at 105%
  (relaxation) / 95% (contraction) of the group counts in the query's output;
* `results/result_q{i}{c}.csv` — the minimal refinements Erica's PVL search
  returned for each (query, constraint), as stored by the authors.

The data is `InputData/ACSIncome/ACSIncome_state_number.arff` of the same
repository (1,664,500 rows), with Erica's preprocessing (SEX as M/F, age and
income buckets, occupation groups).  `pqde.benchmarks.erica` decodes the stored
refinement vectors without running Erica's code and validates each one on the
data (it must satisfy its constraints; the original query must not).
