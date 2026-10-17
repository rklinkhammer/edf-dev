# Encoder utility platform validation — 2026-10-17 UTC

Export: `artifacts/arty-z7-20/20261017T033255Z-0b4f36f6/`.
Hardware run: `artifacts/arty-hardware/20261017T030437Z-a3444ef7/`.

- DMOTOR software 0.5.0, commit `14390a1b486306cebdbc26bebdd889fd7d7c73cd`, dirty development snapshot.
- Source SHA256: `cc6ff659d6afc90a1e5ba6ab23bbe177e19711ac16b0f07901a92a736769e757`.
- Input bitstream SHA256: `3c8ff4dc5a066255f3194cf91e2eff424b1e1c8ecb91841aa115386dab967f82`.
- Exported controller IP revision 6, measured `rpm400_verified` engine, 20 MHz controller.
- DVRMC upgraded in isolated `../dvrmc/build/rpm400-integration/dvrmc.xpr`; original project not saved.
- Routed timing: setup +2.783 ns, hold +0.012 ns; no failing endpoints.
- DRC: zero errors/critical warnings; 40 DSP pipeline warnings.
- Routed I/O report confirms PULLDOWN on U19, W18, W16, V12 fault inputs.
- Native software 3/3 passed with UBSan; full AXI/HLS XSim passed including disabled/unconfigured forward/reverse encoder capture and reset cleanup.
- ARM QEMU semantic, protocol and Linux tests passed in `do_semantics`.
- Boot build: 2898 tasks successful/reused. Linux build: 9144 tasks successful/reused.
- Export SHA256SUMS passed. Actual rootfs inspected: ARM ELF `usr/bin/dmotor-encoder`, version 0.5.0 and expected fingerprint, FPGA firmware present. Exported hardware identity equals the imported bundle.

Rebuild with `EDF_DMOTOR_SOURCE=../dmotor ./edf --target arty-z7-20 image`;
then use the same override with `export`. The pinned submodule was not changed;
omitting the override stages the older software. No SDK rebuild was requested;
any SDK copied by the exporter is a pre-existing artifact.

No SD card was flashed and no physical-board result is claimed for this image.
After boot and the usual FPGA Manager load, disconnect motor drive power, verify
encoder signal voltage compatibility and run:

```sh
sudo dmotor-encoder --externally-inhibited 0
```

Controller must be disabled and unconfigured. Turn a shaft manually; check its
channel changes and direction reverses. Ctrl-C restores core reset. This utility
never enables motion. See `../dmotor/software/README.md` for limitations and the
encoder ratio check (1560 counts/output revolution for the provisional 13×30×4
encoder).
