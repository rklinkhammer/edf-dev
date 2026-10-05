#!/bin/bash
set -eo pipefail
source /opt/edf-config/targets.sh
root=/home/amd-edf/edf
exec 8>"$root/.edf-sources.lock"
flock -n -s 8 || { echo 'Source sync is active.' >&2; exit 1; }
[[ -d $root/builds/$EDF_TARGET ]] || { echo 'Build this target first.' >&2; exit 1; }
exec 9>"$root/builds/$EDF_TARGET/.edf-build.lock"
flock -n 9 || { echo 'Another command is using this target build directory.' >&2; exit 1; }
# Initialize tools only after taking the lock; do not run BitBake or build recipes.
source /opt/edf-scripts/yocto-env.sh >/dev/null
exec python3 /opt/edf-scripts/export.py "$BUILDDIR"
