#!/bin/sh
# Redraws the chapter's figures into paper/figures/exp with the settings the paper uses.
# Running time: RT_RESULTS (default results_preview; the full run replaces it), with Healthcare (Erica's
# pairs) as an extra row of the runtime grid. Quality and view stage: results/ (the accuracy runs).
# Usage: scripts/draw_chapter_figures.sh [quality|view_stage|runtime_grid|attrs|cases ...]  (default: all but cases)
cd "$(dirname "$0")/.."
RT_RESULTS=${RT_RESULTS:-results_preview}
figs=${*:-quality view_stage runtime_grid attrs}
for f in $figs; do
  case $f in
    runtime_grid|attrs)
      env PQDE_RESULTS="$RT_RESULTS" \
          PQDE_RT_METHODS=PRIV_EXPL,OPT_PRIV_EXPL,B1,OPT,SINGLE_STAGE,EXH_ALL,EXH_NAIVE \
          PQDE_RT_SWEEPS=k,data_fraction,view_fraction,tau PQDE_RT_SCALE=linear PQDE_RT_EXH_K_ONLY=1 \
          PQDE_RT_SPLIT_K=1 PQDE_K7_METHOD=EXH_ALL PQDE_RT_EXTRA=healthcare_erica \
          PYTHONPATH=src python3 -c "from pqde import paper_figures as F; print(F.fig_$f())" ;;
    *)
      PYTHONPATH=src python3 -c "from pqde import paper_figures as F; print(F.fig_$f())" ;;
  esac
done
