#!/bin/bash
set -euo pipefail
cd /home/amd-edf/edf
exec 9>.edf-sources.lock
flock -n -x 9 || { echo 'Builds or another source sync are active.' >&2; exit 1; }
repo init -u https://github.com/Xilinx/yocto-manifests.git -b refs/tags/amd-edf-rel-v26.06.1 -m default-edf.xml
repo sync -j4
repo manifest -r -o /artifacts/manifest-26.06.1.xml

repo version > /artifacts/repo-version.txt
git -C .repo/repo rev-parse HEAD >> /artifacts/repo-version.txt
