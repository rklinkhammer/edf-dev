"""Run isolated interactive-shell checks against the existing container image."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORKER = '''#!/bin/bash
exec 9>/tmp/edf-shell-test.lock
flock -n 9 || exit 99
printf 'WORKER %s %s %s\\n' "$EDF_TARGET" "$0" "$1"
if [[ $1 == boot && $0 == */build.sh ]]; then sleep 600; fi
if [[ $1 == sdk ]]; then exit 23; fi
'''
TEST = r'''
import pexpect
for target in ('zc702','zcu111'):
    import os
    env = dict(os.environ, EDF_TARGET=target)
    child = pexpect.spawn('/bin/bash', ['--noprofile','--rcfile','/opt/edf-scripts/shell-rc.sh','-i'], env=env, encoding='utf-8', timeout=15)
    prompt = r'\[edf:' + target + r'\].*\$ '
    child.expect(prompt)
    child.sendline('edf-build help'); child.expect('Usage: edf-build'); child.expect(prompt)
    child.sendline('edf-build boot'); child.expect('WORKER '+target+' /opt/edf-scripts/build.sh boot')
    child.sendcontrol('c'); child.expect(prompt)
    child.sendline('flock -n /tmp/edf-shell-test.lock echo LOCK_FREE'); child.expect(r'\r\nLOCK_FREE\r\n'); child.expect(prompt)
    child.sendline('edf-build sdk; echo RESULT=$?'); child.expect(r'\r\nRESULT=23\r\n'); child.expect(prompt)
    child.sendline('edf-build linux'); child.expect('WORKER '+target+' /opt/edf-scripts/build.sh linux'); child.expect(prompt)
    child.sendline('edf-build qemu'); child.expect('WORKER '+target+' /opt/edf-scripts/qemu.sh boot'); child.expect(prompt)
    child.sendline('edf-build invalid; echo RESULT=$?'); child.expect(r'\r\nRESULT=2\r\n'); child.expect(prompt)
    child.sendline('exit'); child.expect(pexpect.EOF)
from pathlib import Path
for target in ('zc702','zcu111'):
    logs=list(Path('/artifacts/logs',target).glob('*-linux-*.log'))
    assert logs and ('WORKER '+target) in logs[0].read_text()
print('PASS: both targets, help, dispatch, Ctrl+C returns to shell, lock release, failure status, logs')
'''
with tempfile.TemporaryDirectory(prefix='edf-shell-test-') as temp:
    base=Path(temp)
    (base/'worker.sh').write_text(WORKER)
    (base/'test.py').write_text(TEST)
    subprocess.run(['docker','--context','orbstack','run','--rm','--network','none','--platform','linux/amd64',
                    '--tmpfs','/artifacts:mode=1777',
                    '-v',f'{ROOT}/scripts:/opt/edf-scripts:ro','-v',f'{ROOT}/config:/opt/edf-config:ro',
                    '-v',f'{base}/worker.sh:/opt/edf-scripts/build.sh:ro',
                    '-v',f'{base}/worker.sh:/opt/edf-scripts/qemu.sh:ro',
                    '-v',f'{base}/test.py:/tmp/test.py:ro',
                    '--entrypoint','python3','edf-dev:ubuntu2204-26.06.1','/tmp/test.py'],check=True)
