#!/bin/sh
# Board-side checks; load the matching FPGA overlay first (docs/arty.md).
# Run software tests separately from the maintenance application.
set -eu
case "${1:-}" in
  software)
    dmotor-semantic-tests
    dmotor-protocol-tests
    dmotor-linux-tests
    dmotor-runtime-tests
    ;;
  production)
    cat /sys/class/fpga_manager/fpga0/state
    cat /usr/share/dmotor/source-version.json
    sudo modprobe dmotor_access
    ls -l /dev/dmotor0
    printf '%s\n' 'Next: follow dmotor/software/linux/output-validation.md with drive power disconnected.'
    ;;
  inspection)
    cat /sys/class/fpga_manager/fpga0/state
    for d in /sys/class/uio/uio*; do
      [ -d "$d" ] && printf '%s: %s\n' "$d" "$(cat "$d/name")"
    done
    printf '%s\n' 'Confirm dmotor-inspection index, externally inhibit drive, then use dmotor-inspect/encoder.'
    ;;
  *) echo "Usage: sh docs/tests.sh software|production|inspection" >&2; exit 2 ;;
esac
