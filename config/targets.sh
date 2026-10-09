# Shared defaults; each target has one checked-in definition.
export EDF_TARGET=${EDF_TARGET:-zc702}
[[ $EDF_TARGET =~ ^[a-z0-9-]+$ && -f /opt/edf-config/targets/$EDF_TARGET.sh ]] || {
  echo "Unknown target: $EDF_TARGET" >&2; return 2;
}
export EDF_VENDOR=amd IMAGE_RECIPE=edf-linux-disk-image KERNEL_RECIPE=linux-xlnx
export BOOT_RECIPE=xilinx-bootbin QEMU_SUPPORTED=1 SOURCE_ROOT=/opt/edf
source "/opt/edf-config/targets/$EDF_TARGET.sh" || return
