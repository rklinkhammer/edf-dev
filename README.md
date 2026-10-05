# EDF development container

Locally maintained build host for AMD EDF **26.06.1**, built from Ubuntu 22.04.
This is our Dockerfile, not a reproduction of AMD's unpublished container recipe.
Both boards use this Compose environment with separate target build directories.

## Manual fresh build: ZC702 and ZCU111

The first target is named `zc702`, not `zcu702`. Run these commands on macOS
with OrbStack running. Nothing starts automatically. For an existing workspace,
perform the full reset below first.

```sh
cd ~/workspace/edf-dev
docker --context orbstack compose build --pull --no-cache shell
./edf build-container  # record image/package inventory using the rebuilt image
./edf validate         # initialize volumes and check the host
./edf sync             # download release-pinned source repositories
```

Empty local caches alone do not prevent remote prebuilt sstate downloads.
For local compilation, run this once after sync, before either target build:

```sh
for target in zc702 zcu111; do
  EDF_TARGET="$target" docker --context orbstack compose run --rm --no-deps -T shell -ec '
    source /opt/edf-scripts/yocto-env.sh
    cat >> conf/local.conf <<"CONF"

# Manual source-build policy
SSTATE_MIRRORS = ""
BB_HASHSERVE_UPSTREAM = ""
BB_DISKMON_DIRS = "STOPTASKS,${TMPDIR},20G,100K STOPTASKS,${DL_DIR},20G,100K HALT,${TMPDIR},10G,50K"
CONF
  '
done
```

Normal source mirrors and required binary inputs (reference hardware, uninative)
remain available. Compatible tasks compiled for the first board can be reused
for the second. This does not synthesize a Vivado design.

Build sequentially to limit CPU, memory and disk pressure:

```sh
# ZC702: Cortex-A9 / ARM32
./edf boot zc702
./edf linux zc702
./edf qemu zc702
# Exit QEMU: Ctrl+A, then X before continuing.

# ZCU111: Cortex-A53 / ARM64
./edf boot zcu111
./edf linux zcu111
./edf qemu zcu111
# Exit QEMU: Ctrl+A, then X.
```

Optional SDKs are separate builds:

```sh
./edf sdk zc702
./edf sdk zcu111
```

SDK installers go to each target's `tmp/deploy/sdk/` in the workspace volume.
Their host is x86-64 Linux; their compiler target matches the board.
Build logs are `validation/<target>-<command>.log`, overwritten on subsequent
runs. Commands default to ZC702. `check` is a planning dry run, not a build.

## Interrupting and resuming builds

The host launcher requires `python3` on macOS. For `./edf boot`, `linux`, `sdk`,
and `check`, Ctrl+C now explicitly stops and removes that invocation's build
container. Docker allows up to 20 seconds to stop before forcing termination.
Wait for the launcher to return before starting another command for that target.
This also releases the target build lock; other target containers and interactive
shells are left alone. Downloads, shared state and completed build files remain
in their persistent volumes. Rerun the same command to resume incomplete work.

Output remains live in the terminal and in `validation/<target>-<command>.log`.
A canceled command exits with status 130; completed builds preserve their
container exit status. Ctrl+C in `tail -f` or `docker stats` only stops monitoring.
This cancellation behavior applies to the four build commands above, not the
interactive shell or QEMU controls. Exit QEMU with Ctrl+A, then X.

## Delete all downloads and shared-state cache

These commands delete data. First stop any automatic runners that could launch
new containers. The loop stops/removes only this Compose project's containers,
including manual shells, QEMU and SDK builds.

```sh
cd ~/workspace/edf-dev
for id in $(docker --context orbstack ps -aq --filter label=com.docker.compose.project=edf-dev); do
  docker --context orbstack stop -t 20 "$id"
  docker --context orbstack rm "$id"
done
docker --context orbstack compose down --remove-orphans
for volume in edf-dev_downloads edf-dev_sstate-cache; do
  if docker --context orbstack volume inspect "$volume" >/dev/null 2>&1; then
    docker --context orbstack volume rm "$volume"
  fi
done
```

This deletes every file in `DL_DIR` and `SSTATE_DIR`, including fetched Git
repositories and cached task archives. Source checkouts, configuration and
existing build outputs remain in the workspace volume. They can still avoid
compilation; for a completely fresh start, continue with the full reset.

## Full reset: sources, builds, caches, images and results

Run the preceding stop/cache-removal block first, then:

```sh
cd ~/workspace/edf-dev
if docker --context orbstack volume inspect edf-dev_workspace >/dev/null 2>&1; then
  docker --context orbstack volume rm edf-dev_workspace
fi
if docker --context orbstack image inspect edf-dev:ubuntu2204-26.06.1 >/dev/null 2>&1; then
  docker --context orbstack image rm edf-dev:ubuntu2204-26.06.1
fi
rm -rf ./artifacts ./validation
mkdir -p artifacts validation
```

This removes source repositories, both build trees, their saved kernel/rootfs
settings, SDKs, QEMU disks, image exports and validation logs. Preserve any desired
customizations outside these locations before a future reset. Setup source files,
scripts, test source code and user-supplied `hardware/` inputs are retained.
Follow the manual sequence above to recreate everything. `validate` initializes
the volumes and `sync` downloads the repositories again.

Docker's image-layer cache is separate from Yocto's shared-state cache.
`--no-cache` bypasses image-layer reuse; avoid global Docker pruning, which can
affect unrelated projects.

Historical automatic clean runs used separate `edf-dev-clean-<timestamp>_*`
volumes and images. Those existing run volumes/images have been removed for this
manual restart. Regular Compose reset commands cover only the `edf-dev` project.
Do not invoke `scripts/clean-validate.py` for the manual procedure: that script
starts a separate automatic ZC702 validation run with its own storage.

## Targets and shared storage

| Target | Board firmware machine | Linux image machine | Build directory inside container |
| --- | --- | --- | --- |
| `zc702` | `zynq-zc702-sdt-full` | `amd-cortexa9thf-neon-common` (ARM32) | `/home/amd-edf/edf/builds/zc702` |
| `zcu111` | `zynqmp-zcu111-sdt-full` | `amd-cortexa53-common` (ARM64) | `/home/amd-edf/edf/builds/zcu111` |

Both targets have explicit board/common-machine mappings.
To add a target, extend `config/targets.sh` and the
launcher's target allowlist with the appropriate board/common-machine mapping.
Both targets use the same EDF source release and host image.

The host container runs **linux/amd64**, using OrbStack/Rosetta on Apple Silicon.
Target architecture is selected by Yocto's MACHINE; this setup does not yet
qualify a native ARM64 host image. The multilib dependencies in the Dockerfile
are specifically for the x86-64 host.

Compose owns three persistent Linux-filesystem volumes:

- `edf-dev_workspace`: pinned source repositories and isolated target builds.
- `edf-dev_downloads`: shared fetched sources (`DL_DIR`).
- `edf-dev_sstate-cache`: shared task results (`SSTATE_DIR`).

Yocto's task signatures and architecture metadata control cache reuse. Sharing
sstate does not mean ARM32 binaries are used in an ARM64 image. Never share a
`TMPDIR` between simultaneous target builds. The wrapper uses per-target locks
and prevents source sync while wrapped builds are active. Interactive/manual
BitBake commands bypass those wrapper locks and must be coordinated manually.
Four build/parse workers and `-j4` are configured per target; concurrent targets
multiply resource use. Different EDF releases should get their own source trees.

The macOS `artifacts/` directory is `/artifacts` in the container. Export final
images explicitly from the target's `tmp/deploy/images/` into that directory.
`hardware/` is mounted read-only at `/hardware` for future custom hardware.
Container removal keeps all volumes. `docker compose down -v` deletes them.

## Interactive build workflow

Enter a shell for the desired target on your Mac:

```sh
cd ~/workspace/edf-dev
./edf shell zcu111
# Or: ./edf shell zc702
```

Then run commands inside that same container:

```sh
edf-build help
edf-build boot
edf-build linux
edf-build sdk       # optional separate SDK build
edf-build qemu      # requires completed firmware and Linux builds
```

The prompt shows the selected target. Each command initializes the required
Yocto environment in a child process; no manual environment sourcing is needed.
Existing target/source locks still apply. Use separate target shells when needed.
`edf-build check` performs dry runs; `edf-build qemu-prepare` only stages QEMU.

Ctrl+C goes to the foreground command; wait for it to finish handling the
interrupt and return to the same shell. BitBake may wait for active tasks, and a
hung compiler may still require explicit recovery. The interactive workflow does
not use the host launcher's 20-second container-stop policy. For QEMU, use Ctrl+A,
then X. Use `exit` to leave the container shell.

Console sessions are recorded under `artifacts/logs/<target>/` on the Mac, with
unique timestamped filenames. These are terminal transcripts and can contain
terminal control characters. Task-level logs remain in the target's Yocto build
tree. Commands return their exit status, so `edf-build boot && edf-build linux`
only proceeds if firmware succeeds. Builds do not start automatically on entry.

These helpers are bind-mounted, so no container-image rebuild is needed. Open a
new `./edf shell` to get the updated startup configuration. In an already-open
shell, run `source /opt/edf-scripts/shell-rc.sh` to enable the command and prompt.
Use a different fresh shell for SDK application development; do not mix a sourced
SDK environment with BitBake. Existing host-side `./edf boot|linux|sdk` commands
remain available for unattended use.

## Interactive and configuration commands

```sh
./edf shell zc702
# In that shell:
source /opt/edf-scripts/yocto-env.sh
# BOARD_MACHINE, LINUX_MACHINE and BUILDDIR now identify the selected target.
```

```sh
./edf kernel-menuconfig zc702
./edf kernel-saveconfig zc702
./edf rootfs-menuconfig zc702
./edf linux zc702
./edf sdk zc702
```

Kernel configuration uses native Kconfig in tmux. Save/exit, then use
`kernel-saveconfig` to preserve changes as a target-specific kernel fragment.
RootFS configuration is our package/image-feature editor, not PetaLinux's full
package catalog. SDK generation is separate from the Linux image build; the
SDK's default host is x86-64 Linux, with the selected target architecture.
Configuration files stay in the selected build directory's `conf/`.

## QEMU

```sh
./edf qemu-prepare zc702
./edf qemu zc702
```

Build both firmware and Linux first. The helper merges their generated QEMU
settings and inserts BOOT.BIN into a separate SD image copy. It never modifies
the deploy input images. A new staged copy is prepared each launch; snapshot
mode discards guest writes. Exit with **Ctrl+A, then X**. Console output is saved
in the target's `qemu-console.log`. SLIRP networking needs no privileged
container, and no guest SSH port is published onto macOS. QEMU tests the
processor/Linux path, not RF converters, PL behavior, or physical initialization.

## Future custom layer and bitstream integration

This section describes future work. The layer mount, custom image, Arty target,
and PL firmware recipes are not currently implemented. Apply these steps after
active builds finish; adding this documentation does not change the build.

### Keep custom source outside disposable volumes

Store your layer on the Mac and keep it in Git:

```text
~/workspace/edf-dev/layers/meta-myproject/
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
target that needs it, including ZCU111; each build directory owns a separate
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

The current `./edf linux` wrapper explicitly builds `edf-linux-disk-image`.
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
  ownership of the three volume roots.
- `artifacts/container-packages.tsv` records installed package versions;
  `artifacts/container-image.json` records the local image identity.
- `artifacts/manifest-26.06.1.xml` records the exact source revisions.
- `artifacts/repo-version.txt` records the source-sync tool version and revision.

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

