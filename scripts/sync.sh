#!/bin/bash
set -euo pipefail
source /opt/edf-config/targets.sh
mkdir -p "$SOURCE_ROOT"
cd /home/amd-edf/edf
exec 9>.edf-sources.lock
flock -n -x 9 || { echo 'Builds or another source sync are active.' >&2; exit 1; }
if [[ $EDF_VENDOR == microchip ]]; then
  command -v git-lfs >/dev/null || { echo 'Rebuild the container: ./edf build-container' >&2; exit 1; }
  cd "$SOURCE_ROOT"
  repo init -u https://github.com/linux4microchip/meta-mchp-manifest.git -b refs/tags/linux4microchip-2026.04 -m polarfire-soc/default.xml
  repo sync -j4
  repo manifest -r -o /artifacts/manifest-microchip-2026.04.xml
  repo version > /artifacts/repo-version-microchip.txt
  exit
fi
repo init -u https://github.com/Xilinx/yocto-manifests.git -b refs/tags/amd-edf-rel-v26.06.1 -m default-edf.xml
repo sync -j4
repo manifest -r -o /artifacts/manifest-26.06.1.xml

repo version > /artifacts/repo-version.txt
git -C .repo/repo rev-parse HEAD >> /artifacts/repo-version.txt
