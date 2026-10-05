#!/bin/bash
set -eo pipefail
mode=${1:-}
if [[ $mode != _kernel ]]; then
  exec 8>/home/amd-edf/edf/.edf-sources.lock
  flock -n -s 8 || { echo "Source sync is active." >&2; exit 1; }
fi
source /opt/edf-scripts/yocto-env.sh >/dev/null
export MACHINE="$LINUX_MACHINE"
if [[ $mode != _kernel ]]; then
  exec 9>"$BUILDDIR/.edf-build.lock"
  flock -n 9 || { echo 'Another EDF configuration session is open.' >&2; exit 1; }
fi
case "$mode" in
  kernel)
    [[ -t 0 && -t 1 ]] || { echo 'Run kernel-menuconfig in an interactive terminal.' >&2; exit 1; }
    export TERM=${TERM:-xterm-256color}
    rm -f "$BUILDDIR/kernel-menuconfig.status"
    tmux new-session -s edf-kernel '/bin/bash /opt/edf-scripts/configure.sh _kernel'
    if [[ ! -f $BUILDDIR/kernel-menuconfig.status ]]; then
      echo 'Menu session detached or interrupted before completion.' >&2; exit 1
    fi
    exit "$(cat "$BUILDDIR/kernel-menuconfig.status")"
    ;;
  _kernel)
    trap 'printf "%s\n" "$?" > "$BUILDDIR/kernel-menuconfig.status"' EXIT
    printf 'OE_TERMINAL = "tmux-new-window"\n' > "$BUILDDIR/conf/edf-menu-terminal.conf"
    bitbake -R "$BUILDDIR/conf/edf-menu-terminal.conf" -c menuconfig virtual/kernel
    printf '\nTo preserve saved changes across clean builds, run ./edf kernel-saveconfig.\n'
    ;;
  save-kernel)
    bitbake -c diffconfig virtual/kernel
    bitbake-getvar -r virtual/kernel --value WORKDIR > "$BUILDDIR/kernel-workdir.txt"
    python3 /opt/edf-scripts/save-kernel.py "$BUILDDIR"
    ;;
  rootfs)
    python3 /opt/edf-scripts/rootfs-menu.py "$BUILDDIR/conf/edf-rootfs.conf"
    ;;
  *) echo 'Unknown configuration command.' >&2; exit 2 ;;
esac
