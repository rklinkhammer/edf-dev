# EDF development environment

Docker-based AMD EDF/Yocto builds with direct BitBake access, local hash-server
storage, and Linux/macOS Docker-context support.

- **[Build guide](docs/build.md):** setup, complete DMOTOR/Arty builds, software-only
  iteration, hardware bundles, SDK, direct BitBake and kernel menuconfig.
- [Arty board operation](docs/arty.md): FPGA Manager, access modes and board checks.
- [DMOTOR source](https://github.com/rklinkhammer/dmotor): controller, board sources,
  driver/runtime and maintenance application.

`external/dmotor` is the pinned product source. `EDF_DMOTOR_SOURCE` selects a local
working checkout for **both** FPGA and software builds. See the build guide before
using a development override or changing the hardware bundle.
