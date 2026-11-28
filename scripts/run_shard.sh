#!/bin/sh
# Run one shard of the experiments: scripts/shards/<name>.jobs, one job per line
#   <experiment> <pairs, comma-separated, or - for the experiment's own pair list> [<E4 sweep>]
# Jobs run as separate processes, at most P at a time (default 4); a single timed
# run is never parallelised.  Outputs: results_shards/<name>/<experiment>-<pairs>[-<sweep>]/,
# logs in results_shards/<name>/logs/, a marker per finished job in .../done/,
# and results_shards/<name>/DONE when the shard is finished.  Re-running the
# script skips finished jobs.  CONFIG=<experiments yaml> runs every job with that config.
set -u
NAME=$1
P=${2:-4}
OUT=results_shards/$NAME
mkdir -p "$OUT/logs" "$OUT/done"
PY=${PY:-python3}
CONFIG=${CONFIG:-}
export OUT PY CONFIG
grep -v '^\s*#' "scripts/shards/$NAME.jobs" | grep -v '^\s*$' | xargs -P "$P" -L 1 sh -c '
  exp=$0; pairs=$1; sweep=${2:-}; tag="$exp-$(echo "$pairs" | tr , _)"
  [ "$pairs" = "-" ] && tag="$exp-all"
  [ -n "$sweep" ] && tag="$tag-$sweep"
  [ -f "$OUT/done/$tag" ] && exit 0
  set --
  [ -n "$CONFIG" ] && set -- --config "$CONFIG"
  [ -n "$sweep" ] && set -- "$@" --sweeps "$sweep"
  if [ "$pairs" = "-" ]; then
    $PY -m pqde run "$exp" "$@" --out "$OUT/$tag" > "$OUT/logs/$tag.txt" 2>&1
  else
    $PY -m pqde run "$exp" --pairs $(echo "$pairs" | tr , " ") "$@" --out "$OUT/$tag" > "$OUT/logs/$tag.txt" 2>&1
  fi && date > "$OUT/done/$tag"
'
date > "$OUT/DONE"
