#!/usr/bin/env python3
"""Export Microchip's native WIC layout without AMD firmware insertion."""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import importlib.util

spec = importlib.util.spec_from_file_location('edf_export', Path(__file__).with_name('export.py'))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def main(build, output_root=Path("/artifacts")):
    target = os.environ['EDF_TARGET']
    # Read final BitBake settings; parsing is not a recipe build.
    result = common.run('bitbake','-e',os.environ['IMAGE_RECIPE'],capture_output=True,text=True).stdout
    def value(key):
        matches=re.findall(r'^(?:export )?'+re.escape(key)+r'="(.*)"$',result,re.M)
        if not matches: raise RuntimeError(f'Missing BitBake setting {key}')
        return matches[-1]
    if value('MACHINE') != 'mpfs-disco-kit': raise RuntimeError('Unexpected Microchip machine')
    deploy=Path(value('DEPLOY_DIR_IMAGE'))
    link=value('IMAGE_LINK_NAME')
    disk=common.required(deploy/(link+'.wic'))
    # Pin rootfs and manifest to the same build generation as the resolved WIC.
    stem=disk.name[:-4]
    files={'rootfs.tar.gz': common.required(deploy/(stem+'.tar.gz')),
           'packages.manifest':common.required(deploy/(stem+'.manifest')),
           'payload.bin':common.required(deploy/'payload.bin'),
           'fitImage':common.required(deploy/'fitImage'),
           'boot.scr':common.required(deploy/'boot.scr')}
    for name in ('u-boot.bin','u-boot.elf','uboot.env','mpfs-disco-kit.dtb'):
        if (deploy/name).is_file(): files[name]=(deploy/name).resolve()
    sdk=Path(value('DEPLOY_DIR_SDK'))
    sdks=sorted(p for p in sdk.glob('*') if p.is_file() and target in p.name and 'mchp-base-image' in p.name)
    parent=output_root/target;parent.mkdir(parents=True,exist_ok=True)
    needed=disk.stat().st_size+sum(p.stat().st_size for p in files.values())+sum(p.stat().st_size for p in sdks)+2*1024**3
    if shutil.disk_usage(parent).free<needed:raise RuntimeError('Insufficient export space plus 2 GiB reserve')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    final=parent/(stamp+'-'+uuid.uuid4().hex[:8])
    original=common.digest(disk)
    with tempfile.TemporaryDirectory(prefix='.export-',dir=parent) as temp:
        out=Path(temp)
        print('Collecting Discovery Kit artifacts; preserving Microchip WIC layout.',flush=True)
        for name,p in files.items():shutil.copy2(p,out/name)
        common.run('bmaptool','create','-o',out/'sdcard.wic.bmap',disk)
        with (out/'sdcard.wic.gz').open('wb') as stream:
            common.run('gzip','-1','-c',disk,stdout=stream)
        with gzip.open(out/'sdcard.wic.gz','rb') as stream:
            h=hashlib.sha256()
            for block in iter(lambda:stream.read(4194304),b''):h.update(block)
        if h.hexdigest()!=original or common.digest(disk)!=original:raise RuntimeError('WIC integrity check failed')
        if sdks:
            (out/'sdk').mkdir()
            for p in sdks:shutil.copy2(p,out/'sdk'/p.name)
        source=Path(os.environ['SOURCE_ROOT'])
        common.run(sys.executable,source/'.repo/repo/repo','manifest','-r','-o',out/'source-manifest.xml',cwd=source)
        info={'target':target,'vendor':'microchip','release':'linux4microchip-2026.04',
              'exported_utc':stamp,'image_recipe':os.environ['IMAGE_RECIPE'],'source_wic':str(disk),
              'sdcard_wic_sha256':original,'sdcard_wic_bytes':disk.stat().st_size,
              'sdk_files':[p.name for p in sdks],
              'source_manifest_scope':'Checkout revisions at export, not attested build provenance',
              'hardware_boot_verified':False}
        (out/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
        (out/'README.txt').write_text('Discovery Kit SD image, original Microchip partition layout.\n'
            'Write sdcard.wic.gz as a whole-disk image using its bmap, or decompress first.\n'
            'Writing overwrites the selected card. No device was flashed by this command.\n'
            'Board HSS/FPGA reference design must be compatible with release 2026.04.\n'
            'payload.bin is an HSS payload containing U-Boot, not the board HSS firmware itself.\n'
            'Physical boot remains unverified. rootfs.tar.gz alone is not an SD image.\n')
        (out/'SHA256SUMS').write_text(''.join(f'{common.digest(p)}  {p.relative_to(out)}\n' for p in sorted(out.rglob('*')) if p.is_file()))
        out.rename(final)
    print(f'Export complete: {final}',flush=True)

if __name__=='__main__':
    try:main(Path(sys.argv[1]))
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:sys.exit(f'Export failed: {error}')
