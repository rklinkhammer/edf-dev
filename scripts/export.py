#!/usr/bin/env python3
"""Collect immutable artifacts and create a board-specific SD image copy."""
import configparser
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def required(path):
    if not path.is_file():
        raise RuntimeError(f'Missing {path}. Complete firmware and Linux builds first.')
    return path.resolve()


def config(path):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(required(path))
    return cfg['config_bsp']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main(build):
    target, board, linux = (os.environ[k] for k in ('EDF_TARGET', 'BOARD_MACHINE', 'LINUX_MACHINE'))
    deploy = build/'tmp/deploy/images'
    bp, lp = deploy/board, deploy/linux
    bc = config(bp/f'BOOT-{board}.qemuboot.conf')
    ic = config(lp/f'edf-linux-disk-image-{linux}.rootfs.qemuboot.conf')
    if bc['machine'] != board or ic['machine'] != linux:
        raise RuntimeError('Input machine mismatch; refusing to mix board artifacts.')
    stem = lp/ic['image_name']  # Pin to the same image generation, not drifting symlinks.
    disk = required(Path(str(stem)+'.wic'))
    inputs = {
        'boot.bin': required(bp/bc['qb_default_kernel']),
        'system.dtb': required(bp/bc['qb_dtb']),
        ic['kernel_imagetype']: required(lp/ic['kernel_imagetype']),
        'rootfs.tar.gz': required(Path(str(stem)+'.tar.gz')),
        'packages.manifest': required(Path(str(stem)+'.manifest')),
    }
    native = (lp/ic['staging_dir_native']).resolve()
    for tool in ('usr/bin/mcopy','usr/sbin/parted'):
        required(native/tool)
    env = {**os.environ, 'PATH': os.environ['PATH']+f':{native}/usr/bin:{native}/usr/sbin'}
    parent = Path('/artifacts')/target
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    final = parent/f'{stamp}-{uuid.uuid4().hex[:8]}'
    sdks = sorted(p for p in (build/'tmp/deploy/sdk').glob('*')
                  if p.is_file() and f'-{linux}-toolchain-' in p.name
                  and 'edf-linux-disk-image-' in p.name)
    # Allow for compressed output being as large as raw, copies, and a reserve.
    needed = disk.stat().st_size + sum(p.stat().st_size for p in inputs.values()) + sum(p.stat().st_size for p in sdks) + 2*1024**3
    if shutil.disk_usage(parent).free < needed:
        raise RuntimeError('Insufficient host space for export plus 2 GiB reserve.')
    if shutil.disk_usage(build).free < disk.stat().st_size + 2*1024**3:
        raise RuntimeError('Insufficient Linux workspace space for SD image staging.')
    with tempfile.TemporaryDirectory(prefix='.export-', dir=parent) as output, tempfile.TemporaryDirectory(prefix='export-', dir=build/'tmp') as work:
        out, work = Path(output), Path(work)
        print(f'Exporting {target}: collecting binaries and hashing inputs...', flush=True)
        records = {}
        for name, src in inputs.items():
            shutil.copy2(src, out/name)
            records[name] = {'source': str(src), 'sha256': digest(src)}
            if digest(out/name) != records[name]['sha256']:
                raise RuntimeError(f'Copy verification failed: {name}')
        original_hash = digest(disk)
        staged = work/'sdcard.wic'
        run('cp','--reflink=auto','--sparse=always',disk,staged)
        print('Inserting board firmware into a separate SD image...', flush=True)
        listing = run('wic','ls',staged,'--native-sysroot',native,env=env,capture_output=True,text=True).stdout
        (out/'partitions.txt').write_text(listing)
        # Current EDF SD layout requires its first partition to be FAT.
        if not any(line.split() and line.split()[0] == '1' and 'fat' in line.lower() for line in listing.splitlines()):
            raise RuntimeError('Expected FAT boot partition 1; refusing unknown disk layout.')
        run('wic','cp',out/'boot.bin',str(staged)+':1/boot.bin','--native-sysroot',native,env=env)
        verify = work/'verify'; verify.mkdir()
        run('wic','cp',str(staged)+':1/boot.bin',verify,'--native-sysroot',native,env=env)
        if digest(verify/'boot.bin') != records['boot.bin']['sha256']:
            raise RuntimeError('Firmware read-back verification failed.')
        print('Regenerating block map and compressing SD image...', flush=True)
        run('bmaptool','create','-o',out/'sdcard.wic.bmap',staged)
        raw_hash = digest(staged)
        with (out/'sdcard.wic.xz').open('wb') as stream:
            run('xz','-T2','-1','-c',staged,stdout=stream)
        run('xz','-t',out/'sdcard.wic.xz')
        if digest(disk) != original_hash:
            raise RuntimeError('Source WIC changed during export.')
        if sdks:
            (out/'sdk').mkdir()
            for src in sdks:
                shutil.copy2(src, out/'sdk'/src.name)
        root = Path('/opt/edf')
        shutil.copy2(root/'source-manifest.xml', out/'source-manifest.xml')
        shutil.copy2('/usr/local/share/edf-dev/packages.tsv', out/'container-packages.tsv')
        info = {'target':target, 'board_machine':board, 'linux_machine':linux,
                'exported_utc':stamp, 'image_name':ic['image_name'],
                'firmware_config':str((bp/f'BOOT-{board}.qemuboot.conf').resolve()),
                'inputs':records, 'original_wic':{'source':str(disk),'sha256':original_hash},
                'sdcard_wic_sha256':raw_hash, 'sdcard_wic_bytes':staged.stat().st_size,
                'sdk_files':[p.name for p in sdks],
                'source_manifest_scope':'Pinned container source revisions; not an attestation of every fetched recipe input.',
                'verification':'Firmware read-back, source WIC unchanged, compressed stream integrity; physical boot not tested.'}
        (out/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
        (out/'README.txt').write_text(f'''{target} SD-card export
sdcard.wic.xz contains the complete partitioned disk image with this board's boot.bin.
Decompress with xz -dk sdcard.wic.xz, then write sdcard.wic as a whole-disk image.
The SD card must be at least {staged.stat().st_size} bytes. Writing overwrites the card.
Alternatively, Linux bmaptool can copy sdcard.wic.xz using sdcard.wic.bmap.
rootfs.tar.gz is a filesystem archive, not a bootable disk image.
SHA256SUMS checks exported files; build-info.json also records the uncompressed disk hash.
Physical-board boot has not been verified by this exporter. No device was flashed.
Source manifest records pinned container sources, not an attestation of every fetched recipe input.
''')
        hashes = [f'{digest(p)}  {p.relative_to(out)}\n' for p in sorted(out.rglob('*')) if p.is_file()]
        (out/'SHA256SUMS').write_text(''.join(hashes))
        out.rename(final)
    print(f'Export complete: {final}\nContainer: /artifacts/{target}/{final.name}',flush=True)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        main(Path(sys.argv[1]))
    except (RuntimeError, OSError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f'Export failed: {error}')
