# Source this file; all build state is isolated by target, caches are shared.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  echo 'Use: source /opt/edf-scripts/yocto-env.sh' >&2; exit 2
fi
source /opt/edf-config/targets.sh || return
cd /home/amd-edf/edf || return
[[ -f edf-init-build-env ]] || { echo 'Run ./edf sync first.' >&2; return 1; }
mkdir -p "builds/$EDF_TARGET" || return
source ./edf-init-build-env "builds/$EDF_TARGET" || return
[[ -f conf/local.conf ]] || { echo "EDF initialization did not create local.conf." >&2; return 1; }
if ! grep -q '^# edf-dev persistent settings' conf/local.conf; then
  cat >> conf/local.conf <<CONF

# edf-dev persistent settings
DL_DIR = "/home/amd-edf/edf/downloads"
SSTATE_DIR = "/home/amd-edf/edf/sstate-cache"
BB_NUMBER_THREADS = "4"
BB_NUMBER_PARSE_THREADS = "4"
PARALLEL_MAKE = "-j4"
MACHINE ??= "$BOARD_MACHINE"
include conf/edf-rootfs.conf
include conf/edf-kernel.conf
CONF
fi
printf 'EDF target: %s; build: %s\n' "$EDF_TARGET" "$BUILDDIR"
