# Status and next steps (handoff note)

Keeps the state of the work outside the chat context.

## Running now
* Detached full run (`setsid nohup` script, independent of the chat session):
  accuracy E1/E2/E6/E3 + case studies (done), E5 (done/finishing), E4 (reduced:
  2 pairs on ACSIncome and IPUMS, one repeat on Tax/Tax dirty; 60 s time limit).
  Logs: `results/logs/run_*.txt`; `results/run_done.txt` appears when everything ends.
* E4/E5 write their raw CSVs after every pair, so a stopped run still leaves usable data
  (`pqde plot e4` / `pqde plot e5` redraw from it).

## When the run ends
1. `pqde plot e1 e2 e3 e4 e5 e6` (if needed) and
   `python -c "from pqde.report import build_report; build_report()"`.
2. Rewrite the C1–C3 sections of `docs/CASE_STUDIES.md` (now Census-division pairs
   under the Ni et al. 2024 Tax rules without area_code→state) from
   `results/case_studies/CASE_STUDIES_DATA.md`; update its overview table from E2.
3. Commit + push results; update PR #2 description (benchmarks: Erica ACSIncome,
   DPXPlain IPUMS, Ni et al. rules; OPT_PRIV_EXPL; timeouts).
4. Summarise for the user: accuracy (ApproxRatio vs precision@k), gamma (Eq. 12
   near-optimal), runtime (B2 timeouts at k >= 7, PRIV ≈ B1 ≈ B3, OPT ≈ 8–11x).

## Decisions already taken by the user
* All experiments on the original route; optimisations only as OPT_PRIV_EXPL (O1 + O3).
* Derived constants (tau, gamma) follow their rules when k, eps or tau vary.
* Contrast pairs = DPXPlain's IPUMS questions, group attributes excluded (views and
  explanation attributes).
* Erica pairs: Q' = Erica's own refinement that best tells the story (`pqde run erica`).
* Tax CQA: Ni et al. 2024 rules without area_code→state (option b).
* Keep pairs not from prior work, but cite the source of every pair (`docs/PAIRS.md`).

## Open points for the paper
* HD compares counts: for contrasts between groups of very different size a
  share-normalised variant may fit better.
* At gamma_R = N, Rep = (2m+N)/(2(m+N)) for every view (depends only on view size).
* ApproxRatio is high where precision@k is low (near-tied candidates); report both.
* B2 is exponential but B3 (greedy) is exact (Prop. 7.1); the efficiency claim is that
  privacy costs ~nothing in time vs B3.
