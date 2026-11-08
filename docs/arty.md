# Arty Z7-20 / DMOTOR board operation

**All build commands are centralized in [the build guide](build.md).** Hardware
sources belong to DMOTOR at `platforms/arty-z7-20`; EDF consumes a matched bundle.
The previous DVRMC/manual-import instructions are [historical](history/arty-build-manual.md).

## Platform

Arty Z7-20, `xc7z020clg400-1`, 512 MiB DDR, UART0 at 115200 baud, SD0,
Ethernet0, 100 MHz FCLK0 and 20 MHz FCLK1. The controller occupies
`0x43c00000–0x43c0ffff`. Generated board firmware and Linux machine inputs must
come from the same XSA. BOOT.BIN contains processor firmware, not the PL bitstream.
Linux loads PL with FPGA Manager and a full overlay, keeping PL drivers out of the
base device tree. Do not remove/reload PL while applications own its devices.

## Load and inspect

After boot, with motor drive externally inhibited:

```sh
sudo dmotor-load-fpga --dry-run
sudo dmotor-load-fpga
cat /sys/class/fpga_manager/fpga0/state
cat /usr/share/dmotor/source-version.json
```

`dmotor-load-fpga` is installed in `/usr/sbin` by `dvrmc-firmware` in newly
built images. It loads the packaged `.bin` and `.dtbo` together using `fpgautil`,
checks that provenance is present, and verifies the resulting manager state.
It does not verify cryptographic pairing of arbitrary files: use the matched EDF
package. `--firmware-dir DIR` selects another directory containing the same three
filenames. `--dry-run` checks files/tool availability without programming hardware.

This is an explicit first-load command, not a boot service or live-reload tool.
It refuses an already operating FPGA, existing overlays or `/dev/dmotor0`, and
serializes invocations with `/run/dmotor-load-fpga.lock`. It never removes overlays,
stops applications, retries partial loads or enables motors. After a failed load,
inspect the kernel log and reboot before another attempt. If a killed process
left a lock, remove it only after confirming no load process remains.

To use the helper on an existing image that already contains `fpgautil` and the
matched firmware, copy just the script from the EDF checkout:

```sh
scp meta-edf-dev/recipes-firmware/dvrmc/files/dmotor-load-fpga amd-edf@amd-edf:~/
ssh amd-edf@amd-edf
sudo install -m 0755 ~/dmotor-load-fpga /usr/sbin/dmotor-load-fpga
sudo dmotor-load-fpga --dry-run
sudo dmotor-load-fpga
```

Use the actual account/address. Copying/installing this helper does not update
firmware or automatically program PL. Full EDF image build/export remains supported.

Expected FPGA Manager state is `operating`. Firmware provenance is stored beside
it in `hardware-inputs.json`. Loading PL does not configure or enable motors.

## Inspection versus production access

Set `EDF_DMOTOR_ACCESS` in `config/targets/arty-z7-20.conf` and rebuild/deploy the
image; this is not a live runtime switch.

- `inspection` uses generic UIO and the inhibited `dmotor-inspect` / `dmotor-encoder`
  utilities. Kernel boot arguments must include `uio_pdrv_genirq.of_id=generic-uio`;
  the target configuration supplies this at boot, not through a PL overlay.
- `production` uses the exclusive `dmotor_access` driver at `/dev/dmotor0` and
  installs `dmotord` / `dmotor-maint`. No service or motion starts automatically.
  Its initial use is drive-disconnected commissioning, not qualified powered motion.

For inspection:

```sh
ls -l /dev/uio*
for d in /sys/class/uio/uio*; do echo "$d: $(cat "$d/name")"; done
sudo dmotor-inspect --externally-inhibited 0
sudo dmotor-encoder --externally-inhibited 0
```

Confirm the UIO name is `dmotor-inspection` before using an index. Encoder movement
has been observed on hardware; direction, counts/revolution and powered control
remain separate checks. Production commissioning instructions are in
`dmotor/software/linux/production.md` in the selected DMOTOR checkout.
