#!/usr/bin/env python3
"""Run an isolated ZC702 build with empty caches and no remote sstate."""
import datetime
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) > 1:
    run = Path(sys.argv[1]).resolve()
    if run.parent != ROOT/'validation':
        sys.exit('Resume requires a run directory directly under this workspace validation/.')
    state = json.loads((run/'status.json').read_text())
    if state['status'] == 'passed':
        sys.exit('This validation already passed. Omit the run directory to start fresh.')
    project, image = state['project'], state['image']
    artifacts = Path(state['artifacts'])
    state.setdefault('resumes', []).append(datetime.datetime.now(datetime.timezone.utc).isoformat())
else:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dt%H%M%Sz').lower()
    project = 'edf-dev-clean-' + stamp
    run = ROOT / 'validation' / project
    artifacts = ROOT / 'artifacts' / project
    run.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    image = 'edf-dev-clean:' + stamp
    state = {'project': project, 'image': image, 'artifacts': str(artifacts),
             'started_utc': stamp, 'completed': [], 'status': 'running'}
override = run / 'compose.override.json'
override.write_text(json.dumps({'services': {name: {
    'image': image,
    'volumes': [{'type': 'bind', 'source': str(artifacts), 'target': '/artifacts'}]
} for name in ('init', 'shell')}}, indent=2))
dc = ['docker', '--context', 'orbstack', 'compose', '-p', project,
      '-f', str(ROOT/'compose.yaml'), '-f', str(override)]
container = None

def save():
    pending = run/'status.tmp'
    pending.write_text(json.dumps(state, indent=2) + '\n')
    pending.replace(run/'status.json')

def stop_container():
    if container:
        subprocess.run(['docker', '--context', 'orbstack', 'stop', '-t', '10', container],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def execute(phase, command, qemu=False):
    if phase in state['completed']:
        print(f'{phase}: already completed in this run', flush=True)
        return
    state.pop('error', None)
    state.update(phase=phase, status='running')
    save()
    print(f'{phase}: started; log {run/ (phase + ".log")}', flush=True)
    with (run/(phase+'.log')).open('wb') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE if qemu else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE if qemu else log, stderr=subprocess.STDOUT, env={**os.environ, 'EDF_TARGET': 'zc702'})
        seen = b''
        prompt_seen = False
        deadline = time.monotonic() + 900 if qemu else None
        try:
            while process.poll() is None:
                if shutil.disk_usage(ROOT).free < 20 * 1024**3:
                    raise RuntimeError('Stopped at the 20 GiB host free-space reserve.')
                if qemu:
                    ready, _, _ = select.select([process.stdout], [], [], 2)
                    if ready:
                        data = os.read(process.stdout.fileno(), 65536)
                        log.write(data); log.flush()
                        seen = (seen + data)[-65536:]
                        if not prompt_seen and b'amd-edf login:' in seen:
                            prompt_seen = True
                            process.stdin.write(b'\x01x'); process.stdin.flush()
                            deadline = time.monotonic() + 60
                    if time.monotonic() > deadline:
                        raise RuntimeError('QEMU did not reach login and exit within the time limit.')
                else:
                    time.sleep(2)
            if qemu:
                log.write(process.stdout.read())
            if process.returncode:
                raise RuntimeError(f'{phase} exited {process.returncode}; see its log.')
            if qemu and not prompt_seen:
                raise RuntimeError('QEMU exited without reaching the login prompt.')
        except BaseException:
            stop_container()
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
            raise
    state['completed'].append(phase)
    save()
    print(f'{phase}: PASS', flush=True)

def shell(phase, script, qemu=False):
    global container
    container = project + '-' + phase
    execute(phase, dc + ['run', '--rm', '--no-deps', '-T', '--name', container,
                         'shell', '-ec', script], qemu=qemu)
    container = None

print(f'Clean validation: {run}', flush=True)
save()
try:
    execute('container-build', dc + ['build', '--pull', '--no-cache', 'shell'])
    execute('init', dc + ['run', '--rm', '--no-deps', '-T', 'init'])
    shell('empty-caches', '''
for folder in downloads sstate-cache; do
  test -z "$(find "$folder" -mindepth 1 -print -quit)"
  printf 'EMPTY: %s\n' "$folder"
done
test ! -e .repo
test ! -e sources
test ! -e builds
printf 'EMPTY: source checkout and build directories\n'
cp /usr/local/share/edf-dev/packages.tsv /artifacts/container-packages.tsv
/opt/edf-scripts/validate.sh
''')
    execute('image-identity', ['docker', '--context', 'orbstack', 'image', 'inspect', image])
    shell('source-sync', '/opt/edf-scripts/sync.sh')
    shell('clean-policy', '''
source /opt/edf-scripts/yocto-env.sh
cat >> conf/local.conf <<'CONF'

# This isolated validation must compile without external shared state.
SSTATE_MIRRORS = ""
BB_HASHSERVE_UPSTREAM = ""
BB_DISKMON_DIRS = "STOPTASKS,${TMPDIR},20G,100K STOPTASKS,${DL_DIR},20G,100K HALT,${TMPDIR},10G,50K"
CONF
cp conf/local.conf /artifacts/zc702-local.conf
bitbake-getvar --value SSTATE_MIRRORS > /artifacts/effective-sstate-mirrors.txt
bitbake-getvar --value BB_HASHSERVE_UPSTREAM > /artifacts/effective-hashserve-upstream.txt
python3 - <<'CHECK'
from pathlib import Path
for name in ('effective-sstate-mirrors.txt', 'effective-hashserve-upstream.txt'):
    value = (Path('/artifacts')/name).read_text().strip().strip('"')
    assert not value, (name, value)
print('PASS: remote sstate and upstream hash equivalence disabled')
CHECK
''')
    shell('zc702-boot', '/opt/edf-scripts/build.sh boot')
    shell('zc702-linux', '/opt/edf-scripts/build.sh linux')
    shell('zc702-qemu', '/opt/edf-scripts/qemu.sh boot', qemu=True)
    shell('export', '''
mkdir -p /artifacts/zc702
cp -L builds/zc702/tmp/deploy/images/zynq-zc702-sdt-full/BOOT-zynq-zc702-sdt-full.bin /artifacts/zc702/BOOT.BIN
cp -L builds/zc702/tmp/deploy/images/amd-cortexa9thf-neon-common/edf-linux-disk-image-amd-cortexa9thf-neon-common.rootfs.wic.xz /artifacts/zc702/linux.wic.xz
cp -L builds/zc702/tmp/deploy/images/amd-cortexa9thf-neon-common/edf-linux-disk-image-amd-cortexa9thf-neon-common.rootfs.wic.bmap /artifacts/zc702/linux.wic.bmap
cp builds/zc702/qemu-console.log /artifacts/zc702/qemu-boot.log
cd /artifacts/zc702
sha256sum BOOT.BIN linux.wic.xz linux.wic.bmap > SHA256SUMS
''')
    state.update(status='passed', phase='complete')
    save()
except BaseException as error:
    state.update(status='failed', error=str(error))
    save()
    raise
