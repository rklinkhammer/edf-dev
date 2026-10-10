# EDF development: Scarthgap, NFS and local builds

This replacement lives alongside the original EDF environment. It uses a separate
Compose project `edf-dev-next`, image, local build volume and hash-server volume.
AMD EDF 26.06.1 sources are baked into the image using the checked-in upstream
manifest and exact manifest commit. Changing sources requires rebuilding the image.

## Build

Run as your normal user. Docker Engine + Compose are required. On this Mac:

```sh
export EDF_DOCKER_CONTEXT=orbstack
./edf build-container
./edf validate
./edf --target zc702 check
./edf --target zc702 image
./edf --target zc702 export
./edf --target zcu111 image
./edf --target zcu111 qemu
./edf --target zcu111 sdk
./edf --target zcu111 shell
./edf --target zcu111 -n edf-linux-disk-image
```

`image` builds board firmware followed by the common CPU-family Linux image.
`boot` and `linux` remain independently available. Extra arguments go to BitBake
for the selected Linux machine. The initialized shell holds the target lock;
exit it before running another command for that target. A small supervisor stops its own build container on Ctrl+C, records output
and returns the container exit status. No flashing occurs.

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
`tests/runtime/configuration.sh` checks effective firmware/Linux machine selection
and hash/storage policy inside the built container.

`check` is a dependency dry run, not compilation or hardware certification.
Actual NFS access is tested only when your chosen NFS directories are mounted.
