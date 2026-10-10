#!/bin/bash
# Runs inside the EDF container. The lock covers preparation and the guest lifetime.
set -eo pipefail
case "${1:-qemu}" in qemu|qemu-prepare) ;; *) echo 'Usage: ./edf qemu[-prepare] [TARGET]' >&2; exit 2;; esac
python3 /opt/edf-scripts/prepare-qemu.py "$BUILDDIR"
if [[ ${1:-qemu} == qemu-prepare ]]; then exit 0; fi
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
