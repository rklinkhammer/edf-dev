SUMMARY = "DVRMC full FPGA image and matching Linux overlay for Arty Z7-20"

# Generated together from the same implemented XSA; see docs/arty.md.
FILESEXTRAPATHS:prepend := "/hardware/arty-z7-20:/project/config/hardware:"
SRC_URI = "file://dvrmc.bit file://dvrmc.dtso file://arty-z7-20.json"
S = "${WORKDIR}"
COMPATIBLE_MACHINE = "(arty-z7-20|amd-cortexa9thf-neon-common)"
PACKAGE_ARCH = "${MACHINE_ARCH}"
# The generated overlay is self-contained; it does not include kernel headers.
KERNEL_INCLUDE = ""

inherit dfx_user_dts
# devicetree.bbclass supplies a kernel-source license by default. This recipe
# packages the user's hardware export, not an in-kernel device-tree source.
LICENSE = "CLOSED"
LIC_FILES_CHKSUM = ""

do_install:append() {
    install -m 0644 ${WORKDIR}/arty-z7-20.json ${D}${nonarch_base_libdir}/firmware/xilinx/${FW_INSTALL_DIR}/hardware-inputs.json
}

python () {
    if d.getVar('EDF_DVRMC') != '1':
        raise bb.parse.SkipRecipe('DVRMC firmware is selected only by the Arty target')
}
