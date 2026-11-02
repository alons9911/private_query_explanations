#!/bin/sh
# Prints the state of each cloud shard (DONE marker on its branch); exit 0 when all six are done.
cd /home/user/private_query_explanations
n_done=0
for n in acs ipums tax taxdirty adult hospital; do
  b=claude/git-repo-experiments-f0705v-shard-$n
  if git fetch -q origin "$b" 2>/dev/null && git cat-file -e "FETCH_HEAD:results_shards/$n/DONE" 2>/dev/null; then
    echo "$n done"; n_done=$((n_done+1))
  else
    echo "$n running ($(git log -1 --format=%cd --date=format:%H:%M FETCH_HEAD 2>/dev/null) last push)"
  fi
done
[ "$n_done" -eq 6 ]
