# Migration and rollback

The original `/Volumes/Zeus/workspace/edf-dev` checkout, image and four volumes
remain intact. This replacement uses a distinct Compose project and volumes.
Do not copy live TMPDIRs or live hash databases. Cache reuse is optional and must
be explicitly selected through mount paths. No cleanup or flash operation is automated.

Before adopting this replacement:
1. Validate identity, mounts and hashserv; test socket requests and restart persistence.
2. Run both AMD targets through dry-run, image/SDK build, verified export and QEMU.
3. Test Ctrl+C and confirm the per-target lock is available afterward.
4. Supply and validate the actual Arty machine/hardware inputs, then test physical boot.
5. Port PolarFire with its own pinned vendor image/adapter before retiring its old flow.

The old custom rootfs/config menus and mutable source synchronization are removed in this
checkout. Persistent customization belongs in checked-in configuration and layer
files. The initialized shell supports BitBake menuconfig and diffconfig directly;
copy resulting fragments into the custom layer rather than generated build conf.

Rollback means returning to the original checkout; no volume restoration is needed.
