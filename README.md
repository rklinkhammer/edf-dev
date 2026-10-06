# EDF and PolarFire SoC development environment

One Ubuntu 22.04 build container supports three targets: AMD ZC702, AMD ZCU111,
and the Microchip PolarFire SoC Discovery Kit. The container runs **x86-64 Linux
(`linux/amd64`)** through OrbStack/Rosetta on Apple Silicon. The target CPU
architecture is selected by Yocto; it is independent of the container architecture.
SDK installers also run on x86-64 Linux and cross-compile for the selected target.

The project is `/Volumes/Zeus/workspace/edf-dev`. OrbStack's managed data is at
`/Volumes/Zeus/orbstack`. Keep these directories separate: **never select the
project directory as OrbStack's data location**. The project uses named Docker
volumes for sources, builds and caches, not macOS bind mounts for those files.

## Targets and recipes

| Target argument | Board / Linux CPU architecture | Source release | Firmware machine | Linux image machine | Linux image recipe |
| --- | --- | --- | --- | --- | --- |
| `zc702` | Zynq-7000 ZC702 / Cortex-A9, ARM32 | AMD EDF `amd-edf-rel-v26.06.1` | `zynq-zc702-sdt-full` | `amd-cortexa9thf-neon-common` | `edf-linux-disk-image` |
| `zcu111` | Zynq UltraScale+ RFSoC ZCU111 / Cortex-A53, ARM64 | AMD EDF `amd-edf-rel-v26.06.1` | `zynqmp-zcu111-sdt-full` | `amd-cortexa53-common` | `edf-linux-disk-image` |
| `mpfs-disco-kit` | PolarFire SoC Discovery Kit / RISC-V 64-bit | Microchip `linux4microchip-2026.04` | `mpfs-disco-kit` | `mpfs-disco-kit` | `mchp-base-image` |

The target is `zc702`, not `zcu702`. Commands default to `zc702` when the target
argument is omitted; examples below specify it explicitly. Arty Z7-20 remains
future work and is not interchangeable with ZC702 firmware.

| Operation | ZC702 | ZCU111 | Discovery Kit |
| --- | --- | --- | --- |
| `boot` | `xilinx-bootbin` board boot image | `xilinx-bootbin` board boot image | `virtual/bootloader` → `u-boot-mchp`, including HSS payload |
| `linux` | EDF Linux image | EDF Linux image | Microchip Linux image, including bootloader dependencies |
| `sdk` | x86-64 Linux SDK targeting ARM32 | x86-64 Linux SDK targeting ARM64 | x86-64 Linux SDK targeting RISC-V 64-bit |
| Kernel configuration | `linux-xlnx` | `linux-xlnx` | `linux-mchp` |
| RootFS configuration | Selected image's packages/features | Selected image's packages/features | Selected image's packages/features |
| `qemu` / `qemu-prepare` | Implemented | Implemented; no RF/PL hardware validation | Not implemented; command reports unsupported |
| `export` | Board-specific `.wic.xz` and artifacts | Board-specific `.wic.xz` and artifacts | Vendor-layout `.wic.gz` and artifacts |

## Storage: volumes, architectures and artifacts

All four named volumes are Linux-backed and managed by OrbStack within its data
location on Zeus. Their names do not imply a fixed allocation or a dedicated CPU
architecture. Removing a container keeps them; `docker compose down -v` deletes
this project's named volumes.

| Named volume | Mount inside container | Targets / architectures supported | Contents |
| --- | --- | --- | --- |
| `edf-dev_workspace` | `/home/amd-edf/edf` | **All three:** ARM32, ARM64 and RISC-V 64-bit | Shared AMD source checkout; separate `builds/<target>/` trees for **every target**, including PolarFire; configuration, temporary work, deployed firmware/Linux images, SDK installers and staged AMD QEMU disks |
| `edf-dev_microchip-workspace` | `/home/amd-edf/microchip` | Discovery Kit / RISC-V 64-bit | Separate Microchip manifest and source checkout. Its build outputs are in `edf-dev_workspace`, not here |
| `edf-dev_downloads` | `/home/amd-edf/edf/downloads` | All three targets plus their host build tools | `DL_DIR`: downloaded archives, fetched Git repositories and other recipe inputs |
| `edf-dev_sstate-cache` | `/home/amd-edf/edf/sstate-cache` | All three targets plus compatible host/native tasks | `SSTATE_DIR`: reusable task results, selected by Yocto signatures and architecture metadata |

The downloads and sstate mounts overlay subdirectories of the main workspace;
their bytes belong to their own volumes. Sharing sstate does not mix target
binaries: only compatible task signatures can be reused.

| Target | Build directory inside container | Deployment outputs |
| --- | --- | --- |
| `zc702` | `/home/amd-edf/edf/builds/zc702` | `tmp/deploy/images/zynq-zc702-sdt-full/`, `tmp/deploy/images/amd-cortexa9thf-neon-common/`, `tmp/deploy/sdk/` |
| `zcu111` | `/home/amd-edf/edf/builds/zcu111` | `tmp/deploy/images/zynqmp-zcu111-sdt-full/`, `tmp/deploy/images/amd-cortexa53-common/`, `tmp/deploy/sdk/` |
| `mpfs-disco-kit` | `/home/amd-edf/edf/builds/mpfs-disco-kit` | `tmp/deploy/images/mpfs-disco-kit/`, `tmp/deploy/sdk/` |

Deployment paths in the last column are relative to that target's build directory.
Each target owns its `conf/` and `tmp/`; never share `TMPDIR` between concurrent
builds. AMD targets share one source checkout; Microchip uses its separate checkout.

The following paths are **host directories, not named volumes**. Relative paths
are under `/Volumes/Zeus/workspace/edf-dev`.

| Host path | Container mount | Targets / purpose |
| --- | --- | --- |
| `scripts/` | `/opt/edf-scripts` (read-only) | Shared launch, configuration, QEMU and export helpers |
| `config/` | `/opt/edf-config` (read-only) | All target and recipe mappings |
| `hardware/` | `/hardware` (read-only) | User-provided hardware inputs; mounting files does not automatically include them in an image |
| `artifacts/` | `/artifacts` (read/write) | Exports under `<target>/<timestamp>-<id>/`, interactive logs under `logs/<target>/`, source manifests and container inventory |
| `validation/` | Not mounted | Host command logs and validation results |
| `layers/` (future) | Not currently mounted | Proposed custom layer sources; see custom integration below |

Docker images and Docker build-layer caches also live in OrbStack's managed
storage, outside these four named volumes. Deleting Yocto caches does not delete
Docker's image-layer cache or host exports.

## Setup and source synchronization

Run on macOS with OrbStack running. This builds the shared host image once;
normal board builds do not require rebuilding it for each architecture.

```sh
cd /Volumes/Zeus/workspace/edf-dev
./edf build-container
./edf validate

# One AMD sync serves both ZC702 and ZCU111.
./edf sync zc702

# Separate Microchip checkout; run if using the Discovery Kit.
./edf sync mpfs-disco-kit
```

For a fully fresh test, use the reset instructions below first. A source sync
only downloads the release-pinned checkouts; it does not build board images.
The helpers prevent source sync during wrapped builds. Direct BitBake commands
bypass those locks and must be coordinated manually.

### Cache policy and free-space thresholds

All targets use `config/build-policy.inc`: remote sstate and the upstream hash
service are disabled, the SDK host is x86-64 Linux, and the disk monitor stops
scheduling below **15 GiB** free and halts below **10 GiB** on build/download
storage. Local downloads and compatible sstate remain reusable. These thresholds
are free-space guards, not volume-size limits.

The shared policy is included when a target environment is initialized, including
existing build directories. It supersedes earlier vendor defaults. To customize
one target, put overrides in that build directory's `conf/edf-policy.conf`, which
is included afterward and is never overwritten by the helper. For example:

```sh
./edf shell zc702    # or zcu111 / mpfs-disco-kit
# Inside the shell:
source /opt/edf-scripts/yocto-env.sh
# Edit conf/edf-policy.conf here for this target only.
```

Normal source mirrors and required binary inputs remain available. Empty local
downloads/sstate plus these defaults avoid remote sstate reuse, but existing
build outputs can still avoid compilation; use the full reset for a clean test.
Four build/parse workers and `-j4` are configured per target; build sequentially
to limit CPU, memory and disk pressure.

## Build workflow for every target

Choose one shell; the prompt identifies the selected target:

```sh
./edf shell zc702
# Or: ./edf shell zcu111
# Or: ./edf shell mpfs-disco-kit
```

Inside that shell, the same command sequence applies:

```sh
edf-build check    # dependency-planning dry run, not compilation
edf-build boot
edf-build linux
edf-build sdk      # optional, separate SDK build
edf-build export
```

For AMD, complete both `boot` and `linux` before QEMU or export. For the Discovery
Kit, `linux` includes the U-Boot/payload dependencies, so the separate `boot` step
is optional. `boot` alone never produces the complete Linux SD image.

Equivalent host commands, shown for all targets:

```sh
# ZC702 / ARM32
./edf boot zc702
./edf linux zc702
./edf sdk zc702       # optional
./edf export zc702

# ZCU111 / ARM64
./edf boot zcu111
./edf linux zcu111
./edf sdk zcu111      # optional
./edf export zcu111

# Discovery Kit / RISC-V 64-bit
./edf boot mpfs-disco-kit    # optional before linux
./edf linux mpfs-disco-kit
./edf sdk mpfs-disco-kit    # optional
./edf export mpfs-disco-kit
```

`edf-build` initializes Yocto in a child process; it does not initialize the parent
shell for direct BitBake commands. To invoke BitBake manually, initialize explicitly:

```sh
# Inside ./edf shell mpfs-disco-kit:
source /opt/edf-scripts/yocto-env.sh
bitbake -C compile u-boot-mchp     # force U-Boot recompilation
```

Then run `edf-build linux` and `edf-build export` to update and collect the SD
image. Microchip's `payload.bin` contains U-Boot for HSS; it is **not board HSS
firmware**. Install a compatible Discovery Kit FPGA reference design and HSS
separately using Microchip's tools. These commands do not run Vivado/Libero or
program FPGA hardware. Use a fresh shell for SDK application development; do not
mix a sourced SDK environment with BitBake.

## Configuration, QEMU and logs

Kernel and RootFS configuration are available for every supported target. On macOS:

```sh
target=mpfs-disco-kit    # or zc702 / zcu111
./edf kernel-menuconfig "$target"
./edf kernel-saveconfig "$target"
./edf rootfs-menuconfig "$target"
./edf linux "$target"
```

Inside the selected target shell, the equivalent commands are:

```sh
edf-build kernel-menuconfig
edf-build kernel-saveconfig
edf-build rootfs-menuconfig
edf-build linux
```

Kernel configuration uses Kconfig in tmux. Save/exit, then `kernel-saveconfig`
preserves a target-specific fragment. RootFS configuration is the project's
package/image-feature editor, not PetaLinux's full catalog. Both save under the
selected build directory's `conf/`. SDK generation remains a separate step.

QEMU is implemented only for the AMD targets:

```sh
./edf qemu-prepare zc702    # or zcu111; stage only
./edf qemu zc702            # or zcu111; stage and launch
# Inside the matching target shell: edf-build qemu
```

The helper merges firmware/Linux QEMU settings and inserts `boot.bin` into a
separate SD image copy. It leaves deploy inputs unchanged and uses snapshot mode
to discard guest writes. Exit with **Ctrl+A, then X**. SLIRP networking needs no
privileged container; no guest SSH port is published to macOS. QEMU does not
validate RF converters, PL logic or physical-board initialization.

| Log | Location |
| --- | --- |
| Host `boot`, `linux`, `sdk`, `check`, `export` | `validation/<target>-<command>.log`, overwritten on rerun |
| Source sync | `validation/<target>-source-sync.log` |
| Interactive commands | `artifacts/logs/<target>/`, unique terminal transcripts |
| Individual Yocto tasks | Selected build tree, under `tmp/work/.../temp/` |
| QEMU console | Selected build tree's `qemu-console.log` |

For host `./edf boot|linux|sdk|check|export`, Ctrl+C stops/removes that invocation's
container, allowing up to 20 seconds before forced termination. Wait for the
launcher to return before restarting the same target. A canceled command exits
130; other target containers and persistent data remain. Rerun to resume.

Inside an interactive shell, Ctrl+C reaches the foreground command. BitBake can
wait for active tasks before returning to the prompt; this does not use the
host launcher's 20-second stop policy. Use `exit` to leave the shell. Ctrl+C in
`tail -f` or `docker stats` only stops monitoring. Helpers take per-target locks;
direct BitBake commands bypass them.

## Exported artifacts

Run `./edf export TARGET` or `edf-build export` after the required builds. Export
collects existing results; it does not build recipes or flash a device. It takes
the target lock, so finish any manual BitBake work first.

Exports are published atomically into `artifacts/<target>/<UTC-timestamp>-<id>/`.
Existing exports are not overwritten. The table lists export names, which may
differ from upstream deployment filenames.

| Artifact | ZC702 / ARM32 | ZCU111 / ARM64 | Discovery Kit / RISC-V 64-bit |
| --- | --- | --- | --- |
| Complete SD disk image | `sdcard.wic.xz` | `sdcard.wic.xz` | `sdcard.wic.gz` |
| Boot payload | `boot.bin` | `boot.bin` | `payload.bin`, `boot.scr`; optional U-Boot files and `uboot.env` when present |
| Kernel / device tree | `uImage`, `system.dtb` | `Image`, `system.dtb` | `fitImage`; standalone `mpfs-disco-kit.dtb` when present |
| Root filesystem archive | `rootfs.tar.gz` | `rootfs.tar.gz` | `rootfs.tar.gz` |
| Block map | `sdcard.wic.bmap` | `sdcard.wic.bmap` | `sdcard.wic.bmap` |
| Partition listing | `partitions.txt` | `partitions.txt` | Not separately exported |
| Metadata / checksums | `packages.manifest`, `source-manifest.xml`, `build-info.json`, `README.txt`, `SHA256SUMS` | Same | Same |
| Optional SDK | Matching files in `sdk/` | Matching files in `sdk/` | Matching files in `sdk/` |

AMD export stages a copy of the Linux WIC, inserts this board's `boot.bin` into
FAT partition 1, reads it back for verification, regenerates the block map and
compresses with xz. Microchip export preserves the vendor WIC layout (FAT boot,
raw HSS payload, ext4 rootfs), regenerates the block map and compresses with gzip.
Both check that the original WIC is unchanged. Microchip does not receive AMD
`boot.bin` insertion.

Verify files from the export directory on macOS:

```sh
shasum -a 256 -c SHA256SUMS
```

The WIC is a whole-disk SD image; `rootfs.tar.gz` is only a filesystem archive.
For a raw-image writer, decompress with `xz -dk sdcard.wic.xz` (AMD) or
`gzip -dk sdcard.wic.gz` (Microchip), then write the raw WIC to the entire card.
Linux `bmaptool` can use the compressed image and matching block map. Writing
overwrites the card; physical boot is a separate validation step.

Allow room for collected files and compressed output, plus an AMD raw staging
copy. Source manifests record checkout revisions at export, not proof that those
revisions built every artifact. SDK files are collected if present but are not
rebuilt or certified current against a later rootfs. Export supports the default
image recipes above; custom images need explicit integration.

## Reset downloads, caches or all generated data

These commands delete data. Stop this project's containers first, including
interactive shells and QEMU. No cleanup is performed merely by reading this guide.

```sh
cd /Volumes/Zeus/workspace/edf-dev
for id in $(docker --context orbstack ps -aq --filter label=com.docker.compose.project=edf-dev); do
  docker --context orbstack stop -t 20 "$id"
  docker --context orbstack rm "$id"
done
docker --context orbstack compose down --remove-orphans
```

To delete **only downloads and sstate**, shared by all architectures:

```sh
for volume in edf-dev_downloads edf-dev_sstate-cache; do
  if docker --context orbstack volume inspect "$volume" >/dev/null 2>&1; then
    docker --context orbstack volume rm "$volume"
  fi
done
```

Existing source checkouts and build trees can still avoid compilation. For a
**full reset of all three targets**, also run:

```sh
for volume in edf-dev_workspace edf-dev_microchip-workspace; do
  if docker --context orbstack volume inspect "$volume" >/dev/null 2>&1; then
    docker --context orbstack volume rm "$volume"
  fi
done
if docker --context orbstack image inspect edf-dev:ubuntu2204-26.06.1 >/dev/null 2>&1; then
  docker --context orbstack image rm edf-dev:ubuntu2204-26.06.1
fi
rm -rf ./artifacts ./validation
mkdir -p artifacts validation
```

This removes sources, all build trees and saved build configuration, SDKs, staged
QEMU disks, exports and logs. Preserve wanted changes outside those locations.
Tracked project files, tests and `hardware/` inputs are retained. The separate
`edf-dev-recovery-20261005` directory is not touched by these commands.

Then repeat setup and sync for the vendors you need. To rebuild the host image
without Docker layer reuse, run the no-cache command in maintenance below.
Avoid global Docker pruning, which can affect unrelated projects. The legacy
`scripts/clean-validate.py` launches a separate automatic ZC702 validation run;
it is not the manual reset procedure for this three-target environment.

## Future custom layer and bitstream integration

This section describes future AMD/Arty work. The general layer workflow also
applies to Microchip, but the EDF image and XSA/bitstream examples are AMD-specific.
This section describes future work. The layer mount, custom image, Arty target,
and PL firmware recipes are not currently implemented. Apply these steps after
active builds finish; adding this documentation does not change the build.

### Keep custom source outside disposable volumes

Store your layer on the Mac and keep it in Git:

```text
/Volumes/Zeus/workspace/edf-dev/layers/meta-myproject/
├── conf/layer.conf
├── conf/machine/
├── recipes-apps/
├── recipes-bsp/
├── recipes-kernel/
└── recipes-core/images/
```

Later, create the host `layers/` directory and add this bind mount to the shared
`x-common.volumes` list in `compose.yaml`:

```yaml
- ./layers:/layers
```

The writable mount permits layer creation from the container. The layer then
survives workspace/cache volume deletion. New containers pick up the mount.
Once mounted, enter a target shell and initialize its build environment:

```sh
./edf shell zc702
# Inside the container:
source /opt/edf-scripts/yocto-env.sh
bitbake-layers create-layer /layers/meta-myproject
bitbake-layers add-layer /layers/meta-myproject
bitbake-layers show-layers
```

Create the layer only once. Repeat initialization and `add-layer` for each other
target that needs it, including ZCU111 or Discovery Kit; each build directory owns a separate
`conf/bblayers.conf`. A full workspace reset requires registering the preserved
layer again. Board-specific recipes and configuration must be scoped to the
appropriate machine rather than applied to every target using the layer.

### Add applications and configuration

Use application recipes, kernel configuration fragments, device-tree additions,
and bootloader recipe extensions in your layer. For a custom EDF image, create
`recipes-core/images/myproject-image.bb` with, for example:

```bitbake
require recipes-extended/images/edf-linux-disk-image.bb

IMAGE_INSTALL:append = " my-application"
```

`my-application` is a placeholder for a package provided by your own recipe.
From the initialized target shell, build with:

```sh
MACHINE="$LINUX_MACHINE" bitbake myproject-image
```

The current `./edf linux` wrapper selects the target image from `config/targets.sh`:
`edf-linux-disk-image` for AMD or `mchp-base-image` for Microchip.
Selecting a custom image through the wrapper requires a later change, as does
teaching the QEMU preparation helper to locate that image's deploy filenames.
Do not assume the current QEMU command selects `myproject-image` automatically.

### Import the Arty hardware design

Use your `arty-z7-20-2021.2` project as the hardware/software reference. The
intended modern handoff is:

```text
Vivado design → XSA → SDTGen → gen-machine-conf
                                  ↓
                     Dedicated Arty machine and device tree
```

Keep the XSA, bitstream and generated device-tree inputs tied to the same design
revision. The XSA describes the hardware; the bitstream programs the PL. Modern
tool compatibility of the old XSA must be checked, and a fresh export may be
needed. Register the generated BSP layer as required and retain its source and
hardware inputs outside disposable volumes.

Add a unique Arty target to `config/targets.sh` and the launcher's allowlist,
using its own board machine and build directory. The Zynq-7000 common Linux
machine can remain `amd-cortexa9thf-neon-common`. Do not use ZC702 firmware as the
final Arty board firmware: DDR, clocks, MIO and peripheral configuration must
match the Arty even for PS-only operation. Share downloads and compatible sstate
with the reference targets, but keep target build directories separate.

### Choose when the PL bitstream loads

| Approach | Integration |
| --- | --- |
| During boot | Include the bitstream in the board's boot flow with matching firmware and device tree. For Zynq-7000, this can mean a bitstream partition in `BOOT.BIN` loaded by the FSBL. |
| After Linux starts | Package the bitstream and matching device-tree overlay into the root filesystem, then load them through Linux FPGA management. Package installation alone does not load the hardware. |

For boot-time loading, configure the generated machine/boot-image recipes for
the matching bitstream and rebuild board firmware. Copying a `.bit` file into
the workspace alone does not add it to `BOOT.BIN`.

For Linux loading, AMD's `dfx_user_dts` recipe class supports packaging firmware
and device-tree overlays, including full flat designs as well as DFX designs.
A dedicated firmware recipe in your layer should supply the matching payload and
overlay, use the appropriate machine compatibility, and be included in your
custom image. Follow the release-specific class guidance for bitstream conversion
and packaging; file formats and loading details depend on the device family.

First establish PS-only Arty boot, then add the PL firmware and device-tree
nodes describing its peripherals. Exclude old PL-dependent device-tree references
from the PS-only configuration. Migrate application recipes as their hardware
dependencies become available. Validate on the physical board; QEMU does not
validate the custom PL implementation.

References:

- [EDF 26.06.1 machine generation](https://edf.docs.amd.com/en/v26.06.1/shel/running-gen-machine-conf.html)
- [AMD firmware and overlay recipe class, rel-v2026.1](https://github.com/Xilinx/meta-xilinx/blob/rel-v2026.1/meta-xilinx-core/classes-recipe/dfx_user_dts.bbclass)
- [Your Arty Z7-20 2021.2 reference project](https://github.com/rklinkhammer/arty-z7-20-2021.2)

## Container provenance and maintenance

- The Dockerfile pins the Ubuntu base by digest.
- Packages come from Ubuntu's signed repositories, including security updates.
  No pip-installed dependencies or downloaded shell installers are used.
- The build account is UID/GID 1000. No sudo, SSH daemon or VNC server is installed.
  The interactive/build service drops Linux capabilities, enables
  `no-new-privileges`, and has no Docker socket mount.
- The short root initialization service has only CHOWN capability and changes
  ownership of the four volume roots.
- `artifacts/container-packages.tsv` records installed package versions;
  `artifacts/container-image.json` records the local image identity.
- AMD sync writes `artifacts/manifest-26.06.1.xml` and `artifacts/repo-version.txt`.
- Microchip sync writes `artifacts/manifest-microchip-2026.04.xml` and
  `artifacts/repo-version-microchip.txt`.

APT package versions are resolved at build time, so this is **not a byte-for-byte
reproducible image build**. A package inventory is not an SBOM or a vulnerability
scan. Rebuilding without cache refreshes the package indexes and security updates:

```sh
docker --context orbstack compose build --pull --no-cache shell
./edf build-container  # refresh recorded package inventory/image identity
./edf validate
```

Review and update the base digest deliberately for newer base images. Pinning
provenance does not by itself establish absence of vulnerabilities. This setup
has not undergone a vulnerability scan or a complete software-supply-chain audit.

## References

- [AMD EDF build-host package requirements](https://edf.docs.amd.com/en/v26.06.1/osdev/build-edf-yocto-with-the-edf-build-container.html)
- [EDF 26.06.1 platform/recipe matrix](https://edf.docs.amd.com/en/v26.06.1/ref/common-specifications.html)
- [Release source manifest](https://github.com/Xilinx/yocto-manifests/blob/amd-edf-rel-v26.06.1/default-edf.xml)


- [Microchip setup instructions](https://github.com/linux4microchip/meta-mchp/blob/linux4microchip-2026.04/meta-mchp-common/README.md)
- [Discovery Kit machine](https://github.com/linux4microchip/meta-mchp/blob/linux4microchip-2026.04/meta-mchp-polarfire-soc/meta-mchp-polarfire-soc-bsp/conf/machine/mpfs-disco-kit.conf)
- [Discovery Kit reference design](https://github.com/polarfire-soc/polarfire-soc-discovery-kit-reference-design)

## Validation scope

The restored environment passed container/filesystem smoke checks. The consistency
update passed 11 tests plus interactive routing/configuration/cancellation checks
for all targets. Dispatch tests use mocked upstream initialization and BitBake;
they do not certify real recipe builds. Upstream
QEMU regression tests require a synced AMD checkout and were skipped during
recovery. Earlier source-sync and dry-run results predate that recovery. Full
board image/SDK builds and physical boot have not been revalidated in the restored
environment. Capability tables describe implemented commands, not hardware certification.
