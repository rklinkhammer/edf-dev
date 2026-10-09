#!/usr/bin/env python3
"""Assemble a separate selected-board SD image; never modify Yocto deploy inputs."""
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def config(path):
    parser = configparser.ConfigParser(interpolation=None)
    with path.open() as stream:
        parser.read_file(stream)
    return parser['config_bsp']


def require(path, remedy):
    if not path.is_file():
        raise RuntimeError(f'Missing {path}\n{remedy}')
    return path.resolve()


def merge_configs(tool, bootconf, imageconf):
    args = [sys.executable, tool, 'load', bootconf]
    # qemuboot-tool rejects removal of absent keys. ZynqMP omits qb_kernel_root.
    for key in ('image_link_name', 'image_name', 'qb_kernel_root'):
        if key in config(bootconf):
            args.extend(('remove', key))
    args.extend(('merge', imageconf))
    try:
        return run(*args, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as error:
        detail = '\n'.join(part.strip() for part in (error.stdout, error.stderr) if part and part.strip())
        raise RuntimeError(f'qemuboot-tool merge failed (exit {error.returncode}):\n{detail}') from error


def main(build):
    deploy = build / 'tmp/deploy/images'
    board_machine = os.environ['BOARD_MACHINE']
    linux_machine = os.environ['LINUX_MACHINE']
    target = os.environ['EDF_TARGET']
    board = deploy / board_machine
    linux = deploy / linux_machine
    bootconf = require(board / f'BOOT-{board_machine}.qemuboot.conf', 'Run ./edf boot first.')
    imageconf = require(linux / f'edf-linux-disk-image-{linux_machine}.rootfs.qemuboot.conf', 'Run ./edf linux first.')
    b, i = config(bootconf), config(imageconf)
    if b['machine'] != board_machine or i['machine'] != linux_machine:
        raise RuntimeError('Unexpected machine in QEMU input configurations.')
    disk = require(linux / (i['image_link_name'] + '.wic.qemu-sd'), 'Run ./edf linux first.')
    boot = require(board / b['qb_default_kernel'], 'Run ./edf boot first.')
    dtb = require(board / b['qb_dtb'], 'Run ./edf boot first.')
    native = (linux / i['staging_dir_native']).resolve()
    qemubin = (board / b['staging_bindir_native']).resolve()
    require(qemubin / b['qb_system_name'], 'Inside ./edf shell, source /opt/edf-scripts/yocto-env.sh and run: MACHINE=$BOARD_MACHINE bitbake qemu-helper-native')
    require(native / 'usr/bin/mcopy', 'Run ./edf linux to populate its native sysroot.')
    require(native / 'usr/sbin/parted', 'Run ./edf linux to populate its native sysroot.')
    tool = Path('/opt/edf/sources/meta-xilinx/meta-xilinx-core/scripts/qemuboot-tool')
    require(tool, 'Rebuild the source-pinned EDF container.')
    merged = merge_configs(tool, bootconf, imageconf)
    stage = deploy / f'{target}-qemu'
    stage.mkdir(exist_ok=True)
    # Each run creates a fresh copy from the immutable deploy input. Reflink when supported.
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=stage) as tmp:
        tmp = Path(tmp)
        staged_disk = tmp / disk.name
        run('cp', '--reflink=auto', '--sparse=always', disk, staged_disk)
        shutil.copy2(boot, tmp / 'boot.bin')
        run('wic', 'cp', tmp / 'boot.bin', str(staged_disk) + ':1', '--native-sysroot', native)
        # Verify that the inserted firmware is byte-for-byte the selected board build.
        extracted = tmp / 'verify'
        extracted.mkdir()
        run('wic', 'cp', str(staged_disk) + ':1/boot.bin', extracted, '--native-sysroot', native)
        if (extracted / 'boot.bin').read_bytes() != boot.read_bytes():
            raise RuntimeError('BOOT.BIN verification failed.')
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read_string(merged)
        c = cfg['config_bsp']
        # PMU ROM and PMU hardware DTB stay in the board deploy directory.
        # The ZynqMP helper runs two emulators; preserve those auxiliary paths.
        for key in list(c):
            if key.startswith('qb_'):
                c[key] = c[key].replace('@DEPLOY_DIR_IMAGE@', str(board))
        c['deploy_dir_image'] = str(stage)
        c['image_name'] = target
        c['image_link_name'] = target
        c['qb_rootfs'] = str(stage / f'{target}.wic.qemu-sd')
        c['qb_default_kernel'] = str(stage / 'boot.bin')
        c['qb_dtb'] = str(stage / 'system.dtb')
        # Keep paths valid even though the merged file is in a separate directory.
        for key in ('staging_bindir_native', 'staging_dir_host', 'staging_dir_native', 'uninative_loader'):
            if c.get(key):
                c[key] = str((board / c[key]).resolve())
        # Fully cached firmware builds need not materialize their recipe sysroots.
        # The image build supplies the native tools used for WIC and launch.
        c['staging_dir_native'] = str(native)
        c['staging_dir_host'] = str((linux / i['staging_dir_host']).resolve())
        shutil.copy2(dtb, tmp / 'system.dtb')
        with (tmp / f'{target}.qemuboot.conf').open('w') as stream:
            cfg.write(stream)
        os.replace(staged_disk, stage / f'{target}.wic.qemu-sd')
        for name in ('boot.bin', 'system.dtb', f'{target}.qemuboot.conf'):
            os.replace(tmp / name, stage / name)
    print(f'Prepared {stage}/{target}.qemuboot.conf', flush=True)


if __name__ == '__main__':
    try:
        main(Path(sys.argv[1]).resolve())
    except (RuntimeError, OSError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f'QEMU preparation failed: {error}')
