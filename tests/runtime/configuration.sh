#!/bin/bash
set -eo pipefail
for EDF_TARGET in zc702 zcu111; do
  export EDF_TARGET
  source /opt/edf-config/targets.sh
  probe=$(mktemp -d)
  python3 /opt/edf-scripts/configure.py "$probe"
  cd /opt/edf
  source ./edf-init-build-env "$probe" > "$probe/init.log" 2>&1
  MACHINE="$BOARD_MACHINE" bitbake -e > "$probe/board.env"
  MACHINE="$LINUX_MACHINE" bitbake -e > "$probe/linux.env"
  python3 - "$probe" <<'PY'
import pathlib,os,sys
p=pathlib.Path(sys.argv[1])
for file,machine in [('board.env',os.environ['BOARD_MACHINE']),('linux.env',os.environ['LINUX_MACHINE'])]:
    text=(p/file).read_text().splitlines()
    assert f'MACHINE="{machine}"' in text
    assert 'BB_SIGNATURE_HANDLER="OEEquivHash"' in text
    assert 'BB_HASHSERVE="unix:///hashserv/hashserv.sock"' in text
    assert f'TMPDIR="{p}/tmp"' in text
print('PASS effective firmware/Linux machines and hash/storage policy:',os.environ['EDF_TARGET'])
PY
  cd /home/amd-edf/edf
  rm -rf "$probe"
done
