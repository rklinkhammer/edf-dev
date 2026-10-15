#!/usr/bin/env python3
"""Install or verify a matched SDT, Linux overlay, bitstream and EDF machine bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

MACHINE = 'arty-z7-20'
MANIFEST = Path('config/hardware/arty-z7-20.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(root, sdt, conf):
    for name in (f'machine/{MACHINE}.conf', f'multiconfig/{MACHINE}-cortexa9-fsbl.conf',
                 f'dts/{MACHINE}/{MACHINE}-cortexa9-fsbl.dts'):
        if not (conf / name).is_file():
            raise ValueError(f'Missing generated machine input: {name}')
    bits = list(sdt.glob('*.bit'))
    if len(bits) != 1:
        raise ValueError('SDT directory must contain exactly one exported bitstream')
    linux = conf / f'dts/{MACHINE}/cortexa9-linux.dts'
    overlay = conf / f'dts/{MACHINE}/pl-overlay-full/pl.dtso'
    if '43c00000' in linux.read_text() or 'firmware-name' in linux.read_text():
        raise ValueError('Generate with -g full: base Linux tree must not contain PL devices or firmware')
    if '43c00000' not in overlay.read_text() or 'firmware-name' not in overlay.read_text():
        raise ValueError('Expected DVRMC controller and firmware reference in full overlay')
    if 'arty-z7-20' not in (sdt / 'system-top.dts').read_text():
        raise ValueError('Expected an Arty Z7-20 SDT export')
    destination = root / f'hardware/{MACHINE}'
    destination.mkdir(parents=True, exist_ok=True)
    if sdt.resolve() != (destination / 'sdt').resolve():
        if (destination / 'sdt').exists():
            shutil.rmtree(destination / 'sdt')
        shutil.copytree(sdt, destination / 'sdt')
    shutil.copy2(destination / 'sdt' / bits[0].name, destination / 'dvrmc.bit')
    overlay_text = re.sub(r'(&amba\s*\{)(?!\s*#address-cells)',
                          r'\1\n        #address-cells = <1>;\n        #size-cells = <1>;',
                          overlay.read_text())
    (destination / 'dvrmc.dtso').write_text(overlay_text)
    tracked = []
    for source in sorted(conf.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(conf)
        if MACHINE not in str(relative):
            continue
        target = root / 'meta-edf-dev/conf' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_text()
        if source == overlay:
            content = overlay_text
        if relative == Path(f'machine/{MACHINE}.conf'):
            lines = content.splitlines()
            lines = [f'SDT_URI = "file:///hardware/{MACHINE}/sdt"' if line.startswith('SDT_URI =')
                     else f'SDT_URI[S] = "${{WORKDIR}}/hardware/{MACHINE}/sdt"' if line.startswith('SDT_URI[S]')
                     else line for line in lines]
            content = '\n'.join(lines) + '\n'
        if source == linux:
            # Built-in UIO matching must be present before Linux driver init.
            chosen = re.search(r'(\bchosen\s*\{)(.*?)(\};)', content, flags=re.S)
            if not chosen:
                raise ValueError('Linux base tree lacks /chosen')
            body = chosen.group(2)
            argument = 'uio_pdrv_genirq.of_id=generic-uio'
            bootargs = re.search(r'bootargs\s*=\s*"([^"\n]*)"\s*;', body)
            if bootargs:
                args = bootargs.group(1).split()
                args = [arg for arg in args if not arg.startswith('uio_pdrv_genirq.of_id=')]
                args.append(argument)
                body = body[:bootargs.start()] + 'bootargs = "' + ' '.join(args) + '";' + body[bootargs.end():]
            else:
                body = '\n                bootargs = "' + argument + '";' + body
            content = content[:chosen.start(2)] + body + content[chosen.end(2):]
            # Regenerate symbols with dtc -@; Lopper's memory-node symbol can be stale.
            content = re.sub(r'\n        __symbols__ \{.*?\n        \};', '', content, flags=re.S)
            # SDTGen 2026.1 emits a MicroBlaze root compatible for this Zynq board.
            content = content.replace('compatible = "xlnx,arty-z7-20-microblaze";',
                                      'compatible = "digilent,arty-z7-20", "xlnx,zynq-7000";')
            content = content.replace('model = "Xilinx Zynq";', 'model = "Digilent Arty Z7-20 DVRMC";')
            if '"xlnx,zynq-7000"' not in content:
                raise ValueError('Linux tree lacks Zynq-7000 machine compatible')
        target.write_text(content)
        tracked.append(target)
    files = tracked + [destination / 'dvrmc.bit', destination / 'dvrmc.dtso']
    files += sorted(p for p in (destination / 'sdt').rglob('*') if p.is_file())
    record = {'machine': MACHINE, 'tools': 'Vivado/SDTGen and EDF gen-machine-conf 2026.1',
              'load_method': 'Linux FPGA Manager full overlay',
              'files': {str(p.relative_to(root)): sha(p) for p in files}}
    (root / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text(json.dumps(record, indent=2) + '\n')


def verify(root, hardware=None):
    record = json.loads((root / MANIFEST).read_text())
    for name, expected in record['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'Invalid manifest path: {name}')
        path = (hardware / Path(*relative.parts[1:])
                if hardware is not None and relative.parts[0] == 'hardware' else root / relative)
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f'Missing or changed hardware input: {name}; regenerate the matched bundle (docs/arty.md)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--hardware-root', type=Path)
    parser.add_argument('--sdt', type=Path)
    parser.add_argument('--conf', type=Path)
    args = parser.parse_args()
    if bool(args.sdt) != bool(args.conf):
        parser.error('--sdt and --conf are required together for installation')
    if args.sdt:
        install(args.root.resolve(), args.sdt.resolve(), args.conf.resolve())
    verify(args.root, args.hardware_root)
    print('PASS matched Arty hardware bundle')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        sys.exit(str(error))
