FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append = "${@' file://dvrmc-fpga.cfg' if d.getVar('EDF_DVRMC') == '1' else ''}"
