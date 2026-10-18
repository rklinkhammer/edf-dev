#!/usr/bin/env python3
"""Build/export Vivado hardware, generate SDT/EDF inputs, then install a verified bundle."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
import runpy

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hardware_bundle import pack, unpack
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
    inputs.add_argument('--project', type=Path, default=None, help='Legacy saved project override; skips DMOTOR HLS/IP rebuild')
    inputs.add_argument('--xsa', type=Path, help='Use an existing fixed XSA including bitstream; skip Vivado')
    inputs.add_argument('--bundle', type=Path, help='Import a verified portable bundle; no AMD tools required')
    parser.add_argument('--force', action='store_true', help='Rebuild tested DMOTOR IP even if fingerprint matches')
    parser.add_argument('--vivado', type=Path, default=Path('/opt/vitis/2026.1/Vivado/bin/vivado'))
    parser.add_argument('--sdtgen', type=Path, default=Path('/opt/vitis/2026.1/Vitis/bin/sdtgen'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--dry-run', action='store_true', help='Print stages; no tools, import or directories')
    parser.add_argument('--generate-only', action='store_true', help='Build and validate candidate without importing')
    parser.add_argument('--export-image', action='store_true', help='After import, build and export Linux/boot image')
    args = parser.parse_args()
    if args.jobs < 1 or (args.generate_only and args.export_image):
        parser.error('Positive jobs required; generate-only cannot export an image')
    dmotor = runpy.run_path(str(ROOT/'scripts/dmotor-source.py'))['resolve']()
    env = {**os.environ, 'EDF_DMOTOR_SOURCE':str(dmotor)}
    product = not (args.project or args.xsa or args.bundle)
    if product and not (dmotor/'tools/build.py').is_file():
        parser.error('Selected DMOTOR revision predates the product workflow; update the pin or set EDF_DMOTOR_SOURCE')
    hardware_key = runpy.run_path(str(dmotor/'tools/build.py'))['fingerprint']() if product else None
    source = (args.bundle or args.xsa or args.project or dmotor/'build/product/vivado/dvrmc.xpr').expanduser().resolve()
    if not product and not source.is_file(): parser.error(f'Missing input: {source}')
    print(f'DMOTOR hardware/software source: {dmotor}\nInput: {source}',flush=True)
    if args.dry_run:
        if product:
            run([sys.executable,dmotor/'tools/build.py','project','--dry-run'],dmotor,env)
        print('Stages: '+('verified bundle import' if args.bundle else 'Vivado/XSA -> SDT -> candidate validation -> bundle -> import')+
              (' -> image -> export' if args.export_image else ''),flush=True)
        return
    if product:
        run([sys.executable,dmotor/'tools/build.py','project','--amd-root',args.vivado.parents[2]]+
            (['--force'] if args.force else []),dmotor,env)
    if not args.bundle:
        for tool in ([args.sdtgen] if args.xsa else [args.vivado,args.sdtgen]):
            if not tool.is_file(): parser.error(f'Missing AMD tool: {tool}')
    docker = ['docker']
    if os.environ.get('EDF_DOCKER_CONTEXT'): docker += ['--context',os.environ['EDF_DOCKER_CONTEXT']]
    artifacts = Path(subprocess.check_output(['python3','scripts/host-config.py'],cwd=ROOT,text=True).strip())
    stage = artifacts/'arty-hardware'/ (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    stage.mkdir(parents=True)
    print(f'Logs, candidate and backup: {stage}',flush=True)
    env['EDF_ARTIFACTS']=str(artifacts)
    if args.bundle:
        record=unpack(source,stage/'imported')
        candidate=stage/'imported/candidate'
        importer.verify(candidate)
        expected=record.get('dmotor_hardware_sha256')
        if expected and expected != runpy.run_path(str(dmotor/'tools/build.py'))['fingerprint']():
            raise ValueError('Bundle and selected DMOTOR hardware sources differ; select the matching checkout')
        if not args.generate_only: publish(candidate,ROOT,stage/'previous')
        if args.export_image:
            for action in ('image','export'): run([ROOT/'edf','--target','arty-z7-20',action],ROOT,env)
        print(('Verified candidate bundle: ' if args.generate_only else 'Imported verified bundle: ')+str(stage),flush=True)
        return
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
              'generate_only':args.generate_only,'dmotor_source':str(dmotor)},indent=2)+'\n')
    if product and hardware_key != runpy.run_path(str(dmotor/'tools/build.py'))['fingerprint']():
        raise ValueError('DMOTOR sources changed during board build; candidate not imported')
    metadata={'dmotor_commit':subprocess.check_output(['git','-C',str(dmotor),'rev-parse','HEAD'],text=True).strip(),
              'dmotor_hardware_sha256':hardware_key,
              'tools':{'vivado':str(args.vivado),'sdtgen':str(args.sdtgen)},
              'origin':'product' if product else 'legacy-explicit-input'}
    manifest_path=candidate/importer.MANIFEST
    manifest=json.loads(manifest_path.read_text())
    manifest['dmotor']=metadata
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Portable hardware bundle: '+str(pack(stage,metadata)),flush=True)
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
