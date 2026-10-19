

bitbake -c menuconfig virtual/kernel
bitbake -c diffconfig virtual/kernel
bitbake -f -c compile virtual/kernel
./edf --target arty-z7-20 bitbake -c clean virtual/kernel
./edf --target arty-z7-20 bitbake virtual/kernel

sudo fpgautil \
  -b /lib/firmware/xilinx/dvrmc-firmware/dvrmc-firmware.bin \
  -o /lib/firmware/xilinx/dvrmc-firmware/dvrmc-firmware.dtbo

cat /sys/class/fpga_manager/fpga0/state
cat /usr/share/dmotor/source-version.json
sudo modprobe dmotor_access
ls -l /dev/dmotor0


dmotor-semantic-tests
dmotor-protocol-tests
dmotor-linux-tests
dmotor-runtime-tests

sudo dmotord --externally-inhibited \
  /dev/dmotor0 /usr/share/dmotor/inhibited-example.conf

sudo dmotor-maint


# DVRMC’s board design now lives inside DMOTOR:
# - Block design: dmotor/platforms/arty-z7-20/vivado/design_1.bd
# - Authoritative constraints: dmotor/platforms/arty-z7-20/constraints/arty-z7-20.xdc
# - Project creation: dmotor/platforms/arty-z7-20/vivado/create.tcl
# The build recreates the Vivado project under dmotor/build/product/vivado, using the freshly packaged DMOTOR IP. EDF then builds the bitstream, generates the matched device-tree inputs, and packages them for Linux FPGA Manager.
# ~/workspace/dvrmc is retained as historical reference. The default workflow no longer reads it, so edits there will not affect subsequent builds.
# For GUI changes, open the generated Vivado project and save the reviewed block-design changes back to the authoritative source in platforms/arty-z7-20. Edit the authoritative XDC directly. Treat build/product/vivado as disposable output.
# EDF therefore needs only its DMOTOR submodule—no separate DVRMC submodule.