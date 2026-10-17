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

# The production binding owns the GPIO-to-HALT source and excludes UIO.
EDF_DMOTOR_ACCESS ?= "inspection"
python do_patch:append() {
    from pathlib import Path
    path = Path(d.getVar('WORKDIR')) / 'dvrmc.dtso'
    text = path.read_text()
    original = 'compatible = "xlnx,controller-axi-0.18";'
    if text.count(original) != 1:
        bb.fatal('Expected exactly one DVRMC controller binding')
    mode = d.getVar('EDF_DMOTOR_ACCESS')
    if mode == 'inspection':
        binding = 'compatible = "generic-uio";\n                linux,uio-name = "dmotor-inspection";'
    elif mode == 'production':
        if 'axi_gpio_3: gpio@41230000' not in text:
            bb.fatal('Production HALT binding requires the reviewed DVRMC axi_gpio_3 topology')
        binding = 'compatible = "dmotor,controller-0.18";\n                halt-gpios = <&axi_gpio_3 0 0>;'
    else:
        bb.fatal('EDF_DMOTOR_ACCESS must be inspection or production')
    path.write_text(text.replace(original, binding))
}
