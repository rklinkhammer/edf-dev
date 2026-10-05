#!/bin/bash
set -euo pipefail
id
[[ $(id -u) == 1000 ]]
[[ $(dpkg --print-architecture) == amd64 ]]
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 22.04 ]]
locale charmap | grep -qi 'UTF-8'
for tool in git repo python3 gcc g++ make gawk wget diffstat chrpath socat cpio xz zstd lz4; do
  command -v "$tool"
done
python3 -c 'import yaml, jinja2, pexpect, git'
python3 - <<'PY'
import fcntl, pathlib, tempfile
for base in ['/home/amd-edf/edf','/home/amd-edf/edf/downloads','/home/amd-edf/edf/sstate-cache']:
    with tempfile.TemporaryDirectory(prefix='.edf-check-',dir=base) as name:
        p=pathlib.Path(name)
        (p/'case').write_text('lower')
        (p/'CASE').write_text('upper')
        assert (p/'case').read_text() == 'lower', 'case-insensitive filesystem'
        (p/'link').symlink_to('case')
        assert (p/'link').read_text() == 'lower'
        with (p/'lock').open('w') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print('PASS: writable, case-sensitive, symlinks, file lock:', base)
PY
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
printf 'int main(void){return 0;}\n' > "$scratch/check.c"
gcc "$scratch/check.c" -o "$scratch/check"
"$scratch/check"
getent hosts github.com
printf 'PASS: container smoke checks. Yocto parsing and board builds are separate checks.\n'
