#!/usr/bin/env python3
"""Build/export Vivado hardware, generate SDT/EDF inputs, then install a verified bundle."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('arty_import', ROOT/'scripts/arty-hardware.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)

def run(command, cwd, env=None):
    print('+ '+__import__('shlex').join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, env=env, check=True)

def replace_file(source, destination):
    """Replace generated files even when their preserved source mode is read-only."""
    fd, name = tempfile.mkstemp(prefix='.arty-import-', dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

def publish(candidate, root, backup):
    """Back up every affected file; manifest is published last, rollback on failure."""
    record = json.loads((candidate/importer.MANIFEST).read_text())
    paths = [Path(name) for name in record['files']] + [importer.MANIFEST]
    for path in paths:
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid candidate path')
    backup.mkdir(parents=True)
    existing = []
    for path in paths:
        if (root/path).exists():
            (backup/path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root/path, backup/path)
            existing.append(str(path))
    (backup/'restore.json').write_text(json.dumps({'affected':list(map(str,paths)), 'existed':existing},indent=2))
    try:
        for path in paths:
            (root/path).parent.mkdir(parents=True, exist_ok=True)
            replace_file(candidate/path, root/path)
        importer.verify(root)
    except BaseException:
        for path in paths:
            if str(path) in existing:
                replace_file(backup/path, root/path)
            else:
                (root/path).unlink(missing_ok=True)
        raise

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--project', type=Path, default=None, help='Saved Vivado XPR (default ../dvrmc/dvrmc.xpr)')
    inputs.add_argument('--xsa', type=Path, help='Use an existing fixed XSA including bitstream; skip Vivado')
    parser.add_argument('--vivado', type=Path, default=Path('/opt/vitis/2026.1/Vivado/bin/vivado'))
    parser.add_argument('--sdtgen', type=Path, default=Path('/opt/vitis/2026.1/Vitis/bin/sdtgen'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--dry-run', action='store_true', help='Print stages; no tools, import or directories')
    parser.add_argument('--generate-only', action='store_true', help='Build and validate candidate without importing')
    parser.add_argument('--export-image', action='store_true', help='After import, build and export Linux/boot image')
    args = parser.parse_args()
    if args.jobs < 1 or (args.generate_only and args.export_image):
        parser.error('Positive jobs required; generate-only cannot export an image')
    source = (args.xsa or args.project or ROOT.parent/'dvrmc/dvrmc.xpr').expanduser().resolve()
    if not source.is_file(): parser.error(f'Missing input: {source}')
    print(f'Input: {source}\nStages: '+('XSA copy' if args.xsa else 'Vivado project copy -> synthesis -> implementation -> bitstream -> XSA')+
          ' -> SDTGen -> container gen-machine-conf -> candidate verification -> '+
          ('retain candidate' if args.generate_only else 'backup + import')+
          (' -> EDF image + export' if args.export_image else ''), flush=True)
    if args.dry_run: return
    for tool in ([args.sdtgen] if args.xsa else [args.vivado,args.sdtgen]):
        if not tool.is_file(): parser.error(f'Missing AMD tool: {tool}')
    docker = ['docker']
    if os.environ.get('EDF_DOCKER_CONTEXT'): docker += ['--context',os.environ['EDF_DOCKER_CONTEXT']]
    artifacts = Path(subprocess.check_output(['python3','scripts/host-config.py'],cwd=ROOT,text=True).strip())
    stage = artifacts/'arty-hardware'/ (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    stage.mkdir(parents=True)
    print(f'Logs, candidate and backup: {stage}',flush=True)
    env = {**os.environ, 'EDF_ARTIFACTS':str(artifacts)}
    if args.xsa: shutil.copy2(source,stage/'dvrmc.xsa')
    else:
        run([args.vivado,'-mode','batch','-source',ROOT/'scripts/vivado/arty-build.tcl',
             '-tclargs',source,stage,args.jobs],stage)
    run([args.sdtgen,'-xsa',stage/'dvrmc.xsa','-dir',stage/'sdt'],stage)
    # Mount staging independently of /hardware: failed generation cannot damage live inputs.
    run(docker+['compose','up','-d','--build','--wait','hashserv'],ROOT,env)
    run(docker+['compose','run','--rm','--no-deps','-T','-v',f'{stage}:/generation',
                '-e','EDF_TARGET=zc702','shell','bash','/opt/edf-scripts/arty-generate.sh'],ROOT,env)
    candidate = stage/'candidate'
    importer.install(candidate,stage/'sdt',stage/'conf')
    importer.verify(candidate)
    (stage/'workflow.json').write_text(json.dumps({'source':str(source),'xsa_sha256':importer.sha(stage/'dvrmc.xsa'),
              'generate_only':args.generate_only},indent=2)+'\n')
    if not args.generate_only:
        publish(candidate,ROOT,stage/'previous')
        print('Installed and verified matched Arty bundle.',flush=True)
    if args.export_image:
        for action in ('image','export'):
            run([ROOT/'edf','--target','arty-z7-20',action],ROOT,env)
    print(f'Complete: {stage}',flush=True)

if __name__ == '__main__':
    try: main()
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        sys.exit(f'Hardware workflow failed; inspect the retained staging directory: {error}')
