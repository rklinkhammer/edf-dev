# One shared host image; target architecture is selected by Yocto MACHINE.
export EDF_VENDOR=amd IMAGE_RECIPE=edf-linux-disk-image KERNEL_RECIPE=linux-xlnx
export BOOT_RECIPE=xilinx-bootbin QEMU_SUPPORTED=1
export SOURCE_ROOT=/home/amd-edf/edf
case "${EDF_TARGET:-zc702}" in
  zc702)
    export EDF_TARGET=zc702 BOARD_MACHINE=zynq-zc702-sdt-full
    export LINUX_MACHINE=amd-cortexa9thf-neon-common ;;
  zcu111)
    export EDF_TARGET=zcu111 BOARD_MACHINE=zynqmp-zcu111-sdt-full
    export LINUX_MACHINE=amd-cortexa53-common ;;
  mpfs-disco-kit)
    export EDF_TARGET=mpfs-disco-kit EDF_VENDOR=microchip
    export BOOT_RECIPE=virtual/bootloader QEMU_SUPPORTED=0
    export BOARD_MACHINE=mpfs-disco-kit LINUX_MACHINE=mpfs-disco-kit
    export IMAGE_RECIPE=mchp-base-image KERNEL_RECIPE=linux-mchp
    export SOURCE_ROOT=/home/amd-edf/microchip ;;
  *) echo "Unknown EDF target: ${EDF_TARGET}" >&2; return 2 ;;
esac
