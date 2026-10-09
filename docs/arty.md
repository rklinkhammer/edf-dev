# Arty Z7-20 inputs

The original repository has no Arty machine or hardware inputs. This replacement
recognizes `--target arty-z7-20` but refuses a build until the real board machine
exists at `meta-edf-dev/conf/machine/arty-z7-20.conf`.

Use AMD EDF 26.06.1's custom-board/SDT machine generation flow with the Arty Z7-20
Vivado hardware design. Check the generated machine configuration and its includes
into meta-edf-dev, and place referenced hardware under hardware/arty-z7-20.
Use container-visible paths (`/hardware/arty-z7-20/...`). Verify CPU, DDR, UART,
SD controller, boot addresses and board device tree against the actual design.
PS-only is the initial scope; matching bitstream inputs are required before adding PL.

The target uses its own firmware machine and the Cortex-A9 EDF Linux image.
Parsing, firmware/image compilation, export inspection and physical SD boot are
separate acceptance steps. QEMU is disabled for Arty until separately qualified.
No fabricated machine config or ZC702 firmware is supplied.

## Inspected legacy hardware baseline

Repository: https://github.com/rklinkhammer/dvrz.git
Inspected commit: `1079252b6ec1d493b6ffdbf6fdd50e59788761d0`.
The project is Vivado 2023.2, part `xc7z020clg400-1`.
`dvrz_wrapper.xsa` contains the HWH, PS initialization code and
`dvrz_wrapper.bit`; it also contains custom PL driver inputs.

The checked-in PS configuration enables Ethernet 0 on MIO 16–27, SD0 on
MIO 40–45 and UART1 on MIO 48–49. DDR high address is `0x3FFFFFFF`; verify
the DDR configuration against physical hardware when regenerating the design.
These are observations of the legacy project, not EDF qualification.

The repository is sufficient as the design reference. When its EDF conversion
is ready, generate the matching SDT and machine configuration, record the new
commit and input hashes, and install those inputs in the paths above.
No additional legacy files are needed to finish the container infrastructure.
