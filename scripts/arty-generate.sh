#!/bin/bash
set -eo pipefail
# Internal container helper: standalone staging mount, never the live hardware bundle.
export EDF_TARGET=zc702
mkdir -p /home/amd-edf/edf/builds/zc702
exec 9>/home/amd-edf/edf/builds/zc702/.edf-build.lock
flock -n 9 || { echo 'ZC702 bootstrap build is busy' >&2; exit 1; }
source /opt/edf-scripts/yocto-env.sh
cd /generation
/opt/edf/sources/meta-xilinx/meta-xilinx-core/gen-machine-conf/gen-machine-conf \
  --hw-description /generation/sdt --machine-name arty-z7-20 \
  -c /generation/conf --output /generation/work -g full
