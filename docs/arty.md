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
firmware recipe binds the generated controller node to `generic-uio` for
inhibited inspection; a production motion driver remains a separate step. Do not reload or remove
the overlay while a driver/application is using the PL devices.

## Automated hardware build and import

Run on a Linux AMD-tool host, with the Vivado project saved and no GUI build running:

```sh
# Preview the workflow without invoking tools or modifying the bundle.
./edf --target arty-z7-20 hardware --dry-run

# Build the saved ../dvrmc/dvrmc.xpr and import its matched hardware bundle.
./edf --target arty-z7-20 hardware

# Also build Linux/boot firmware and export a fresh SD image.
./edf --target arty-z7-20 hardware --export-image
```

The workflow runs Vivado batch synthesis, implementation and bitstream generation
in a saved project copy, exports a fixed XSA containing the bitstream, runs SDTGen,
then uses the pinned Docker environment for `gen-machine-conf`. It installs into a
candidate directory first and verifies the bundle before updating live inputs.
There is no automatic IP upgrade or substitution of a newer DMOTOR IP repository;
the saved Vivado project determines the IP versions being built. External source
and IP dependencies must be available; save constraints before invoking the command.
If Vivado imported an XDC, edit/save the imported project copy: editing the original
file in `digilent-xdc` does not update that copy. The completed run includes `io.rpt`
to check physical pin assignments and pull settings in the implemented design.

Useful variants:

```sh
./edf --target arty-z7-20 hardware --project /path/to/dvrmc.xpr --jobs 4
./edf --target arty-z7-20 hardware --xsa /path/to/export-including-bitstream.xsa
./edf --target arty-z7-20 hardware --xsa /path/to/design.xsa --generate-only
```

`--xsa` skips Vivado and trusts the supplied implemented XSA; it cannot qualify
its timing or DRC. `--generate-only` retains a verified candidate without importing
it. Override `--vivado` and `--sdtgen` if tools are not installed under
`/opt/vitis/2026.1`. Vivado mode requires the expected part `xc7z020clg400-1`,
completed synthesis/implementation, nonnegative reported setup/hold slack and no
DRC errors before export. Timing/DRC reports remain available for review; these
checks do not constitute complete CDC, external-I/O or motor safety qualification.

Each invocation creates a fresh directory under `artifacts/arty-hardware/` (or the
configured artifacts mount), with XSA, SDT, generated configuration, candidate,
Vivado reports/logs and workflow metadata. Before import, `previous/` backs up all
files that will be overwritten and records affected paths in `restore.json`.
Normal import failures restore those files; a power loss or SIGKILL can interrupt
publication, so retain the backup for recovery. The manifest is copied last and
subsequent builds verify it. The previous bundle is not touched during generation.

Hardware commands take an exclusive repository lock; ordinary `./edf` builds take
a shared lock and refuse to overlap import. This protects commands started through
this checkout's launcher, not manual Docker/BitBake processes or another checkout
sharing the same volumes. Stop those before importing. The ZC702 generation
bootstrap also takes its existing container target lock.

Docker context selection is unchanged. Vivado/SDTGen run on the host; OrbStack does
not make AMD tools run on macOS. Use a supported tool host for this command and
transfer the resulting bundle/configuration for Mac-based EDF builds. The command
does not flash a board, load an FPGA or run motor commands.

The individual commands below remain useful for diagnosis or custom workflows.

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

## UIO inspection and software identity update

The Arty firmware recipe now changes the controller overlay binding to
`generic-uio`, named `dmotor-inspection`. The Arty base Linux device tree supplies `/chosen/bootargs` containing
`uio_pdrv_genirq.of_id=generic-uio`. The stock boot script reads this property
and appends its existing root arguments; UIO and its
generic platform driver are explicitly built in. No boot-script patch is used. Hardware regeneration preserves this base-tree
policy. Other targets are unchanged. Bitstream loading remains manual; this does not authorize motion.

Rebuild and export with `./edf --target arty-z7-20 image`, then
`./edf --target arty-z7-20 export`. On the newly booted image check:

```sh
cat /proc/cmdline
dmotor-inspect --version
cat /usr/share/dmotor/source-version.json
```

After loading the matched firmware/overlay with outputs externally inhibited,
check `/sys/class/uio/uio*/name` for `dmotor-inspection` before inspecting its index.
The mapping remains an inhibited bring-up interface with advisory locking, not a
production motion driver. Existing exports are not modified by these changes.

The base tree is packaged in the board boot artifacts. Rebuild both board firmware
and Linux (`image`), then export; replacing only the runtime FPGA overlay cannot
change a built-in driver parameter already consumed during kernel startup.

### Encoder-only maintenance utility

The Arty image includes `dmotor-encoder` (DMOTOR 0.5.0 or later). After loading the
FPGA, with all motors disabled/unconfigured and motor drive power disconnected:

```sh
sudo dmotor-encoder --externally-inhibited 0
```

It releases the encoder reset and prints raw positions every 250 ms. Rotate the
shaft manually and reverse direction to verify counts and channel mapping.
Ctrl-C restores core reset. Verify encoder A/B voltage compatibility before
connecting: a 5 V encoder supply does not establish 3.3 V-safe outputs. This
utility neither configures nor enables motion. It is separate from semantic
tests and is not started at boot. Do not reload the FPGA while it owns UIO.

To build local software changes instead of the pinned submodule, explicitly set
`EDF_DMOTOR_SOURCE=../dmotor` on the hardware/image command. Check the startup
version and `/usr/share/dmotor/source-version.json` against the exported build
metadata. For a deliberate IP upgrade, use the isolated-project preparation
workflow in `dmotor/docs/current_ip_export.md` before invoking `hardware`.

## Optional DMOTOR lifecycle commissioning

The default `EDF_DMOTOR_ACCESS = "inspection"` retains the working UIO tools.
The new `"production"` option selects the exclusive `dmotor_access` kernel
binding and installs `dmotord` plus the separate `dmotor-maint` menu. It does not
autostart motion or a service. This initial version is for drive-disconnected
commissioning; kernel HALT propagation and scheduling still require board tests.
See [DMOTOR commissioning](../../dmotor/software/linux/production.md) for the
configuration, image commands, and acceptance gates. The revision-6 FPGA already
contains the GPIO-to-HALT path, so this software milestone does not change RTL.
