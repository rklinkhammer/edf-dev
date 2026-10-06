"""Isolated setup/dispatch checks: fake upstream init and BitBake, no source builds."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
from pathlib import Path
import os, subprocess
root=Path('/home/amd-edf/edf'); micro=Path('/home/amd-edf/microchip')
(micro/'openembedded-core').mkdir()
init=''' + "'''" + r'''
export BUILDDIR="$1"
mkdir -p "$BUILDDIR/conf"
cd "$BUILDDIR"
touch conf/local.conf
export PATH="/tmp/mock-bin:$PATH"
''' + "'''" + r'''
(root/'edf-init-build-env').write_text(init)
(micro/'openembedded-core/oe-init-build-env').write_text(init)
Path('/tmp/mock-bin').mkdir()
bitbake=Path('/tmp/mock-bin/bitbake')
bitbake.write_text('#!/bin/bash\nprintf "%s|%s\\n" "$MACHINE" "$*" >> /tmp/calls\n')
bitbake.chmod(0o755)
for target,board,image,boot,recipe in [
 ('zc702','zynq-zc702-sdt-full','amd-cortexa9thf-neon-common','xilinx-bootbin','edf-linux-disk-image'),
 ('zcu111','zynqmp-zcu111-sdt-full','amd-cortexa53-common','xilinx-bootbin','edf-linux-disk-image'),
 ('mpfs-disco-kit','mpfs-disco-kit','mpfs-disco-kit','virtual/bootloader','mchp-base-image')]:
 env=dict(os.environ,EDF_TARGET=target)
 build=root/'builds'/target
 (build/'conf').mkdir(parents=True)
 (build/'conf/edf-policy.conf').write_text('# user override retained\n')
 for action in ('boot','linux','sdk','check'):
  subprocess.run(['bash','/opt/edf-scripts/build.sh',action],env=env,check=True)
 conf=(build/'conf/local.conf').read_text()
 assert conf.count('require /opt/edf-config/build-policy.inc')==1
 assert conf.count('include conf/edf-policy.conf')==1
 assert (build/'conf/edf-policy.conf').read_text()=='# user override retained\n'
 lines=Path('/tmp/calls').read_text().splitlines()
 assert lines==[f'{board}|{boot}',f'{image}|{recipe}',f'{image}|{recipe} -c populate_sdk',f'{board}|-n --no-setscene {boot}',f'{image}|-n --no-setscene {recipe}'],lines
 Path('/tmp/calls').unlink()
print('PASS: all target boot/image/SDK/check routing; repeated policy setup preserves overrides')
'''

@unittest.skipUnless(os.environ.get('EDF_DOCKER_TESTS') == '1', 'requires Docker image')
class TargetDispatch(unittest.TestCase):
    def test_all_targets(self):
        subprocess.run(['docker','--context','orbstack','run','--rm','--network','none',
                        '--platform','linux/amd64',
                        '--tmpfs','/home/amd-edf/edf:mode=1777',
                        '--tmpfs','/home/amd-edf/microchip:mode=1777',
                        '-v',f'{ROOT}/scripts:/opt/edf-scripts:ro',
                        '-v',f'{ROOT}/config:/opt/edf-config:ro',
                        '--entrypoint','python3','edf-dev:ubuntu2204-26.06.1','-c',PROBE],check=True)
