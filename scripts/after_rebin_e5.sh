#!/bin/sh
# Runs the equal-bins E5 shard on this machine once the case-study/accuracy shard has finished,
# so that its timings are not disturbed by the accuracy runs.
cd "$(dirname "$0")/.."
until [ -f results_shards/rebin-local/DONE ]; do sleep 30; done
scripts/run_shard.sh eqbins-e5-local 4
