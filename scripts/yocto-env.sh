# Source this file; all build state is isolated by target, caches are shared.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  echo 'Use: source /opt/edf-scripts/yocto-env.sh' >&2; exit 2
fi
source /opt/edf-config/targets.sh || return
edf_build_dir="/home/amd-edf/edf/builds/$EDF_TARGET"
mkdir -p "$edf_build_dir" || return
cd "$SOURCE_ROOT" || return
if [[ $EDF_VENDOR == microchip ]]; then
  [[ -f openembedded-core/oe-init-build-env ]] || { echo 'Run ./edf sync mpfs-disco-kit first.' >&2; return 1; }
  export TEMPLATECONF="$SOURCE_ROOT/meta-mchp/meta-mchp-polarfire-soc/meta-mchp-polarfire-soc-bsp/conf/templates/default"
  source openembedded-core/oe-init-build-env "$edf_build_dir" || return
else
  [[ -f edf-init-build-env ]] || { echo "Run ./edf sync $EDF_TARGET first." >&2; return 1; }
  source ./edf-init-build-env "$edf_build_dir" || return
fi
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

if [[ $EDF_VENDOR == microchip ]] && ! grep -q '^# Microchip workspace settings' conf/local.conf; then
  cat >> conf/local.conf <<CONF

# Microchip workspace settings
MACHINE = "$BOARD_MACHINE"
TMPDIR = "\${TOPDIR}/tmp"
IMAGE_FSTYPES:append = " tar.gz"
CONF
fi

# Append once for new and existing builds; users keep overrides in a separate file.
if ! grep -qxF 'require /opt/edf-config/build-policy.inc' conf/local.conf; then
  cat >> conf/local.conf <<'CONF'

# Shared host/cache/disk policy for every architecture.
require /opt/edf-config/build-policy.inc
include conf/edf-policy.conf
CONF
fi
