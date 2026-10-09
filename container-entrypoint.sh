#!/bin/bash
set -euo pipefail
: "${HOST_UID:?Run the build with ./edf to supply your host identity}"
: "${HOST_GID:?Run the build with ./edf to supply your host identity}"
[[ $HOST_UID =~ ^[0-9]+$ && $HOST_GID =~ ^[0-9]+$ && $HOST_UID != 0 ]] || {
    echo 'HOST_UID must be non-root and HOST_GID must be numeric.' >&2; exit 1;
}
HOST_GROUPS=${HOST_GROUPS:-$HOST_GID}
[[ $HOST_GROUPS =~ ^[0-9]+(,[0-9]+)*$ ]] || { echo 'Invalid HOST_GROUPS' >&2; exit 1; }
# Supply a passwd entry for tools that resolve the build user's name.
getent group "$HOST_GID" >/dev/null || groupadd --gid "$HOST_GID" "hostgroup-$HOST_GID"
getent passwd "$HOST_UID" >/dev/null || useradd --uid "$HOST_UID" --gid "$HOST_GID"     --no-create-home --home-dir /home/yocto --shell /bin/bash "hostuser-$HOST_UID"
install -d -o "$HOST_UID" -g "$HOST_GID" /home/yocto
export HOME=/home/yocto
export USER=$(getent passwd "$HOST_UID" | cut -d: -f1)
export LOGNAME=$USER
# Only the server owns its local database files; never chown /project (NFS).
if [[ ${1:-} == /opt/edf/sources/poky/bitbake/bin/bitbake-hashserv ]]; then
    case $(stat -f -c %T /hashserv) in ext2/ext3|xfs|btrfs|overlayfs) ;; *) echo 'Hash database/socket require local Linux storage.' >&2; exit 2;; esac
    shopt -s nullglob
    chown "$HOST_UID:$HOST_GID" /hashserv /hashserv/hashserv.db* /hashserv/hashserv.sock*
fi
if [[ -d /home/amd-edf/edf && $(stat -f -c %T /home/amd-edf/edf) != nfs* ]]; then
    if [[ $(stat -c %u /home/amd-edf/edf) == 0 ]]; then
        chown "$HOST_UID:$HOST_GID" /home/amd-edf/edf
    fi
fi
exec setpriv --reuid="$HOST_UID" --regid="$HOST_GID" --groups="$HOST_GROUPS" "$@"
