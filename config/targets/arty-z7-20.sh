export BOARD_MACHINE=arty-z7-20 LINUX_MACHINE=amd-cortexa9thf-neon-common QEMU_SUPPORTED=0
[[ -f /project/meta-edf-dev/conf/machine/arty-z7-20.conf ]] || {
  echo 'Arty requires its generated EDF/SDT machine configuration and matching hardware inputs. See docs/arty.md.' >&2
  return 2
}
