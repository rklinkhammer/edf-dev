# Zybo Z7-20 DMOTOR workflow

Zybo uses the same hardware → matched bundle → boot/Linux → WIC export sequence
as Arty. Select `--target zybo-z7-20`. Arty remains separately supported, with its
own hardware files, machine configuration and artifact directories.

## Normal full build

The bumper input is assigned to JD package pin P14 (LVCMOS33). The auxiliary PL
UART is retained: TX on JD7 / U14 and RX on JD8 / U15, both LVCMOS33. All current
external scalar/UART ports pass the strict pin-assignment preflight. This does not
replace implementation DRC or physical wiring validation.

Save your wired Vivado BD and XDC back into dmotor's `platforms/zybo-z7-20` first
(see that platform's README). From `edf-dev`:

```sh
EDF_DMOTOR_SOURCE=../dmotor ./edf --target zybo-z7-20 build --dry-run
EDF_DMOTOR_SOURCE=../dmotor ./edf --target zybo-z7-20 build
```

`build` means `hardware --export-image`. It runs the shared dmotor IP/software
checks, creates a build project from the saved source, synthesizes/implements it,
requires timing and DRC acceptance, exports XSA, runs SDTGen/gen-machine-conf,
validates/imports the Zybo bundle, builds boot and Linux images, then exports.
The existing GUI editing project is preserved. The generated source-build project
is `dmotor/build/product/zybo-z7-20/release-vivado/zybo-z7-20.xpr`.

Hardware-only and subsequent image/export commands:

```sh
EDF_DMOTOR_SOURCE=../dmotor ./edf --target zybo-z7-20 hardware
EDF_DMOTOR_SOURCE=../dmotor ./edf --target zybo-z7-20 image
EDF_DMOTOR_SOURCE=../dmotor ./edf --target zybo-z7-20 export
```

Hardware artifacts are under the configured artifact root's `zybo-hardware/<run>`.
The export is under `zybo-z7-20/<run>` and includes **`sdcard.wic.xz` and
`sdcard.wic.bmap`**, plus boot/kernel/device-tree/rootfs files and provenance.
The raw `.wic` is produced in the container build deploy directory; export makes
a separate SD image with matching boot firmware and compresses it. To retain a
raw copy on the host, use `xz -dk /path/to/sdcard.wic.xz`.

Installed inputs are isolated to `hardware/zybo-z7-20`,
`config/hardware/zybo-z7-20.json` and the generated Zybo machine/multiconfig/DTS
files. The hardware stage must succeed before ordinary image/SDK commands work.
A bundle for Arty cannot be imported as Zybo.

## Existing artifacts and network deployment

The shared workflow also accepts `hardware --project /path/to/wired.xpr`,
`hardware --xsa /path/to/implemented.xsa`, and `hardware --bundle /path/to/hardware-bundle.tar.gz`.
An explicit project/XSA bypasses source IP rebuild; it is not automatically a
source-fingerprint-matched release. `--generate-only` validates a candidate without
installing it. `--export-image` adds image/export after a successful import.
AMD tools are required for hardware generation; verified bundles can be consumed
by the existing Docker/OrbStack workflow without Vivado on that host.

After boot, use `sudo dmotor-load-fpga` for first FPGA/overlay loading, as on Arty.
SCP application deployment remains supported; the SD/WIC workflow is retained.
Neither copying files nor loading the FPGA enables motors or implements live recovery.

## Board-specific configuration

- Zynq `xc7z020clg400-1`; generated Linux memory must describe 1 GiB.
- PS UART1, MIO48/49: USB serial console. Linux alias `serial0`, `/dev/ttyPS0`.
- PS UART0, MIO14/15: monitor UART. Linux alias `serial1`, `/dev/ttyPS1`.
  Use `/dev/ttyPS1` in diagnostic commands that used Arty's `/dev/ttyUL0`.
  Generated nodes must be enabled with clocks/IRQs; no UART node is fabricated.
- PL UART Lite may remain as an auxiliary port, but is not required as the monitor.
- Controller register window remains `0x43c00000`.
- HALT source is `axi_gpio_mc` at `0x41200000`, channel-one bit 0, active high.
  Firmware packaging rejects an overlay without that expected GPIO label/address.
- FPGA configuration remains a Linux full overlay; no FSBL bitstream insertion.

Linux preparation explicitly keeps console traffic off the monitor UART. Verify
FSBL/U-Boot console behavior and actual device identities during first boot, then
run inhibited UART/HB checks. Boot, DDR, Ethernet/SCP, I2C, motor-pin mapping,
shutdown timing and all Zybo hardware gates remain unaccepted until tested.

## Validation status

Launcher dry runs, host regression tests, target-specific binding/bundle tests and
Vivado build-project generation are checked. This integration has not yet produced
or boot-tested a complete Zybo XSA/SDT/Linux/WIC release. Project generation and
Validate Design alone are not bitstream generation; `hardware` performs that work.

## Garbled console fix — 2026-11-10

The imported dmotor PS configuration incorrectly specified a 50 MHz reference
oscillator. Digilent's Zybo Z7-20 preset and the downloaded 2025.1 Pcam project
specify 33.333333 MHz. dmotor now uses that value and guards against regression.
EDF now normalizes the FSBL and system-top-no-pl console aliases/stdout to UART1
at 115200 too; previously only the Linux DTS was corrected and the boot-domain
DTS still selected UART0 at 9600. The monitor remains UART0.

Rerun the full `build` command above, then provision the new WIC export. Do not
reuse the old hardware bundle or merely rerun `image`: FSBL must receive the
newly generated PS initialization. Existing manifests/exports were retained as
historical evidence. Keep the terminal at 115200 8N1 without flow control.
The corrected project and host tests pass; corrected-image boot validation is pending.

Reference: [Digilent Pcam demo](https://github.com/Digilent/Zybo-Z7-20-pcam-5c),
plus the local downloaded `Downloads/hw` project and its board preset. The demo
README also specifies a 115200-baud terminal; no demo camera logic is needed for
this correction.
