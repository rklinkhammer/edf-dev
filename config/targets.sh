# One shared host image; target architecture is selected by Yocto MACHINE.
case "${EDF_TARGET:-zc702}" in
  zc702)
    export EDF_TARGET=zc702 BOARD_MACHINE=zynq-zc702-sdt-full
    export LINUX_MACHINE=amd-cortexa9thf-neon-common ;;
  zcu111)
    export EDF_TARGET=zcu111 BOARD_MACHINE=zynqmp-zcu111-sdt-full
    export LINUX_MACHINE=amd-cortexa53-common ;;
  *) echo "Unknown EDF target: ${EDF_TARGET}" >&2; return 2 ;;
esac
