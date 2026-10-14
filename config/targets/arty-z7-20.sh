export BOARD_MACHINE=arty-z7-20 LINUX_MACHINE=amd-cortexa9thf-neon-common QEMU_SUPPORTED=0
[[ -f /hardware/arty-z7-20/sdt/system-top.dts && -f /hardware/arty-z7-20/dvrmc.bit && -f /hardware/arty-z7-20/dvrmc.dtso ]] || {
  echo 'Arty requires its DVRMC hardware bundle in hardware/arty-z7-20. See docs/arty.md.' >&2
  return 2
}
python3 /opt/edf-scripts/arty-hardware.py --root /project --hardware-root /hardware || return 2
