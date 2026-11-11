export BOARD_MACHINE=zybo-z7-20 LINUX_MACHINE=amd-cortexa9thf-neon-common QEMU_SUPPORTED=0
[[ -f /hardware/zybo-z7-20/sdt/system-top.dts && -f /hardware/zybo-z7-20/dvrmc.bit && -f /hardware/zybo-z7-20/dvrmc.dtso ]] || {
  echo 'Zybo requires its DVRMC hardware bundle in hardware/zybo-z7-20. See docs/zybo.md.' >&2
  return 2
}
python3 /opt/edf-scripts/arty-hardware.py --target zybo-z7-20 --root /project --hardware-root /hardware || return 2
