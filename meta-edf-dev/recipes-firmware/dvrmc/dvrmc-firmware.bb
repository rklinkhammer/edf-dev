SUMMARY = "DVRMC full FPGA image and matching Linux overlay for supported Zynq boards"

# Generated together from the same implemented XSA; see docs/arty.md.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:/hardware/${EDF_DVRMC_BOARD}:/project/config/hardware:"
SRC_URI = "file://dvrmc.bit file://dvrmc.dtso file://${EDF_DVRMC_BOARD}.json file://check_monitor_uart.py file://dmotor-load-fpga"
S = "${WORKDIR}"
COMPATIBLE_MACHINE = "(arty-z7-20|zybo-z7-20|amd-cortexa9thf-neon-common)"
PACKAGE_ARCH = "${MACHINE_ARCH}"
# The generated overlay is self-contained; it does not include kernel headers.
KERNEL_INCLUDE = ""

inherit dfx_user_dts
# devicetree.bbclass supplies a kernel-source license by default. This recipe
# packages the user's hardware export, not an in-kernel device-tree source.
LICENSE = "CLOSED"
LIC_FILES_CHKSUM = ""

RDEPENDS:${PN} += "fpga-manager-script"
FILES:${PN} += "${sbindir}/dmotor-load-fpga"

do_install:append() {
    install -d ${D}${sbindir}
    install -m 0755 ${WORKDIR}/dmotor-load-fpga ${D}${sbindir}/dmotor-load-fpga
    install -m 0644 ${WORKDIR}/${EDF_DVRMC_BOARD}.json ${D}${nonarch_base_libdir}/firmware/xilinx/${FW_INSTALL_DIR}/hardware-inputs.json
}

python () {
    if d.getVar('EDF_DVRMC') != '1':
        raise bb.parse.SkipRecipe('DVRMC firmware is selected only by DMOTOR board targets')
}

# The production binding owns the GPIO-to-HALT source and excludes UIO.
EDF_DMOTOR_ACCESS ?= "inspection"
python do_patch:append() {
    from pathlib import Path
    path = Path(d.getVar('WORKDIR')) / 'dvrmc.dtso'
    text = path.read_text()
    import runpy
    check = runpy.run_path(str(Path(d.getVar('WORKDIR')) / 'check_monitor_uart.py'))
    try:
        if d.getVar('EDF_MONITOR_UART') == 'uartlite':
            check['validate'](text)
        elif d.getVar('EDF_MONITOR_UART') != 'ps-uart0':
            raise ValueError('Unknown monitor UART topology')
    except ValueError as error:
        bb.fatal(str(error))
    original = 'compatible = "xlnx,controller-axi-0.18";'
    if text.count(original) != 1:
        bb.fatal('Expected exactly one DVRMC controller binding')
    mode = d.getVar('EDF_DMOTOR_ACCESS')
    if mode == 'inspection':
        binding = 'compatible = "generic-uio";\n                linux,uio-name = "dmotor-inspection";'
    elif mode == 'production':
        gpio = d.getVar('EDF_HALT_GPIO')
        address = d.getVar('EDF_HALT_GPIO_ADDRESS')
        if f'{gpio}: gpio@{address}' not in text:
            bb.fatal('Production HALT binding requires the reviewed board-specific GPIO topology')
        binding = f'compatible = "dmotor,controller-0.18";\n                halt-gpios = <&{gpio} 0 0>;'
    else:
        bb.fatal('EDF_DMOTOR_ACCESS must be inspection or production')
    path.write_text(text.replace(original, binding))
}
