# EDF development: Scarthgap, NFS and local builds

This replacement lives alongside the original EDF environment. It uses a separate
Compose project `edf-dev-next`, image, local build volume and hash-server volume.
AMD EDF 26.06.1 sources are baked into the image using the checked-in upstream
manifest and exact manifest commit. Changing sources requires rebuilding the image.

## BitBake first

Run as your normal user. Docker Engine, Compose, Bash, and host Python 3 are
required. Build the container once, then use ordinary BitBake arguments:

```sh
./edf build-container
./edf                                      # bitbake edf-linux-disk-image
./edf edf-linux-disk-image                  # same, explicit recipe
./edf bitbake -n edf-linux-disk-image
./edf bitbake -c compile linux-xlnx
./edf bitbake -c populate_sdk edf-linux-disk-image
./edf bitbake --help                        # BitBake's help
./edf --target zcu111 bitbake -e edf-linux-disk-image
./edf --target zc702 --machine board bitbake xilinx-bootbin
./edf --target zcu111 --machine board shell
```

`--target` selects the board configuration and persistent build directory.
`--machine linux` (default) selects that target's common CPU-family Linux machine;
`--machine board` selects its firmware machine. An explicit Yocto MACHINE name is
also accepted. It must be provided by the configured layers; BitBake reports
unsupported machines. Machine selection applies to direct BitBake commands and
the initialized shell. With no BitBake arguments, the default recipe remains
`edf-linux-disk-image`; specify `xilinx-bootbin` for firmware builds.

Launcher options must precede the command. After `bitbake`, arguments are passed
unchanged, including options, multiple recipes, and paths containing spaces.
Use `./edf bitbake <recipe>` or `./edf -- <recipe>` to bypass a convenience-command
name collision. `./edf --help` describes the launcher. The shell has BitBake and
its environment initialized and holds the target lock until you exit.

## Higher-level commands

```sh
./edf --target zc702 image       # board firmware, then Linux image
./edf --target zc702 boot        # board firmware only
./edf --target zc702 linux       # Linux image only
./edf --target zc702 sdk         # standard image SDK
./edf --target zc702 check       # dry-run firmware and Linux dependencies
./edf --target zc702 export
./edf --target zcu111 qemu
./edf validate
```

These commands keep their established board/Linux mappings; `--machine` does not
change them. **Migration:** bare `./edf` now builds only the Linux image. Use
`./edf image` when you want the previous combined firmware-plus-Linux workflow.

All noninteractive builds, including direct BitBake calls, keep the supervisor's
cancellation, log capture, and exit-status propagation. A failed firmware command
stops `image` before Linux builds. Target locks, exports, and QEMU behavior are
preserved. No flashing occurs.

Builds stream directly from an attached container. In a terminal, BitBake shows
its live parsing percentages and task display. Redirected output uses BitBake's
normal plain-text mode. The same output is saved under `artifacts/logs/<target>/`
(terminal logs include carriage returns and ANSI formatting). Ctrl+C stops the
current build, and the launcher returns its exit status. A cold recipe cache can
take several minutes to parse.

## Docker context and macOS

On macOS, the launcher defaults to `orbstack`. On Linux, it defaults to Docker's
active context. Override either:

```sh
./edf --context orbstack bitbake -n edf-linux-disk-image
EDF_DOCKER_CONTEXT=default ./edf bitbake --version
```

Precedence is `--context`, then `EDF_DOCKER_CONTEXT`, then Docker's own
`DOCKER_CONTEXT`/`DOCKER_HOST` environment, then the platform default. Set
`EDF_DOCKER_CONTEXT=''` to use Docker's active context on macOS. Context selection
is exported to path resolution, service startup, the build supervisor, and cleanup.
Set this in your shell environment, not Compose's `.env` file. OrbStack must
already be installed/running and its context available. The launcher uses
Bash 3.2-compatible syntax; source builds run as linux/amd64 on Apple Silicon.

## Architecture compared with jetson-yocto-qdma

Both projects bake pinned sources into an image, adopt the invoking user's
numeric identity, configure Yocto inside the container, and share a local
Unix-socket hash server. Both now center their CLI on BitBake, with target-specific
image recipes as defaults.

| Concern | jetson-yocto-qdma | edf-dev |
| --- | --- | --- |
| Direct interface | `./yocto <BitBake arguments>` | `./edf [bitbake] <BitBake arguments>` |
| Machine selection | `MACHINE` environment variable | `--target` plus `--machine linux/board/name` |
| Build storage | Host project bind mount | Local Linux volume; NFS-capable cache/artifact binds |
| Workflow additions | Single image recipe | Optional firmware/image, SDK, export, and QEMU helpers |
| Process handling | Attached Compose run | Supervised builds with logs and cancellation |

EDF retains local Linux build storage because macOS file sharing and NFS are
unsuitable for its mutable build tree. Its board firmware and Linux image use
different MACHINE values, so a target mapping remains useful even with direct
BitBake access. There is no need to copy Jetson's host-bound build tree to expose
the same BitBake interface.

## Identity and storage

The launcher supplies UID, primary GID and supplementary groups. A short root
entrypoint creates an account, initializes local volume ownership, and drops to
that identity before building. It never recursively chowns project or cache trees.
NFS access requires matching server permissions/ACLs; root squash can stay enabled.

Set mount paths in `.env` (absolute paths on the Docker host):

```dotenv
EDF_DOWNLOADS=/mnt/nfs/yocto/downloads
EDF_SSTATE=/mnt/nfs/yocto/sstate-cache
EDF_ARTIFACTS=/mnt/nfs/edf/artifacts
# Optional pre-created local Linux directory instead of named build volume:
# EDF_BUILD_ROOT=/var/lib/edf/builds
```

The project and custom layer may themselves reside on NFS. Pre-create shared
paths with appropriate permissions. Builds and TMPDIR stay on local Linux storage;
the preflight rejects NFS and macOS-shared build storage. Downloads and sstate
are reusable across hosts. Each host has independent mutable build trees/locks.

Hashserv starts automatically and must pass a health check. Its Scarthgap BitBake
server listens on `/hashserv/hashserv.sock`; only it opens the SQLite database.
The database and socket stay in `edf-dev-next_hashserv`, on local Docker storage.
No TCP port is published. OEEquivHash is enabled; upstream hash services and remote
sstate mirrors are disabled. Use one invoking user per local build/hashserv volume;
finish builds before switching accounts. Existing files owned by another user
require administrator-managed groups/ACLs; there is no recursive ownership repair.

`./edf stop` stops services without removing volumes. Never use `down -v` unless
you intend to delete the replacement's local build and hash database state.

## Configuration and targets

Generated local.conf/bblayers.conf are reconciled on each command. Unchanged
files retain their timestamps so BitBake can reuse its parse cache. Edit
`config/build-policy.inc`, `config/targets/<target>.conf`, or `meta-edf-dev/`.
Target machine/recipe mappings live in `config/targets/<target>.sh`; the launcher
uses these definitions to validate selectors.
Vendor templates are retained so EDF defaults and layer dependencies remain intact;
our policy is loaded afterward. The layer declares Scarthgap compatibility.
Builds default to four container CPUs, 12 GiB RAM, two BitBake workers and `-j4`.
Finish active builds before editing scripts, shared policy or layer files.

ZC702 and ZCU111 retain their distinct firmware machines and CPU-family image
machines. Exports retain machine matching, firmware insertion into a copied WIC,
read-back, hashes and timestamped publication. Original WIC files are unchanged.
QEMU runs with user-mode networking and a disposable snapshot.

Arty Z7-20 is recognized but requires its actual generated custom-board machine
configuration; see [Arty inputs](docs/arty.md). It never borrows ZC702 firmware.
PolarFire remains supported by the original checkout, not this AMD replacement.
See [migration](docs/migration.md) before retiring the original environment.

## Verification

Run the standard Python unittest suite as your normal user. The real Docker
cancellation test is opt-in with `EDF_RUNTIME_TEST=1`; it creates and removes
its own temporary Compose project. Set `QEMUBOOT_TOOL` to the release's
`meta-xilinx-core/scripts/qemuboot-tool` to enable the upstream merge tests.
`tests/test_bitbake_cli.py` checks default/direct dispatch, argument boundaries,
exit propagation, convenience mappings, and simulated Linux/macOS context selection.
`tests/runtime/configuration.sh` checks effective firmware/Linux machine selection
and hash/storage policy inside the built container.

`check` is a dependency dry run, not compilation or hardware certification.
Actual NFS access is tested only when your chosen NFS directories are mounted.
