dmotor-semantic-tests
dmotor-protocol-tests
dmotor-linux-tests
sudo fpgautil \
  -b /lib/firmware/xilinx/dvrmc-firmware/dvrmc-firmware.bin \
  -o /lib/firmware/xilinx/dvrmc-firmware/dvrmc-firmware.dtbo
cat /sys/class/fpga_manager/fpga0/state
ls -l /dev/uio*
for d in /sys/class/uio/uio*; do
    [ -d "$d" ] && echo "$d: $(cat "$d/name")"
done
sudo dmotor-inspect --externally-inhibited 0
sudo dmotor-encoder --externally-inhibited 0

bitbake -c menuconfig virtual/kernel
bitbake -c diffconfig virtual/kernel
bitbake -f -c compile virtual/kernel
./edf --target arty-z7-20 bitbake -c clean virtual/kernel
./edf --target arty-z7-20 bitbake virtual/kernel
