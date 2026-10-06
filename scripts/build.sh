#!/bin/bash
set -eo pipefail
# Builds share a read lock on sources, preventing sync during a build.
exec 8>/home/amd-edf/edf/.edf-sources.lock
flock -n -s 8 || { echo 'Source sync is active.' >&2; exit 1; }
source /opt/edf-config/targets.sh
mkdir -p "/home/amd-edf/edf/builds/$EDF_TARGET"
exec 9>"/home/amd-edf/edf/builds/$EDF_TARGET/.edf-build.lock"
flock -n 9 || { echo 'Another command is using this target build directory.' >&2; exit 1; }
source /opt/edf-scripts/yocto-env.sh
case "${1:-}" in
  boot)
    MACHINE="$BOARD_MACHINE" bitbake "$BOOT_RECIPE"
    if [[ $EDF_VENDOR == microchip ]]; then
      echo 'Built U-Boot/HSS payload inputs. Board HSS and FPGA programming are separate.'
    fi ;;
  linux) MACHINE="$LINUX_MACHINE" bitbake "$IMAGE_RECIPE" ;;
  sdk) MACHINE="$LINUX_MACHINE" bitbake "$IMAGE_RECIPE" -c populate_sdk ;;
  check)
    MACHINE="$BOARD_MACHINE" bitbake -n --no-setscene "$BOOT_RECIPE"
    MACHINE="$LINUX_MACHINE" bitbake -n --no-setscene "$IMAGE_RECIPE" ;;
  *) echo 'Unknown build action' >&2; exit 2 ;;
esac
