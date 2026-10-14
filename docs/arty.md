# Arty Z7-20 / DVRMC

`arty-z7-20` is a concrete EDF target for the DVRMC design on the Digilent Arty
Z7-20 (`xc7z020clg400-1`). It uses a generated SDT machine for board firmware and
`amd-cortexa9thf-neon-common` for Linux. Its build state is separate from ZC702.

The current hardware bundle was exported from the implemented `~/workspace/dvrmc`
design with Vivado 2026.1. The original project was not modified. The design has
512 MiB DDR, UART0 at 115200 baud, SD0, Ethernet0, a 100 MHz FCLK0, and a 20 MHz
FCLK1. `controller_axi_0` occupies `0x43c00000–0x43c0ffff` on the 20 MHz clock.
Use these generated inputs, not a ZC702 device tree or FSBL.

## Build and export

With the matching bundle under `hardware/arty-z7-20/`:

```sh
./edf --target arty-z7-20 check
./edf --target arty-z7-20 image
./edf --target arty-z7-20 export
# Optional development SDK, installed separately on the development computer:
./edf --target arty-z7-20 sdk
```

Direct BitBake is still available:

```sh
./edf --target arty-z7-20 --machine board bitbake xilinx-bootbin
./edf --target arty-z7-20 bitbake dvrmc-firmware
./edf --target arty-z7-20 bitbake edf-linux-disk-image
```

The `image` command builds both board firmware and Linux. `export` inserts the
board's BOOT.BIN into a copy of the common Linux SD image. BOOT.BIN contains the
processor boot firmware and base device tree; **it does not contain the FPGA
bitstream**. The Linux root filesystem includes `dvrmc-firmware` and `fpgautil`.
The SDK is not part of the SD image. QEMU is not provided for this custom PL design.

The standard Docker context selection applies, including `--context orbstack` on
macOS. Ordinary builds require Docker, not a host Vivado installation. Hardware
export/generation needs AMD tools on a supported host; transfer the resulting
bundle and matching repository files to a Mac to build there.

## Load from Linux

As root, load explicitly after Linux boots, before accessing PL registers:

```sh
fpgautil -b /lib/firmware/xilinx/dvrmc-firmware/dvrmc-firmware.bin \
         -o /lib/firmware/xilinx/dvrmc-firmware/dvrmc-firmware.dtbo
cat /sys/class/fpga_manager/fpga0/state
```

A successful load reports `operating`. The full overlay asks FPGA Manager to
program the fabric and publishes the PL GPIO, I2C, clocks, and controller nodes.
The base tree excludes these PL devices, preventing premature driver probing.
The kernel also includes the Xilinx FCLK driver to keep both fabric clocks
enabled. The package records its inputs in `hardware-inputs.json` alongside the
firmware. The recipe uses AMD's `dfx_user_dts` class to convert the Vivado `.bit` to the
Zynq FPGA Manager `.bin` format and keep the overlay firmware name consistent.

Loading firmware does not enable motor motion. The controller retains its reset
inhibit and requires its normal configuration, watchdog and enable sequence.
This work does not install a DMOTOR Linux driver or motion application. The
controller's generated `xlnx,controller-axi-0.18` compatible is retained; a Linux
MMIO access/driver integration remains a separate step. Do not reload or remove
the overlay while a driver/application is using the PL devices.

## Regenerate after a Vivado hardware change

Bitstream, SDT, FSBL configuration, Linux base tree and overlay are a matched set.
Do not replace only the `.bit` after changing addresses, clocks, PS configuration,
or IP interfaces. The launcher verifies the SHA-256 bundle manifest and rejects
missing or changed inputs. Generated binaries remain outside Git, under the
ignored `hardware/` directory; preserve that directory along with this revision.

1. Generate the bitstream for the implemented DVRMC design, then export a fixed
   XSA **including the bitstream**. In Vivado with that project open:

   ```tcl
   write_hw_platform -fixed -include_bit -force -file /path/to/edf-dev/hardware/arty-z7-20/dvrmc.xsa
   ```

2. On the AMD-tool host, generate a fresh SDT in a staging directory:

   ```sh
   /opt/vitis/2026.1/Vitis/bin/sdtgen \
     -xsa hardware/arty-z7-20/dvrmc.xsa -dir artifacts/arty-sdt
   ```

   Copy `artifacts/arty-sdt` to `hardware/arty-z7-20/sdt` before the following
   generation step. Keep a copy of the previous bundle if rollback is needed.

3. Generate EDF configuration using the pinned container tools. The existing
   ZC702 environment bootstraps the tool dependencies; the generated machine is
   Arty, not ZC702. In `./edf --target zc702 shell`:

   ```sh
   mkdir -p /artifacts/arty-generation
   cd /artifacts/arty-generation
   /opt/edf/sources/meta-xilinx/meta-xilinx-core/gen-machine-conf/gen-machine-conf \
     --hw-description /hardware/arty-z7-20/sdt --machine-name arty-z7-20 \
     -c /artifacts/arty-generation/conf --output /artifacts/arty-generation/work -g full
   exit
   ```

   Use a writable working directory: this version of the configuration frontend
   writes temporary files in its current directory.

4. Install and fingerprint the matched generated inputs on the host:

   ```sh
   python3 scripts/arty-hardware.py --sdt hardware/arty-z7-20/sdt \
     --conf artifacts/arty-generation/conf
   python3 scripts/arty-hardware.py
   ```

   The installer copies the generated BSP into `meta-edf-dev/conf`, installs the
   bitstream and overlay under `hardware/arty-z7-20`, and updates
   `config/hardware/arty-z7-20.json`. It also corrects SDTGen 2026.1's erroneous
   MicroBlaze root compatible to `digilent,arty-z7-20`, `xlnx,zynq-7000` in the
   Linux tree. It regenerates base-tree symbols and declares the overlay bus
   cell widths explicitly. Review the generated changes before rebuilding.

## Qualification

See [validation evidence](arty-validation.txt) for the checks performed.
This target establishes the software build and explicit Linux loading path.
Physical SD boot, Ethernet/USB behavior, overlay loading on the Arty, and motor
operation still require board testing. The motor controller and H-bridge retain
their own integration and timing qualification requirements.
