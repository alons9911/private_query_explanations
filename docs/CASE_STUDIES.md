# Case studies: query pairs that show why difference explanations are needed

This document covers the six refinement pairs (R1–R6) and four CQA pairs (C1–C4) chosen by the pair search, and what the private algorithm releases on them.

* Released numbers come from one ε = 1, k = 5 run per pair (`pqde run cases`).
* "Exact" numbers are non-private checks of the text. The algorithm never releases them.
* Data files and figures are in `results/case_studies/` (`CASE_STUDIES_DATA.md`, `<pair>/explanations.png`, `<pair>/case_study.json`).

## 1. How the pairs were chosen

The paper's motivation (§1) is that a refinement or a repair can satisfy its constraint while changing *who* the query is about. The queries, the constraint and the aggregate do not reveal that change. The search (`pqde run search`, `src/pqde/search.py`, `configs/pair_search.yaml`) therefore looks for pairs where the change is large, hidden and visible under DP.

**Candidates searched**

* **Refinement:** 232 Adult and 51 Tax base queries (conjunctions of up to two atoms), each paired with a representation constraint it violates.
  * Constraints: ≥30% women, ≥15% non-White, ≥25% under 30 (Adult); ≥30% parents, ≥30% single, ≥50% taxed, ≥30% low-salary (Tax).
  * `Q'` comes from the ERICA-style search. Categorical edits may only relax or contract a value set; swapping a value for a different one does not count as refining it.
* **CQA:** 57 selections on the dirty Tax benchmark and 15 on Hospital, under the dataset's functional dependencies. The Tax FDs are the benchmark's classic dependencies:
  * `Zip→City`, `Zip→State`
  * `(State, MaritalStatus)→SingleExemp`, `(State, MaritalStatus)→MarriedExemp`
  * `(State, HasChild)→ChildExemp`, `(State, Salary)→Rate`

  All of them hold exactly on the clean file and break on the dirty one.

**Scores**

| score | meaning |
|---|---|
| hidden drift | largest TVD between `Q(D)` and `Q'(D)` on attributes that no predicate, the constraint, or one of their proxies mentions (for CQA: any attribute the predicate does not pin to one value) |
| group drift | the same TVD *inside* the constrained group (e.g. women in `Q` vs women in `Q'`). It is high when the refinement did not bring in "more of the same" members of the group |
| unexplained aggregate change | `AVG_{Q'}(y)` minus what re-weighting `Q`'s groups to the new share would give. This is the part of the change the constraint does not account for |
| drop / unevenness (CQA) | the share of `Q(D)` that the repair semantics removes, and how unevenly the removed tuples are spread (the selection rule of §5.1) |
| DP visibility | over 8–20 private runs at ε = 1: the ApproxRatio against B2, and how often a released explanation lands on a hidden attribute with a bin that clears twice the noise s.d. |

**The paper's pairs, scored the same way**

| pair | hidden drift | income change (AVG) | unexplained |
|---|---|---|---|
| A1 | 0.22 (education) | 0.245 → 0.285 | +0.07 |
| A2 | 0.21 (occupation) | 0.595 → 0.573 | +0.01 |

On A2, the running example of the paper, the high-income rate barely moves although the population is largely replaced: only 874 of the 3,055 tuples of `Q` stay in `Q'`. That makes A2 an example of the aggregate *hiding* a change. The pairs below show larger effects, which the release makes visible.

## 2. Overview

| pair | data | what changes | constraint (or CQA drop) | AVG(y): Q → Q' | hidden drift | ApproxRatio vs B2 at ε = 1 | precision@k vs B2 at ε = 1 |
|---|---|---|---|---|---|---|---|
| R1 | Adult | graduate degrees, ≥50 h → + Some-college, ≥35 h | women 17.6% → 30.6% | income 0.73 → 0.36 | 0.48 occupation | 0.96 | 0.76 |
| R2 | Adult | married professionals → + service workers, never-married | non-White 10.2% → 15.7% | income 0.71 → 0.32 | 0.39 income | 0.94 | 0.17 |
| R3 | Adult | married, 40+ → married / divorced / widowed, 61+ | women 8.9% → 30.2% | income 0.50 → 0.25 | 0.29 hours | 0.93 | 0.41 |
| R4 | Adult | professionals ≥50 h → + service workers, ≥30 h | under-30 14.7% → 25.3% | income 0.58 → 0.31 | 0.37 education | 0.98 | 0.13 |
| R5 | Tax | low income, rate ≤ 2 → rate ≤ 3.2 | taxed 23.7% → 50.0% | rate 0.34 → 1.17 | 0.32 State | 0.97 | 0.61 |
| R6 | Tax | single, no children → single (sanity check) | parents 0% → 49.8% | rate 4.64 → 4.62 | 0.01 | 0.98 | 0.59 |
| C1 | Tax (dirty) | South: AL, AR, GA, MS, TN | Q_Σ drops 37.0% | rate 4.40 → 3.70 | 0.34 State | 0.69 | 0.19 |
| C2 | Tax (dirty) | Northeast: NJ, NY, PA, CT, MA | Q_Σ drops 21.2% | rate 3.89 → 4.37 | 0.20 State | 0.85 | 0.15 |
| C3 | Tax (dirty) | Salary ≥ 70,000 | Q_Σ drops 9.2% | rate 4.66 → 4.74 | 0.07 State | 0.79 | 0.24 |
| C4 | Hospital | acute care hospitals (paper's H1) | Q_Σ drops 90.4% | score 89.5 → 92.6 | 0.77 City | 0.82 | 0.17 |

Both accuracy columns are means over 40 private runs (E2). ApproxRatio compares the *score* of the released set with B2's (the exhaustive optimum over the candidates of the exact top-τ views by Use; it can exceed 1 when the private view stage keeps a view outside that set). precision@k is the share of the k released explanations that B2 also returns. It is much lower than ApproxRatio on pairs with many near-tied candidates, e.g. the State views of C1–C3, where the released set scores close to the optimum without being the same set.

## 3. Refinement pairs

### R1 — "more women among highly educated long-hours workers"

**Scenario.** `education IN (Masters, Doctorate, Prof-school) AND hoursPerWeek ≥ 50` returns 1,554 people, 17.6% of them women. The constraint asks for ≥30%. The refinement adds `Some-college` to the education set and lowers the hours threshold to 35. `Q'` has 12,064 people, 30.6% of them women, and the constraint holds.

**What the analyst sees.** Two shares and two sizes. The high-income rate falls from 73% to 36%. Re-weighting `Q`'s men and women to the new gender mix would only bring it to about 70%, so −0.35 of the drop is not explained by the constraint.

**What the release shows.**
* All five released explanations are about the population that came in.
* The view `education = 'Some-college' AND hoursPerWeek ∈ (32, 40]` is empty in `Q` and holds 5,606 people of `Q'` (exact). Its occupation panel is led by Adm-clerical, Craft-repair, Exec-managerial and Sales; its relationship panel shows Husband, Not-in-family, Own-child and Unmarried.
* The same view × occupation and × relationship are released in **all 40 runs**, and × age in 90% of them.

**Bottom line.** The refinement did not find more women of the same kind.
* Inside the group, women in `Q` are 66% Prof-specialty with 55% high income. Women in `Q'` are 30% Adm-clerical with 17% high income, and 75% of them have only some college (exact).
* `Q'` is a different, mostly non-graduate office and sales population. The release says so without exposing any individual.

### R2 — "more minority representation among married professionals"

**Scenario.** `occupation = 'Prof-specialty' AND maritalStatus = 'Married-civ-spouse'` has 10.2% non-White members; the constraint asks for ≥15%. The refinement adds `Other-service` and `Never-married`. Non-White share reaches 15.7%, and the result grows from 3,182 to 8,561.

**What the analyst sees.** The high-income rate falls from 71% to 32%; −0.39 of that is not explained by the racial composition.

**What the release shows.** In the ε = 1 run, the view `workclass = 'Private' AND occupation = 'Other-service'` (empty in `Q`) is described along five attributes:

| attribute | released (Q′, noisy) |
|---|---|
| age | dominated by 17–24 (≈ 1,436) |
| education | HS-grad and Some-college |
| hours per week | mostly ≤ 40 |
| race | mostly White (≈ 2,353 vs ≈ 487 Black) |

The leading candidates are close (no single explanation in more than 28% of runs). Every run nonetheless describes either the service workers or the professionals along age, education or relationship.

**Bottom line.** The minority members `Q'` adds are mostly not married professionals: 57% of the non-White members of `Q'` are service workers. Their high-income rate is 20%, against 63% in `Q` (exact). The constraint was met by widening the population into a lower-income, younger, less educated one, and most of the people added are White. A fairness constraint can be satisfied in letter while changing the population it was meant to protect.

### R3 — "at least 30% women among married people over 40" (the most striking pair)

**Scenario.** `maritalStatus = 'Married-civ-spouse' AND age ≥ 40` returns 12,932 people, 8.9% of them women (in Adult, most married-civ-spouse records are husbands). The refinement found by the search adds Divorced and Widowed and raises the age threshold to 61. Women now make up 30.2%.

**What the analyst sees.** The share rises from 8.9% to 30.2%. The result shrinks from 12,932 to 3,296, and the high-income rate halves (0.50 → 0.25).

**What the release shows.**
* Four of the five panels are about men: `race = 'White' AND gender = 'Male'` along education, occupation and workclass, and `gender = 'Male'` along age.
* In every one, the `Q'` bars are a fraction of the `Q` bars. For example, White men: HS-grad ≈ 3,203 → 655, Exec-managerial ≈ 1,978 → 282.
* The age panel shows men aged 37–53 present in `Q` and absent from `Q'` (exact 0).
* `gender = 'Male' × education` is the most stable explanation (65% of runs).

**Bottom line.** The constraint was met by removing 9,480 men, not by adding women: the number of women actually *falls*, from 1,152 to 996 (exact). The women who remain are mostly widows (61%), with a 7% high-income rate (50% in `Q`), and `Q'` as a whole works 33 hours a week on average (43 in `Q`). Neither the shares nor the query text say this, and it is the change a fairness audit most needs to see.

### R4 — "at least 25% under 30 among long-hours professionals"

**Scenario.** `occupation = 'Prof-specialty' AND hoursPerWeek ≥ 50` has 14.7% under-30s. The refinement adds `Other-service` and relaxes hours to 30. The under-30 share reaches 25.3%; the result grows from 1,681 to 9,186.

**What the release shows.**
* Two-sided views: `occupation = 'Prof-specialty'` along education, relationship and workclass, and `occupation = 'Prof-specialty' AND race = 'White'` along age and marital status.
* `Q'` has about 3–4× more professionals in every education bin, from the hours relaxation.
* Across runs, the `Other-service` view (along education and marital status) is released in 35% of runs.

**Bottom line.** The young people the refinement adds are mostly not young professionals.
* In `Q`, the under-30s are all professionals, 51% with a Bachelor's degree.
* In `Q'`, 57% of the under-30s are service workers, and only 8% earn >50K (24% in `Q`).
* The effect is real but less sharp than R1–R3, because much of the visible change is simply "more of the same professionals".

### R5 — "at least half of the low-income, low-tax filers should pay some tax"

**Scenario.** `Salary ≤ 30000 AND Rate ≤ 2` has 23.7% taxed filers. The refinement raises the rate threshold to 3.2, which makes exactly 50.0% taxed.

**What the analyst sees.** A threshold moved from 2 to 3.2 and a share went from 24% to 50%.

**What the release shows.**
* Every run (40 of 40) releases `Salary ∈ [5000, 20000] AND Rate ∈ [0, 3.07]` × **State**.
* In the ε = 1 run its bins are states such as KY, AZ, ND and PA, which have hundreds of filers in `Q'` and none in `Q` (e.g. KY: released ≈ 818 in `Q'` vs ≈ 45 in `Q`; exact 811 vs 0).
* The exemption panels show that the added filers carry larger single and child exemptions.

**Bottom line.** `Q'` does not add taxpayers from the states already in `Q`.
* The taxed filers of `Q` come mostly from OH and NJ.
* `Q'` imports 15 new states (AZ, CT, DE, ID, IL, KY, ME, MS, MT, ND, NE, OK, PA, VA, WV) whose low-income rates lie between 2% and 3.2%.
* Inside the constrained group, the State distribution moves by TVD 0.62. A constraint on *who pays tax* became a change of *geography*.

### R6 — sanity check: dropping `HasChild = 'N'`

**Scenario.** `MaritalStatus = 'S' AND HasChild = 'N' AND Salary ≥ 50000`, with the constraint ≥30% parents, is refined by dropping the `HasChild` predicate. Parents go from 0% to 49.8%.

**What the release shows.** State and Salary panels in which `Q'` is about twice `Q` in every bin (e.g. Salary 50–70k: ≈ 10,048 vs ≈ 19,900), and nothing else stands out. The hidden drift is 0.01, and the average rate is unchanged (4.64 → 4.62).

**Bottom line.** In this benchmark, having children is independent of every other attribute. The correct explanation is therefore "the same population, twice as large", and that is what the framework releases. It shows the framework does not invent differences.

## 4. CQA pairs

On the dirty Tax data, 18,192 of 200,000 tuples (9%) lie on a conflict hyperedge, but very unevenly. A few injected errors in a state make the state-level FDs fail for whole (State, MaritalStatus) groups:

| state | in conflict |
|---|---|
| AR, NJ | 100% |
| AL | 80% |
| AK | 75% |
| every other state | ≤ 13% |

Repair semantics therefore silently remove whole states.

### C1 — Southern states

**Scenario.** `State IN ('AL', 'AR', 'GA', 'MS', 'TN')` returns 19,515 filers. The consistent answer keeps 12,290 (−37%), and the average tax rate falls from 4.40 to 3.70.

**What the release shows.** In the State panels of the ε = 1 run, AR has ≈ 2,196 filers in `Q` and none in `Q_Σ`, and AL keeps only part of its filers (e.g. ≈ 465 of ≈ 1,990 men). The Rate panel shows the loss concentrated in the higher-rate bins.

**Bottom line.** The repaired answer is not "the South minus some dirty rows". Arkansas is gone (0 of 4,026 kept) and Alabama keeps 20%, while GA, MS and TN keep ≥ 99% (exact). The removed filers pay 5.6% on average and the remaining ones 3.7%, so the 0.7-point drop in the aggregate is a change of states, not of tax burden.

### C2 — Northeast

**Scenario.** `State IN ('NJ', 'NY', 'PA', 'CT', 'MA')` returns 19,466 filers. The consistent answer keeps 15,342 (−21%), and the average rate rises from 3.89 to 4.37.

**What the release shows.** Three of the five State panels are dominated by one bar: NJ, ≈ 1,900–2,000 filers in `Q` and ≈ 0 in `Q_Σ`. Every other bin's difference is at noise level (≤ about 200, with s.d. 60).

**Bottom line.** New Jersey disappears entirely (0 of 3,980 kept), and every other state keeps ≥ 99%. Because NJ filers have low rates (2.1% on average), removing them *raises* the average. A user comparing 3.89 with 4.37 would read it as a correction of dirty data, when it is the removal of one state.

### C3 — high earners, a query that never mentions geography

**Scenario.** `Salary ≥ 70000` returns 70,104 filers. The consistent answer keeps 63,650 (−9.2%, just below the 10% bound of the paper's H-pair rule). The average rate hardly moves (4.66 → 4.74).

**What the release shows.**
* `Salary ∈ (85000, 100000]` × **State** is released in 70% of runs.
* In the ε = 1 run, its leading bins are AR and NJ (≈ 600 each in `Q`, none in `Q_Σ`), followed by AK and AL (`Q_Σ` keeps a fraction).
* The `SingleExemp ∈ [0, 87]` and `HasChild = 'Y'` views repeat the pattern.

**Bottom line.** This is the clearest CQA case for the paper's motivation. The query has no geographic predicate, and the aggregate changes by less than 2%. Yet the repaired answer contains no high earner from Arkansas or New Jersey, and only 20–27% of those from Alabama and Alaska. Only an explanation of the difference reveals it.

### C4 — the paper's H1 on Hospital (small data)

**Scenario.** `HospitalType = 'acute care hospitals'` returns 968 rows. The consistent answer keeps 93 (−90%): a single typo in a hospital's zip, phone or city puts all of that hospital's rows in conflict. The average quality score rises from 89.5 to 92.6.

**What the release shows.**
* `State = 'al'` × City, CountyName and MeasureCode (each released in 80–88% of runs).
* The ε = 1 noise s.d. (60 per bin difference) is comparable to the counts (tens per bin), so only a few bins clear it (e.g. Marshall county).

**Bottom line.** The exact data has a strong story: 67 hospitals become 18, 71 cities become 13, and the share of district-authority hospitals jumps from 20% to 55% while proprietary ones fall from 21% to 5%. With 1,000 tuples, ε = 1 can only point at the attributes involved, not at the individual bins. This pair is useful in the paper as the small-data limitation. C1–C3 make the CQA point with data large enough for the release to be read bin by bin.

## 5. Caveats

* The Tax data is the public benchmark file. In it, demographic attributes are nearly independent of one another (which is why R6 is clean). Tax and rates depend on state, salary and filing status, which is why R5 and C1–C3 are about geography.
* One-sided views (one output empty) dominate several releases (R1, R2, R5). They describe the population that entered or left, as in Example 3.2(b) of the paper. A view where both outputs are present needs a constraint that keeps part of the original population (R3, R4, R6).
* The numbers quoted as "exact" are for checking the text. A paper should quote the released values, or the exact ones next to them, as the draft's own TODOs note.
