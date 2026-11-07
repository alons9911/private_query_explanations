#!/bin/sh
# Prints the state of each cloud shard (DONE marker on its branch); exit 0 when all six are done.
# Usage: scripts/shards_status.sh        (E4 shards: branch ...-shard-<name>, dir results_shards/<name>)
#        scripts/shards_status.sh e7     (E7 shards: branch ...-e7-<name>,    dir results_shards/e7-<name>)
cd "$(dirname "$0")/.."
n_done=0
for n in acs ipums tax taxdirty adult hospital; do
  if [ "${1:-}" = "e7" ]; then b=claude/git-repo-experiments-f0705v-e7-$n; dir=e7-$n
  else b=claude/git-repo-experiments-f0705v-shard-$n; dir=$n; fi
  if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$dir/DONE" 2>/dev/null; then
    echo "$dir done"; n_done=$((n_done+1))
  else
    echo "$dir running ($(git log -1 --format=%cd --date=format-local:%H:%M FETCH_HEAD 2>/dev/null) last push)"
  fi
done
[ "$n_done" -eq 6 ]
