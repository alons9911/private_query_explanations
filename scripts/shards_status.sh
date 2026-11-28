#!/bin/sh
# Prints the state of each cloud shard (DONE marker on its branch); exit 0 when all six are done.
# Usage: scripts/shards_status.sh        (E4 shards: branch ...-shard-<name>, dir results_shards/<name>)
#        scripts/shards_status.sh e7     (E7 shards: branch ...-e7-<name>,    dir results_shards/e7-<name>)
#        scripts/shards_status.sh e7k7   (E7 at k=7: branch ...-e7k7-<name>, dir results_shards/e7k7-<name>)
#        scripts/shards_status.sh eqbins-e4 | eqbins-e7   (equal-width bins re-runs)
#        scripts/shards_status.sh all44   (running time on the other 22 pairs: 8 shards all44-<name>)
#        scripts/shards_status.sh new     (running time on the 15 new refinement pairs: 6 shards new-<n>)
cd "$(dirname "$0")/.."
n_done=0
if [ "${1:-}" = "rt" ] || [ "${1:-}" = "pv" ] || [ "${1:-}" = "tt" ]; then   # rt: running-time rerun (plan_runtime_shards.py);
  g=$1                                                  # pv: its preview (plan_preview_shards.py)
  n_all=$(ls scripts/shards/$g-*.jobs | wc -l)
  for f in $(ls scripts/shards/$g-*.jobs | sort -V); do
    dir=$(basename "$f" .jobs); b=claude/git-repo-experiments-f0705v-$dir
    if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$dir/DONE" 2>/dev/null; then
      echo "$dir done"; n_done=$((n_done+1))
    else
      nd=$(git ls-tree --name-only "FETCH_HEAD:results_shards/$dir/done" 2>/dev/null | wc -l)
      echo "$dir running ($nd/$(grep -cv '^#' scripts/shards/$dir.jobs) jobs; $(git log -1 --format=%cd --date=format-local:%H:%M FETCH_HEAD 2>/dev/null) last push)"
    fi
  done
  [ "$n_done" -eq "$n_all" ]; exit $?
fi
if [ "${1:-}" = "fix" ]; then   # running time on the 7 replaced pairs: 3 shards fix-<n>
  for n in 1 2 3; do
    b=claude/git-repo-experiments-f0705v-fix-$n; dir=fix-$n
    if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$dir/DONE" 2>/dev/null; then
      echo "$dir done"; n_done=$((n_done+1))
    else
      echo "$dir running ($(git log -1 --format=%cd --date=format-local:%H:%M FETCH_HEAD 2>/dev/null) last push)"
    fi
  done
  [ "$n_done" -eq 3 ]; exit $?
fi
if [ "${1:-}" = "new" ]; then   # running time on the 15 new refinement pairs: 6 shards new-<n>
  for n in 1 2 3 4 5 6; do
    b=claude/git-repo-experiments-f0705v-new-$n; dir=new-$n
    if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$dir/DONE" 2>/dev/null; then
      echo "$dir done"; n_done=$((n_done+1))
    else
      echo "$dir running ($(git log -1 --format=%cd --date=format-local:%H:%M FETCH_HEAD 2>/dev/null) last push)"
    fi
  done
  [ "$n_done" -eq 6 ]; exit $?
fi
if [ "${1:-}" = "all44" ]; then
  for n in acs-a acs-b acs-c adult-a adult-b ipums-a ipums-b ipums-c; do
    b=claude/git-repo-experiments-f0705v-all44-$n; dir=all44-$n
    if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$dir/DONE" 2>/dev/null; then
      echo "$dir done"; n_done=$((n_done+1))
    else
      echo "$dir running ($(git log -1 --format=%cd --date=format-local:%H:%M FETCH_HEAD 2>/dev/null) last push)"
    fi
  done
  [ "$n_done" -eq 8 ]; exit $?
fi
for n in acs ipums tax taxdirty adult hospital; do
  if [ "${1:-}" = "e7" ]; then b=claude/git-repo-experiments-f0705v-e7-$n; dir=e7-$n
  elif [ "${1:-}" = "e7k7" ]; then b=claude/git-repo-experiments-f0705v-e7k7-$n; dir=e7k7-$n
  elif [ "${1:-}" = "eqbins-e4" ] || [ "${1:-}" = "eqbins-e7" ]; then b=claude/git-repo-experiments-f0705v-$1-$n; dir=$1-$n
  else b=claude/git-repo-experiments-f0705v-shard-$n; dir=$n; fi
  if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$dir/DONE" 2>/dev/null; then
    echo "$dir done"; n_done=$((n_done+1))
  else
    echo "$dir running ($(git log -1 --format=%cd --date=format-local:%H:%M FETCH_HEAD 2>/dev/null) last push)"
  fi
done
[ "$n_done" -eq 6 ]
