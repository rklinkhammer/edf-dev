FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append = "${@' file://dvrmc-fpga.cfg' if d.getVar('EDF_DVRMC') == '1' else ''}"

# Fail if Kconfig silently drops the monitor driver from an Arty kernel.
do_configure:append() {
    if [ "${EDF_DVRMC}" = "1" ]; then
        grep -qx 'CONFIG_SERIAL_UARTLITE=y' ${B}/.config || bbfatal "Arty monitor requires built-in CONFIG_SERIAL_UARTLITE"
        if grep -qx 'CONFIG_SERIAL_UARTLITE_CONSOLE=y' ${B}/.config; then
            bbfatal "Monitor UART Lite must not be a kernel console"
        fi
    fi
}
