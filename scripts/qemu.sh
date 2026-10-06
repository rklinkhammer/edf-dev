#!/bin/bash
# Runs inside the EDF container. The lock covers preparation and the guest lifetime.
set -eo pipefail
case "${1:-boot}" in boot|prepare) ;; *) echo 'Usage: ./edf qemu[-prepare] [TARGET]' >&2; exit 2;; esac
source /opt/edf-config/targets.sh
[[ $QEMU_SUPPORTED == 1 ]] || { echo "Discovery Kit QEMU boot is not implemented; use physical hardware." >&2; exit 2; }
exec 8>/home/amd-edf/edf/.edf-sources.lock
flock -n -s 8 || { echo "Source sync is active." >&2; exit 1; }
source /opt/edf-scripts/yocto-env.sh >/dev/null
exec 9>"$BUILDDIR/.edf-build.lock"
flock -n 9 || { echo 'Another command is using this target build directory.' >&2; exit 1; }
python3 /opt/edf-scripts/prepare-qemu.py "$BUILDDIR"
if [[ ${1:-boot} == prepare ]]; then exit 0; fi
# AMD's QEMU boot helper invokes wic, which needs image-native parted/mtools.
edf_native=$(python3 - "$BUILDDIR/tmp/deploy/images/$LINUX_MACHINE/edf-linux-disk-image-$LINUX_MACHINE.rootfs.qemuboot.conf" <<'PYCONF'
import configparser, pathlib, sys
p = pathlib.Path(sys.argv[1]); c = configparser.ConfigParser(interpolation=None); c.read(p)
print((p.parent / c['config_bsp']['staging_dir_native']).resolve())
PYCONF
)
export PATH="$PATH:$edf_native/usr/bin:$edf_native/usr/sbin"
printf '\nBooting %s. Exit QEMU with Ctrl+A, then X. Guest changes are discarded.\n' "$EDF_TARGET"
runqemu "$BUILDDIR/tmp/deploy/images/${EDF_TARGET}-qemu/${EDF_TARGET}.qemuboot.conf" nographic slirp snapshot 2>&1 | tee "$BUILDDIR/qemu-console.log"
# This release's runqemu can report launch errors while returning zero.
if grep -q 'runqemu - ERROR' "$BUILDDIR/qemu-console.log"; then exit 1; fi
