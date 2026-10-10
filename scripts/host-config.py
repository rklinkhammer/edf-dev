#!/usr/bin/env python3
"""Resolve Compose/.env paths before containers can create fallback directories."""
import json, os, pathlib, subprocess
command=['docker']
if os.environ.get('EDF_DOCKER_CONTEXT'): command += ['--context',os.environ['EDF_DOCKER_CONTEXT']]
try:
    config=json.loads(subprocess.check_output(command+['compose','config','--format','json'],text=True))
except subprocess.CalledProcessError as error:
    raise SystemExit(error.returncode)
artifact=None
for mount in config['services']['shell']['volumes']:
    if mount['type']=='bind':
        path=pathlib.Path(mount['source'])
        if not path.exists() and path in [pathlib.Path.cwd()/name for name in ('downloads','sstate-cache','artifacts')]:
            path.mkdir()
        if not path.is_dir(): raise SystemExit(f'Pre-create bind directory with appropriate permissions: {path}')
        if not os.access(path,os.R_OK|os.X_OK): raise SystemExit(f'Cannot read bind directory: {path}')
        writable_targets={'/home/amd-edf/edf','/home/amd-edf/edf/downloads','/home/amd-edf/edf/sstate-cache','/artifacts'}
        if mount['target'] in writable_targets and not os.access(path,os.W_OK):
            raise SystemExit(f'Invoking user cannot write bind directory: {path}')
    if mount['target']=='/artifacts': artifact=mount['source']
if not artifact: raise SystemExit('Compose has no artifact bind directory')
print(artifact)
