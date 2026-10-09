#!/bin/bash
set -eo pipefail
root=/home/amd-edf/edf
cd "$root"
/opt/edf-scripts/validate.sh
source /opt/edf-config/targets.sh
mkdir -p "$root/builds/$EDF_TARGET"
exec 9>"$root/builds/$EDF_TARGET/.edf-build.lock"
flock -n 9 || { echo 'Another command is using this target.' >&2; exit 1; }
source /opt/edf-scripts/yocto-env.sh
case "${1:-image}" in
  validate) exit ;;
  shell)
    export MACHINE="$LINUX_MACHINE"
    export PS1="edf[$EDF_TARGET] \w\$ "
    printf 'Target: %s; BitBake MACHINE: %s\n' "$EDF_TARGET" "$MACHINE"
    exec bash --noprofile --norc -i ;;
  image) MACHINE="$BOARD_MACHINE" bitbake "$BOOT_RECIPE"; MACHINE="$LINUX_MACHINE" bitbake "$IMAGE_RECIPE" ;;
  boot) MACHINE="$BOARD_MACHINE" bitbake "$BOOT_RECIPE" ;;
  linux) MACHINE="$LINUX_MACHINE" bitbake "$IMAGE_RECIPE" ;;
  sdk) MACHINE="$LINUX_MACHINE" bitbake "$IMAGE_RECIPE" -c populate_sdk ;;
  check) MACHINE="$BOARD_MACHINE" bitbake -n "$BOOT_RECIPE"; MACHINE="$LINUX_MACHINE" bitbake -n "$IMAGE_RECIPE" ;;
  export) python3 /opt/edf-scripts/export.py "$BUILDDIR" ;;
  qemu|qemu-prepare)
    [[ $QEMU_SUPPORTED == 1 ]] || { echo 'QEMU unsupported for this target.' >&2; exit 2; }
    /opt/edf-scripts/qemu.sh "${1}" ;;
  *) MACHINE="$LINUX_MACHINE" bitbake "$@" ;;
esac
